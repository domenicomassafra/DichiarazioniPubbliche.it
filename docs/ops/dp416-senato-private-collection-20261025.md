# DP-416 — verified private Collection → Passage → held Statement Candidate

Issue: [#71](https://github.com/domenicomassafra/DichiarazioniPubbliche.it/issues/71).
The existing Collection → Capture navigation was delivered in PR #381.
The remaining real-world acceptance checks a **single** attributable
Senato Passage and an unapproved Statement Candidate linked to that Capture.
This is **not** a public excerpt, Claim Candidate, finding, or review approval.

## Source-specific license and permitted private use

The official [Senato Akoma Ntoso dataset](https://github.com/SenatoDellaRepubblica/AkomaNtosoBulkData)
at commit `bfac144eb5c54820971bc1020fece11aae56ec90` supplies
`Leg19/Atto00055187/resaula/01457617-ra.akn.xml`, Git blob SHA-1
`bec30c067a1a79e8b377af483cfc4bfb44d13896` and whole-body
SHA-256 `1cb2b5fc3cbc96701e52f06c34c3ae3cd494eb622aa3f124fb1a93a223e27476`.
At that commit, README.MD SHA-256
`cd01c53874c63df20d18ea151b3e5528af329dbc64ee573be4d480368f5a34dc`
and [LICENSE.MD at the pinned revision](https://github.com/SenatoDellaRepubblica/AkomaNtosoBulkData/blob/bfac144eb5c54820971bc1020fece11aae56ec90/LICENSE.MD) SHA-256
`9ba9550ad48438d0836ddab3da480b3b69ffa0aac7b7878b5a0039e7ab429411`
state [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/legalcode),
allowing adaptation with attribution and the license notice. Attribute the
material to **Senato della Repubblica** and identify the pinned revision.
This source-specific decision supports a **private, bounded, accurately
attributed derivative**; it does not determine third-party privacy, speaker
identity, public exact-quotation clearance, or editorial approval.

The source-use registry's already CURRENT `PARSE_TEXT` right authorizes
reading/parsing the private Capture. The operator must separately record
`EXTRACT_CANDIDATES` in an append-only successor, retaining the same
source/Content/URL subject, receipt, attribution requirement, reviewer
`machine:licence-attestation-v1`, policy version and previous expiry.
Model dispatch uses a different permission,
`OMNIROUTE_MODEL_EXTRACTION_PRIVATE`, **never** added here.
Revoked, expired, superseded, wrongly scoped and ambiguous grants fail
closed on read and before both native writes. The written records remain
`HELD`, with no Person resolution, Claim Candidate or public projection.

## Operator and readback

Read-only preflight on the MiniPC:

```sh
PGDATABASE=dichiarazioni_pubbliche PYTHONPATH=poc:tools python3 tools/dp416_senato_collection_pilot.py --database-url dichiarazioni_pubbliche
```

After source and right review, one explicit scoped operation (with a private
database backup taken before writing):

```sh
PGDATABASE=dichiarazioni_pubbliche PYTHONPATH=poc:tools python3 tools/dp416_senato_collection_pilot.py --database-url dichiarazioni_pubbliche --apply
```

The adapter first checks the official pinned license and byte-identical
persisted Capture. It re-derives the official stenographic Passage/Statement
contracts, validates an exact speaker pointer and hash-bound text-position selector,
rechecks current rights, then uses the existing Passage and Statement
Candidate writers. Deterministic IDs and native `INSERTED/EXISTING`
responses support replay. The SQL readback requires one linked HELD
Candidate with no accepted Person attribution.

The current case is bounded to **one** speaker-local source statement:
`statement-candidate:02a3e35af85163740ebc6dd0b37aa01681c1862954daa5b9cbbc2ff79ee48cf1`
on Passage
`passage:48733afb58735720304507820b22110eb18110d6ba91b52954706d3e38c8706a`.
These names are computed from the exact pinned source; no synthetic candidate
or provider inference is persisted. An absent or separately held Claim Candidate
remains a visible HOLD. The read-only Studio navigation is a bounded snapshot,
not a new publication authority.

**Operational limit:** separate SQL writes recheck current source use between
steps but cannot serialize against a concurrent, uncoordinated append-only
revocation. An interrupted run may leave an orphaned held Passage; rerun
reuses its deterministic ID. This pilot is not a general-purpose ingestion
pipeline, a legal precedent for another source, or a promise of public access.
