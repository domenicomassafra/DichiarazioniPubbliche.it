# Canonical public mockups

This directory is the maintained visual prototype set for the public product architecture
defined in `docs/35-public-product-architecture-v3.md`.

There are exactly nine permanent mockup families:

| File | Public job |
| --- | --- |
| `home.html` | Explain the product and start universal search. |
| `explore.html` | Search and filter the public record. |
| `statement.html` | Show what was said, the finding, evidence, source context and history. |
| `person.html` | Browse one person's public-statement chronology without a person score. |
| `topic.html` | Read a topic dossier with statements, reviewed traces and source paths. |
| `content.html` | Inspect published statement moments/locators inside one original source. |
| `trace.html` | Follow a reviewed longitudinal relation through time. |
| `method.html` | Explain publication, evidence, uncertainty, corrections and provenance. |
| `utility.html` | Shared document grammar for Corrections, Data & API and Project. |

`Contribute` is deliberately excluded until the public-intake abuse and legal gates are
ready. Empty/error/correction states belong to the relevant template rather than becoming
new page families.

## Regeneration

Run:

```bash
python3 prototypes/final-hybrid/build.py
```

The HTML files are generated from `build.py`. PNG files are frozen 1440×1200 visual
receipts of the same pages and may be regenerated with a local headless browser when the
HTML changes materially.

Legacy names (`fact-check`, `record`, `content-audit`, `compare`) are intentionally not
part of the canonical set after the v3 architecture cutover.
