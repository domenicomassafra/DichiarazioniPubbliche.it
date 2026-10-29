# DP-443 real-source pilot: preparation and NO-GO proposal (2026-10-25)

Status: **PREPARER EVIDENCE / NO-GO PROPOSED**. This is not a signed
pilot manifest, independent approval, public release, or complete live
source-to-reader-and-correction exercise. Do not infer approval to scale.

## Authentic source candidates

**Camera parliamentary record (private HOLD).** Original official transcript:
https://documenti.camera.it/leg19/resoconti/assemblea/html/sed0607/stenografico.htm,
sitting 2026-02-03, paragraph iv.289, officially attributed to Vittoria Baldino
(speaker camera:persona:307435). Source HTML SHA-256:
2ab7a0739d6ffc766b45526023ab4bd878c0e996fa90aa7d6dec6a3e0cc7de6f.
Exact 162-character quote SHA-256:
3e42b9c82bfbf854f1efa18cec52fb33b3293d7971ffa3f0dc0bbea5d5d8dbdb.
The live official-source checker validated the speaker-link context, paragraph,
exact text and private Capture/Passage/Candidate roundtrip; result:
OWNER_ACCEPTANCE_PRIVATE_PILOT_VERIFIED. Capture QUARANTINED,
Candidate HELD, rights UNKNOWN, no verified video excerpt timecode,
no production DB change and published=false. This source is not cleared
for a public quotation merely because it is publicly accessible.

**Senato Akoma Ntoso (licensed private Capture).** Official repository:
https://github.com/SenatoDellaRepubblica/AkomaNtosoBulkData,
pinned commit bfac144eb5c54820971bc1020fece11aae56ec90;
blob bec30c067a1a79e8b377af483cfc4bfb44d13896.
Official README and LICENSE CC BY 4.0 SHA-256 values:
cd01c53874c63df20d18ea151b3e5528af329dbc64ee573be4d480368f5a34dc
and 9ba9550ad48438d0836ddab3da480b3b69ffa0aac7b7878b5a0039e7ab429411.
Pinned XML SHA-256:
1cb2b5fc3cbc96701e52f06c34c3ae3cd494eb622aa3f124fb1a93a223e27476.
MiniPC private Capture ID:
capture:a2849fbebd69aa54acc01a259db47379bc9587ec6c67f09720db3dca0768fb4a.
Persisted private rights/capture proof is in
https://github.com/domenicomassafra/DichiarazioniPubbliche.it/issues/330
and speech probes in DP-331/357. The existing recorded uses authorize
specific private capture/analysis, not a public Statement publication
or an accepted reader correction. Attribution, official immutable
source version and rights scope must remain bound to the chosen record.

## Mac Studio and MiniPC observation (2026-10-25)

Git worktree base at the start of inspection:
dc7bb91e57769480995548c3a969ea00318b8c23 (origin/main).
All local tests were admitted by the ControlCenter workload launcher.

- Focused DP-443 readiness unittest: **14 tests OK**, including negative
  HOLD. A structurally complete synthetic evidence packet still returns NO-GO.
- DP-435/436/437/438/439/518 selected tests: **74 tests OK**. These are
  isolated seams, not an authentic published source or corrected live reader.
- Live Camera checker: hashes and held candidate as documented above;
  production_db_changed=false and published=false.
- MiniPC approved-empty reader checker: PASS_APPROVED_EMPTY_ONLY;
  6 canonical routes HTTP 200, 8 demo/private routes HTTP 404,
  4 API lists empty, fingerprint
  501348d9638ee3c4d929205d2e6dca7eb2c8a552ac006dee837ea032a739ae7a.
- MiniPC web service active; /api/v1/health status=ok,
  contract_status=DRAFT, public-v2, dossier_count=0, same fingerprint.
- Launch preflight (--expect-no-go): **NO-GO, 53 blockers**, including
  16 outstanding Q-306 legal decisions and 6 blocked privacy purposes.
  This figure is a preflight count, not a count of open GitHub issues.
- Launch set checker: candidate_status=BLOCKED, held=3, included=0,
  publication_authorized=false, snapshot=NOT_BUILT.

Reproduce on Mac Studio in this repository using the prescribed
python3 ~/.local/share/controlcenter/resource-guard/workload_launcher.py build --
prefix before each Python test/check command:
- env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=poc python3 -m unittest tests.test_dp435_public_statement_seam tests.test_dp436_public_v3_consumer_parity tests.test_dp437_public_opinion_api tests.test_dp438_public_person tests.test_dp439_person_topic_v3 tests.test_dp518_withdrawal_next -q
- env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=poc python3 tools/verify_t4_p02_owner_acceptance.py
- env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=poc python3 tools/check_dp422_live_readback.py --ssh-target minipc --expected-fingerprint 501348d9638ee3c4d929205d2e6dca7eb2c8a552ac006dee837ea032a739ae7a
- env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=poc python3 tools/check_launch_preflight.py --expect-no-go
- env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=poc python3 tools/check_launch_set_manifest.py

The isolated, always-`NO-GO` DP-443 packet validator and its synthetic test
were retired by #545 on 2026-10-29. The 14 passing tests recorded above are
historical; the remaining commands exercise the actual source and reader gates.

## Original AC and disposition

| AC | Verifiable outcome and missing evidence |
| --- | --- |
| 443.1 | HOLD: real source versions identified; no frozen signed manifest binding current public-use rights, expected positive/negative paths and independent signers. |
| 443.2 | HOLD: real private Capture exists; installed MiniPC reader has zero approved public Statements, so source to API/HTML/search/RDF was not witnessed. |
| 443.3 | HOLD: no authentic fact-check with evidenced conclusion/abstention paired with a separately eligible public opinion and attribution holds. |
| 443.4 | HOLD: no publicly approved Person by Topic intersection and dated, source-linked synthesis for an authentic case. |
| 443.5 | HOLD: tests cover isolated correction paths but no live same-record before/correction/withdrawal fingerprints across HTML, API, search, linked data, cache and rollback. |
| 443.6 | HOLD: no completed automated provenance/rights/privacy review with independent agent agreement under #413, accepted gold, live costs/rollback or functioning public privacy/correction contact. |
| 443.7 | NO-GO proposed by preparer. Independent source and consumer verification are absent. Historical scaling is not authorized. |

## Completing the pilot

Reuse the existing guarded Capture and rights registry, private candidate
pipeline, opt-in Statement v3 reader and correction/release mechanisms.
Resolve authentic public Statement acceptance (#78 and #345), Person
readback (#346), transactional withdrawal and last-reader cache/readback
(#64 and #353), automated provenance/rights/privacy/review controls (#413),
operational contacts (#96), and actual rehearsal (#98). Verify one
source-specific public-use basis with cited evidence and an independent
second-model agent, then observe three live projection fingerprints before
correction, after correction and after withdrawal on the MiniPC.
The latest owner decision in
https://github.com/domenicomassafra/DichiarazioniPubbliche.it/issues/300
and the implementation ticket
https://github.com/domenicomassafra/DichiarazioniPubbliche.it/issues/413
require no person in acceptance, review or publication; the independent
agent review and subsequent sample audit are automatic. Personal contact
setup or credential actions alone belong in issue #300.

Keep the approved-empty production projection until this entire sequence
passes. This packet publishes no Statement, performs no provider dispatch
or bulk ingestion, and makes no live DB or consumer change. DP-443 remains
OPEN until all seven original acceptance criteria are observed.
