# DP-315 — private denial coverage and authentic-source boundary

`evaluate_denial` accepts an optional `DenialCoverageManifest`. The manifest
binds the denial/person/scope/time window, source-collection digest, review
reference, observation timestamp, and individually identified search attempts
to the versioned result receipt. Attempts are sorted for deterministic replay;
duplicate IDs, future-dated attempts relative to the observation, malformed
hashes, and mismatched subject/scope are rejected. Missing or changed source
revisions receive `SEARCH_ATTEMPTS_STALE_OR_UNKNOWN_HOLD`. A changed collection, attempt,
or review event changes the receipt. No search result can establish a universal
absence: without a verified prior counterexample the factual status remains
`CHECKED_INSUFFICIENT_EVIDENCE` and the relation remains `PRIVATE_HOLD`.

The manifest's review reference is **caller-provided metadata**, not independent
authorization, source authenticity, complete recall, or permission to publish.
`SEARCH_ATTEMPTS_RECORDED_HOLD` reports a bounded inventory only. A missing
manifest is `NO_SEARCH_MANIFEST_HOLD`. The historical private metadata-only
evaluator path is still provisional; actual acceptance requires independently
authenticated prior *and later* utterances, original quote spans, attributable
speakers, and authorized rights for the intended operation.

## Authentic negative readback (25 October 2026)

The existing read-only consumer command on MiniPC:

```sh
cd /home/udodo/src/DichiarazioniPubbliche.it
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=poc python3 tools/dp331_senato_private_speech_readback.py --database-url dichiarazioni_pubbliche --ordinal 19
```

Observed `PRIVATE_HOLD`: primary Senato [Akoma Ntoso document at pinned
commit](https://github.com/SenatoDellaRepubblica/AkomaNtosoBulkData/blob/bfac144eb5c54820971bc1020fece11aae56ec90/Leg19/Atto00055187/resaula/01457617-ra.akn.xml),
Git blob `bec30c067a1a79e8b377af483cfc4bfb44d13896`, capture SHA-256
`1cb2b5fc3cbc96701e52f06c34c3ae3cd494eb622aa3f124fb1a93a223e27476`,
Capture ID `capture:a2849fbebd69aa54acc01a259db47379bc9587ec6c67f09720db3dca0768fb4a`.
`speech:19` returned `QUESTION`, `NON_COMMITTAL`, `attribution_approved=false`;
turn completeness was unverified. The source's rights record
`private-rights:d87a53e8372a1102567dc2307af841703db3922860595bad9f4f741bc724cb7b`
was `CLEARED` for the five explicitly permitted private uses only, including
`PARSE_TEXT` and `STORE_BODY`, expiring 23 November 2026. Rights and provenance
trace back to [#330](https://github.com/domenicomassafra/DichiarazioniPubbliche.it/issues/330)
and [#331](https://github.com/domenicomassafra/DichiarazioniPubbliche.it/issues/331).
The underlying repository states CC BY 4.0; this does not provide independent
segment-level speaker approval or `EXTRACT_CANDIDATES`/`PUBLISH` rights.

The observation cannot serve as either an endorsed prior X or the later
"I never said X" denial. No such authenticated pair or coverage search attempts
were invented for the live corpus. The installed public-v2 consumer was `active`
and health `ok`, but its projection was `DRAFT`, `dossier_count=0`. The original
AC-315.1–.5 are therefore **not** accepted by this private coverage contract.
Real source pairs and downstream invalidation/linked public Statement, Finding,
and relation readback still require a separately authorized, reviewed pilot.
