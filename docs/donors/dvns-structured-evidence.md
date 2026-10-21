# DP-234 structured evidence — reuse and provenance (2026-10-21)

The Apache-2.0 owner implementation reuses its own provider-neutral
`dvns_structured_evidence`, `structured_evidence`, and DP-215 `dvns_source_suitability`
seams. All input fixtures are synthetic. **No donor source or runtime is copied.**

- DVNS sibling: https://github.com/Italian-Builders-Org/DoveVannoINostriSoldi/tree/569f8e80d6ba05c6a875781f43e53131b39ec58a ; HEAD `569f8e80d6ba05c6a875781f43e53131b39ec58a` (2026-10-20). LICENSE blob `1eb486300a202252221471cd61ecb296c147b05b` says **AGPL-3.0-or-later** (GitHub metadata: `NOASSERTION`). MCP read-only `list_datasets/query_dataset`: https://github.com/Italian-Builders-Org/DoveVannoINostriSoldi/blob/569f8e80d6ba05c6a875781f43e53131b39ec58a/docs/MCP.md . **Discard upstream code import**; any eventual approved API/export needs its own schema and rights decision.
- Frictionless Data Package specification: https://github.com/frictionlessdata/datapackage/tree/da3526c4ed19563620d6a5e33ea55db6234cc411 ; commit `da3526c4ed19563620d6a5e33ea55db6234cc411` (2026-08-25), **Unlicense**. Frictionless Python: https://github.com/frictionlessdata/frictionless-py/tree/c08fa29cb0708427ae65bb689ded8e2691078a82 ; commit `c08fa29cb0708427ae65bb689ded8e2691078a82` (2026-10-15), **MIT**. Reuse the *design concept* of versioned data schema; do not introduce dependency for this narrow fix.
- Python jsonschema: https://github.com/python-jsonschema/jsonschema/tree/c497561ea0a95f5aac09cd63d15eb1420eb7bbec ; commit `c497561ea0a95f5aac09cd63d15eb1420eb7bbec` (2026-10-07), **MIT**. The existing stdlib schema/version checks suffice; no new package.

The bridge holds records and profile bindings with `REVOKED`, `DENIED` or
`EXPIRED` rights, exposing exact `DVNS_RIGHTS_*` or `DP215_PROFILE_RIGHTS_*`
reasons without performing metric/scope/temporal suitability checks. Original
stable source record IDs and normalized HTTPS provenance remain separately
available; a HELD candidate is never approved Evidence or a publication grant.

**Unresolved external acceptance:** no approved DVNS partner API/export or
permissively licensed shared partner schema, authenticated provider/profile
identity mapping, signed compatible source-specific rights/entitlement record,
reviewer permission, or real-source MiniPC canary. The official Senato metadata
canary covers only that separate source family, held pending rights. No live
DVNS ingest/deployment/publication is authorized by this technical change.
