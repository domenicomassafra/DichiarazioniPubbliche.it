# Security Policy

## Supported versions

The project is pre-1.0. Security fixes target the current `main` branch unless a release
is explicitly designated as supported.

## Reporting a vulnerability

Do not open a public issue for a vulnerability that could expose credentials, private
operational data, raw transcripts/evidence, production infrastructure, or a publication
gate bypass.

Until a public security contact is configured, report security issues privately to the
repository owner through the same private channel by which you received access. A public
security email will be added before public launch.

Please include:

- affected revision/version;
- reproduction steps or proof of concept;
- expected impact;
- whether production data or publication integrity may be affected;
- suggested mitigation if known.

## High-priority security classes

- bypass of finding/speaker/evidence/reply/correction review gates;
- public projection leaking raw/private content;
- SSRF, unsafe redirect/DNS handling, or unbounded remote fetch;
- arbitrary file read/write/delete through retention or cache paths;
- SQL injection or unsafe migration behavior;
- forged provider/provenance receipts;
- replay that silently widens a claim's provenance;
- credential or production-database exposure;
- ability for unauthenticated users to mutate review/publication state.

## Security design principles

- fail closed;
- least public data necessary;
- append-only decision history;
- bounded network/file operations;
- no secrets in Git;
- explicit trust boundaries between retrieval, review, verification, and publication;
- deterministic checks around model output.

See `ARCHITECTURE.md` and `docs/29-data-provenance-security-hardening-v2.md` for current
implemented boundaries.
