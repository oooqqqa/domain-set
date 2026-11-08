#!/usr/bin/env python3
"""Convert two dnsmasq-china-list sources into deterministic Surge DOMAIN-SETs.

Standard-library only. Fetch, parse and validate *both* sources before any output
is replaced. It is intended for scheduled CI builds, not for on-device DNS queries.
"""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import tempfile
import urllib.request

UPSTREAM = "https://raw.githubusercontent.com/felixonmars/dnsmasq-china-list/master/"
SOURCES = {
    "china": ("accelerated-domains.china.conf", "china.txt", 50_000),
    "apple-china": ("apple.china.conf", "apple-china.txt", 50),
}
LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\Z", re.ASCII)
MAX_DOWNLOAD = 20 * 1024 * 1024


def valid_domain(domain: str) -> bool:
    # Punycode labels are accepted. Whitespace, Unicode, wildcards, IPs and
    # malformed DNS names are not valid for the target DOMAIN-SET format.
    if not domain or len(domain) > 253 or domain.endswith("."):
        return False
    if not all(LABEL.fullmatch(label) for label in domain.split(".")):
        return False
    try:
        ipaddress.ip_address(domain)
    except ValueError:
        return True
    return False


def parse_dnsmasq(raw: bytes, source_name: str) -> tuple[list[str], dict]:
    try:
        data = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError(f"{source_name}: upstream is not UTF-8") from exc
    if not data.strip():
        raise ValueError(f"{source_name}: empty upstream data")

    domains: set[str] = set()
    parsed_lines = 0
    for n, original in enumerate(data.splitlines(), 1):
        line = original.strip()
        if not line or line.startswith("#"):
            continue
        if not line.startswith("server=/"):
            raise ValueError(f"{source_name}:{n}: unsupported syntax: {line[:100]}")
        # server=/a.example/b.example/114.114.114.114
        fields = line[len("server=/"):].split("/")
        if len(fields) < 2 or not all(fields):
            raise ValueError(f"{source_name}:{n}: malformed server entry")
        server = fields[-1]
        try:
            ipaddress.ip_address(server)
        except ValueError as exc:
            raise ValueError(f"{source_name}:{n}: expected a DNS server IP: {server[:100]}") from exc
        for item in fields[:-1]:
            name = item.lower()
            if not valid_domain(name):
                raise ValueError(f"{source_name}:{n}: invalid domain: {item[:100]}")
            domains.add("." + name)  # dnsmasq /domain/ means suffix, including apex.
        parsed_lines += 1

    if not domains:
        raise ValueError(f"{source_name}: no domain entries")
    sorted_domains = sorted(domains)
    return sorted_domains, {
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "source_rule_count": parsed_lines,
        "output_count": len(sorted_domains),
    }


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "surge-domain-set-builder/1"})
    with urllib.request.urlopen(request, timeout=30) as response:
        if response.status != 200:
            raise ValueError(f"HTTP {response.status} for {url}")
        content = response.read(MAX_DOWNLOAD + 1)
    if len(content) > MAX_DOWNLOAD:
        raise ValueError(f"Source too large: {url}")
    return content


def render(domains: list[str]) -> bytes:
    # No generation timestamps: identical inputs always produce identical files.
    return ("\n".join(domains) + "\n").encode("utf-8")


def guard_count(name: str, count: int, minimum: int, previous: int | None,
                max_drop: float, max_growth: float) -> None:
    if count < minimum:
        raise ValueError(f"{name}: {count} domains is below minimum {minimum}")
    if previous is not None and previous > 0:
        if count < previous * (1 - max_drop):
            raise ValueError(f"{name}: count dropped from {previous} to {count}; refusing to publish")
        if count > previous * (1 + max_growth):
            raise ValueError(f"{name}: count grew from {previous} to {count}; refusing to publish")


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() == data:
        return
    fd, temp_path = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(data)
        os.replace(temp_path, path)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def build(raw_sources: dict[str, bytes], output_dir: Path,
          minimums: dict[str, int], max_drop: float = .20,
          max_growth: float = .50) -> dict:
    if set(raw_sources) != set(SOURCES):
        raise ValueError("Both source inputs are required")
    previous_report = output_dir / "report.json"
    try:
        previous = json.loads(previous_report.read_text("utf-8")) if previous_report.exists() else {}
    except (ValueError, OSError):
        raise ValueError("Existing report.json is corrupt; refusing to overwrite")

    staged: dict[str, bytes] = {}
    report = {"upstream": "felixonmars/dnsmasq-china-list", "lists": {}}
    for name, (upstream_file, output_file, _) in SOURCES.items():
        domains, metadata = parse_dnsmasq(raw_sources[name], name)
        old = previous.get("lists", {}).get(name, {}).get("output_count")
        guard_count(name, len(domains), minimums[name], old, max_drop, max_growth)
        body = render(domains)
        staged[output_file] = body
        report["lists"][name] = {
            "upstream_file": upstream_file,
            "output_file": output_file,
            **metadata,
            "output_sha256": hashlib.sha256(body).hexdigest(),
        }

    # All parsing and validation happens BEFORE any output is modified.
    for file, body in staged.items():
        atomic_write(output_dir / file, body)
    atomic_write(output_dir / "report.json", (json.dumps(report, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download", action="store_true", help="Download both official upstream files")
    parser.add_argument("--china", type=Path, help="Use local accelerated-domains file")
    parser.add_argument("--apple", type=Path, help="Use local apple.china file")
    parser.add_argument("--output", type=Path, default=Path("domains"))
    parser.add_argument("--min-china", type=int, default=50_000)
    parser.add_argument("--min-apple", type=int, default=50)
    parser.add_argument("--max-drop", type=float, default=.20)
    parser.add_argument("--max-growth", type=float, default=.50)
    args = parser.parse_args()
    if args.download == bool(args.china or args.apple) or (not args.download and not (args.china and args.apple)):
        parser.error("Use --download OR provide both --china and --apple")
    if min(args.min_china, args.min_apple) < 1 or not 0 <= args.max_drop < 1 or args.max_growth < 0:
        parser.error("Invalid validation thresholds")

    raw = (
        {"china": fetch(UPSTREAM + SOURCES["china"][0]),
         "apple-china": fetch(UPSTREAM + SOURCES["apple-china"][0])}
        if args.download else
        {"china": args.china.read_bytes(), "apple-china": args.apple.read_bytes()}
    )
    report = build(raw, args.output,
                   {"china": args.min_china, "apple-china": args.min_apple},
                   args.max_drop, args.max_growth)
    for name, info in report["lists"].items():
        print(f"{name}: {info['output_count']} entries -> {args.output / info['output_file']}")


if __name__ == "__main__":
    main()
