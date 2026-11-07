# DP-468 — Current private rights evidence for EU AVS I-293056

The previous source-specific private permission expired on 2 November 2026.
Use `tools/dp458_real_source_packet.py --refresh-private-rights` explicitly
inside the existing MiniPC runtime EnvironmentFile. This retrieves the exact
official item page and [conditions of use](https://audiovisual.ec.europa.eu/en/conditions-of-use)
over HTTPS with bounded bodies and redirects disabled.

The check requires the original item ID, exact quotation and European
Parliament attribution. It also requires the EU-owned CC BY 4.0 licence
language and the exclusions for private individuals, third-party works and
distortion. Both observed page hashes are bound to the new private receipt.
The append-only registry supersedes the old rights record with a seven-day
expiry. Initial `--apply` likewise requires current official evidence.
Missing/changed conditions yield HOLD and leave the ledger intact.

This procedure only refreshes the already scoped **private** uses.
`EXCERPT_PUBLIC` remains denied. Literal audio alignment, public
quotation rights, the six GDPR decisions, independent 2+1 model reviews,
v3 consumer release/correction and public readback remain separate gates.
