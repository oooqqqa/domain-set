# dnsmasq-china-list → Surge DOMAIN-SET

Convert the [felixonmars/dnsmasq-china-list](https://github.com/felixonmars/dnsmasq-china-list) China and Apple China DNS lists into native Surge DOMAIN-SET files. This repository only builds domain lists; Surge itself handles DNS matching and resolution.

## Outputs

| Output | Source |
| --- | --- |
| [domains/china.txt](domains/china.txt) | `accelerated-domains.china.conf` |
| [domains/apple-china.txt](domains/apple-china.txt) | `apple.china.conf` |
| [domains/report.json](domains/report.json) | Source/output SHA-256 checksums and entry counts |

The generated files first appear after a successful GitHub Actions run.

## Surge configuration

Merge these lines into your existing `[Host]` section (or see [surge-remote.conf](domains/surge-remote.conf)):

```ini
[Host]
DOMAIN-SET:https://raw.githubusercontent.com/oooqqqa/domain-set/main/domains/apple-china.txt = server:https://223.5.5.5/dns-query
DOMAIN-SET:https://raw.githubusercontent.com/oooqqqa/domain-set/main/domains/china.txt = server:https://223.5.5.5/dns-query
```

The DNS addresses are examples, and the original dnsmasq server IPs are **not** carried into the output. Surge uses the first matching `[Host]` entry, so place more-specific overrides first. Apple's mainland CDN routing is optional because it can be problematic with some ISPs.

## Conversion and safety

- Converts `server=/example.com/114.114.114.114` to `.example.com` (apex **and** subdomains).
- Parses only the expected dnsmasq `server=/.../IP` syntax; invalid input fails rather than silently dropping rules.
- Deduplicates, lowercases, sorts, and preserves Punycode labels.
- Downloads and validates **both** sources before writing, with minimum size, shrink, and growth safeguards.
- Writes deterministic files plus SHA-256 report; unchanged data produces no output changes.

## Local usage

Python 3.9+; no third-party packages required:

```sh
python3 -m unittest -v
python3 convert.py --download
```

Or use downloaded files:

```sh
python3 convert.py --china /path/to/accelerated-domains.china.conf --apple /path/to/apple.china.conf
```

Output goes to `domains/` by default; `--output`, `--min-china`, `--min-apple`, `--max-drop`, `--max-growth` allow controlled adjustments. Do not relax safeguards solely to make a failed update pass.

[GitHub Actions](.github/workflows/update.yml) checks updates every Monday at 10:27 Beijing time, and supports manual triggers. The repository must permit Actions to write contents in **Settings → Actions → General → Workflow permissions**.

## Source and license

Upstream: [felixonmars/dnsmasq-china-list](https://github.com/felixonmars/dnsmasq-china-list), licensed under [WTFPL v2](https://github.com/felixonmars/dnsmasq-china-list/blob/master/LICENSE). Conversion code: [GPL-3.0](LICENSE), matching [oooqqqa/rule-set](https://github.com/oooqqqa/rule-set).