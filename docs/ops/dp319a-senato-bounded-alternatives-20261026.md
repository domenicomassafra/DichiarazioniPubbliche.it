# DP-319A — Authentic Senato HOLD: bounded alternative coverage (2026-10-26)

This is a **private, source-linked incomplete investigation** of a historical
record. It does not resolve whether the historical document establishes a
current state, endorse a factual claim, or authorize publication. Issue #439
extends the existing DP-319 private planner and the real-source CLI shipped in
[#401](https://github.com/domenicomassafra/DichiarazioniPubbliche.it/pull/401).

## Identified original and use-specific rights

- **Official origin:** Senato della Repubblica,
  [`Leg19/Atto00055187/resaula/01457617-ra.akn.xml`](https://github.com/SenatoDellaRepubblica/AkomaNtosoBulkData/blob/bfac144eb5c54820971bc1020fece11aae56ec90/Leg19/Atto00055187/resaula/01457617-ra.akn.xml),
  repository `SenatoDellaRepubblica/AkomaNtosoBulkData`, immutable commit
  `bfac144eb5c54820971bc1020fece11aae56ec90` (commit dated
  **2026-05-24T14:52:05Z**). The XML metadata gives document date
  **2025-05-29**. The already stored Capture body's SHA-256 is
  `1cb2b5fc3cbc96701e52f06c34c3ae3cd494eb622aa3f124fb1a93a223e27476`;
  the source is pinned by official commit and Git blob ID and checked against
  this exact body hash by `tools/dp319_senato_private_investigation.py`.
- **Licence evidence:** pinned official
  [README](https://github.com/SenatoDellaRepubblica/AkomaNtosoBulkData/blob/bfac144eb5c54820971bc1020fece11aae56ec90/README.MD)
  and [LICENSE](https://github.com/SenatoDellaRepubblica/AkomaNtosoBulkData/blob/bfac144eb5c54820971bc1020fece11aae56ec90/LICENSE.MD)
  declare **CC BY 4.0**, attribution **Senato della Repubblica**. This licence
  is source-specific; the separate `dati.senato.it` portal must not supply
  assumptions about this repository. See
  [`dp326-studio-discovery-metadata-rights-20261024.md`](dp326-studio-discovery-metadata-rights-20261024.md)
  for recorded pinned licence hashes and revocation behavior.
- **Actual private permission:** the previously verified MiniPC current rights
  record `private-rights:d87a53e8372a1102567dc2307af841703db3922860595bad9f4f741bc724cb7b`
  permits **PARSE_TEXT** on the pinned content through **2026-11-23**, subject
  to repeated current-rights, expiry and hash checks. It does **not** grant
  arbitrary searches, other sources, quotation publication or fact checking.
- **Privacy:** a public official institutional record. Only origin identifiers,
  hashes, dates and bounded search outcomes appear here; no private persons,
  personal identifiers or extracted speech is exposed.

## Four alternatives, explicit refusal and stopping envelope

The typed blocker is `SOURCE_VERSION`: *Does the pinned historical Senato
record prove present status?* One attempt was admitted against the existing
authorised official Capture. There is **no authorized assignment** for the
other three alternatives; zero capacity means no queries were issued. They
remain distinct `NOT_CHECKED` entries in the planner and consumer readback.

| Coverage lane | Actionable source/question | Permitted attempt, limit and stop | Observed state |
| --- | --- | --- | --- |
| `ORIGINAL` | Confirm original rather than dependent repost of the Senato document | No independently registered original-media/primary-source assignment or additional use grant; **0** authorized queries, **0** results, **USD 0**; stop `INVESTIGATION_NO_AUTHORIZED_ASSIGNMENT` | `NOT_CHECKED` |
| `FULL_CONTEXT` | Does the whole record and its history constrain the meaning or temporal validity of the pinned document? | No independently authorized archive/history adapter or body-use grant for a different version; **0** queries/results, **USD 0**; stop `INVESTIGATION_NO_AUTHORIZED_ASSIGNMENT` | `NOT_CHECKED` |
| `OFFICIAL` | Does this exact official 2025-05-29 document establish a present status? | Existing pinned Senato Capture, `PARSE_TEXT` only; **1** query, **1** result, **1** per host, **USD 0**, recorded source date 2025-05-29; stop `ONE_PINNED_OFFICIAL_RECORD_OR_HOLD` and global `INVESTIGATION_ATTEMPT_CAP` | `CHECKED_INSUFFICIENT`, actual terminal observation `SOURCE_INCONCLUSIVE` |
| `INDEPENDENT` | Is there truly independent, rights-permitted corroboration of the current-status proposition? | No approved independent reporting adapter, lineage proof or use permission for another publisher; **0** authorized queries/results, **USD 0**; stop `INVESTIGATION_NO_AUTHORIZED_ASSIGNMENT` | `NOT_CHECKED` |

No extra source was queried or counted as negative evidence. The official
GitHub file page, raw endpoint, repository tree entry and any copy of those
same bytes all derive from **one Senato origin**; they are **mirrors**, not
independent corroboration. The planner now counts only distinct lineage IDs
outside the original/official baseline for an independently reviewed
alternative candidate. A separate outlet needs its own real source, bounded
assignment, current rights and independently verified lineage before it can
be counted. No synthetic publisher or invented reviewer is used here.

The selected plan's `max_attempts=1` was exhausted for **that official lane**;
it is not a completed four-lane investigation. The machine receipt preserves
`decision=EXHAUSTED`, while the bounded case readback reports
`status=PRIVATE_PARTIAL_HOLD`, the four per-lane states above,
`source_permissions_for_other_lanes=NOT_EVALUATED`, and residual reason
`HISTORICAL_OFFICIAL_RECORD_DOES_NOT_PROVE_CURRENT_STATUS`. Absence of a
new result does not disprove the proposition.

## Replayed consumer evidence and limitations

On MiniPC, read-only inspection on **2026-10-26** of the durable private
`/home/udodo/.local/state/dichiarazioni-pubbliche/dp319-334-senato-ledger.sqlite`
returned `PRAGMA integrity_check=ok`, **1** source epoch, **1** plan scope,
and **2** append-only events (`RESERVED=1`, `COMPLETED=1`). Completed attempt
`investigation-attempt:24a23475463ce9ffc70356ca5090eb34c02f9c84bfd95c1db435945c4d76fac6`
was `OFFICIAL_STRUCTURED`, `SOURCE_INCONCLUSIVE`, `spent_usd=0`,
`review_event_id=null`, `lineage_id=null`. This record is the **same**
existing #334/#401 attempt; new coverage is a pure projection of its immutable
receipts, not a new cost-bearing action. Previous process-restart CLI replay
was documented in PR #401 at ledger revision **2** with the same attempt ID.

A temporary Mac Studio copy of that exact ledger matched the consumer SHA-256
`d52f8a84ca0401ac0341663a0fff36e8d73ad4ba2ed576e9cc229ef11c7294eb`.
The **new** `InvestigationSQLiteStore.resume(..., source_revision=1)` code,
under the resource guard, read the real copy at revision **2** and returned:
`OFFICIAL=CHECKED_INSUFFICIENT` (`1/1` permitted attempt),
`ORIGINAL=NOT_CHECKED`, `FULL_CONTEXT=NOT_CHECKED`,
`INDEPENDENT=NOT_CHECKED` (`0` permitted attempts each), and
`publication_authority=false`, `dispatch_authorized=false`. No ledger event
or source epoch was added.

Consumer service `dichiarazioni-pubbliche-web.service` was `active` and
`127.0.0.1:18090/api/v1/health` returned `status=ok`, `DRAFT` projection,
`dossier_count=0`. The new coverage readback is validated on Mac Studio
against the existing public CLI seam; it requires the new PR's reviewed
installation before it can be observed from the installed CLI on MiniPC.
No provider was called, no alternative-rights grant was minted, and neither
the ledger nor the public projection was modified. Actual provider-billing
reconciliation and a canonical PostgreSQL Coverage Need closure remain
**unproved**; `publication_authority=false`,
`downstream_queue_closed=false`.
