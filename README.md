# dnsmasq-china-list → Surge DOMAIN-SET

Surge DOMAIN-SET files generated from the China and Apple China DNS lists in [felixonmars/dnsmasq-china-list](https://github.com/felixonmars/dnsmasq-china-list).

The converter extracts domain suffixes from dnsmasq rules. DNS servers are configured separately in Surge; upstream server IP addresses are not included in the generated lists.

## Outputs

| Output | Source |
| --- | --- |
| [domains/china.txt](domains/china.txt) | `accelerated-domains.china.conf` |
| [domains/apple-china.txt](domains/apple-china.txt) | `apple.china.conf` |
| [domains/report.json](domains/report.json) | Source/output SHA-256 checksums and entry counts |

## Surge configuration

The following entries configure DNS servers for the domain lists in Surge's `[Host]` section. A configuration example is also available in [domains/surge-remote.conf](domains/surge-remote.conf).

```ini
[Host]
DOMAIN-SET:https://raw.githubusercontent.com/oooqqqa/domain-set/main/domains/apple-china.txt = server:https://223.5.5.5/dns-query
DOMAIN-SET:https://raw.githubusercontent.com/oooqqqa/domain-set/main/domains/china.txt = server:https://223.5.5.5/dns-query
```

The example uses `https://223.5.5.5/dns-query` as the DNS server. The Apple China entry is optional.

## Conversion

- Converts `server=/example.com/114.114.114.114` to `.example.com`, covering the domain and its subdomains.
- Accepts dnsmasq `server=/.../IP` rules, blank lines, and comment lines. Unsupported syntax or invalid domains cause the build to fail.
- Lowercases, deduplicates, and sorts domain entries while preserving Punycode labels.
- Parses and validates both source lists before modifying output files.
- Checks minimum entry counts and changes relative to the previous report.
- Records source and output SHA-256 checksums in `report.json`. Identical inputs produce identical outputs, without generation timestamps.

## Local usage

Requires Python 3.9 or later and uses only the standard library.

Download and convert both upstream lists:

```sh
python3 convert.py --download
```

Convert local source files:

```sh
python3 convert.py --china /path/to/accelerated-domains.china.conf --apple /path/to/apple.china.conf
```

| Option | Default | Description |
| --- | --- | --- |
| `--output` | `domains` | Output directory |
| `--min-china` | `50000` | Minimum China list entry count |
| `--min-apple` | `50` | Minimum Apple China list entry count |
| `--max-drop` | `0.20` | Maximum proportional decrease from the previous count |
| `--max-growth` | `0.50` | Maximum proportional increase from the previous count |

Change limits apply when the output directory contains a previous report with a positive entry count for the list.

Run the test suite:

```sh
python3 -m unittest -v
```

## Automated updates

The [update workflow](.github/workflows/update.yml) is scheduled for Mondays at 02:27 UTC (10:27 Beijing time). It also supports manual runs and runs on pushes to `main` that modify the converter, tests, or workflow.

Each run executes the tests, downloads and validates both upstream lists, and commits changed outputs to the repository's default branch. The workflow requests `contents: write` permission to publish updates.

## Source and license

Domain data is sourced from [felixonmars/dnsmasq-china-list](https://github.com/felixonmars/dnsmasq-china-list); see the [upstream license](https://github.com/felixonmars/dnsmasq-china-list/blob/master/LICENSE).

The conversion code is licensed under [GPL-3.0](LICENSE).
