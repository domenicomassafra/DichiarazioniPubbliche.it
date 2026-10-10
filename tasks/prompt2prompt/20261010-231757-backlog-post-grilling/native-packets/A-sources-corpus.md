# Native packet A — Sources, acquisition, text, corpus, Studio

Status: INTEGRATION PROPOSAL — planning only, 2026-10-10. Owner: native worker A. The prime alone assigns final DP numbers, writes canonical tickets/PLAN, checks dependencies and commits. This packet has no runtime authority; **no source was acquired, model called, code changed or approval issued in this task**. Every proposed AC below is **unchecked**.

## Decision anchors and coverage

Owner decisions: Q15–Q20 and R04/R05/R07/R09/R10/R11/R23/R26/R27/R33, plus R06/R08/R21/R22/R25/R28 where A produces inputs for B/C/D. The public declaration must contain the source's **exact words**, never an extraction paraphrase; an Italian translation and a separate summary are different representations. A record of someone **quoting** a third person is not an endorsed position. For procedural material an official document's words are distinct from a witness's reported allegation and from a judicially established fact. A source's availability, public-official provenance or repository license is not a project use permit; acquisition/storage, transformation/translation, public quotation, media/embed and retention need separately scoped dispositions. Missing rights must cause a precise private hold and investigation, never a made-up publication permit or a paraphrase masquerading as the declaration. Speaker identity remains non-biometric; when uncertain, attribution remains unapproved. No full human textual editor exists; the future automated path must be benchmarked and authority-governed by B. This task remains strictly planning.

Existing system, not a blank-slate build: `source_adapters.py`, `source_watcher.py`, `source_intelligence.py`, `rights_registry.py`, `private_capture_batch.py`, `capture_pipeline.py`, `corpus_repository.py`, `corpus_retention.py`, `private_candidate_batch.py`, `candidate_matching.py`, `original_source_resolver.py`, `source_revalidation.py`, `source_span_review.py`, `wording_contract.py`, `asr_router.py`, `remote_asr.py`, `parliamentary_official_adapter.py`, `senato_akoma_stenographic.py`, `senato_akoma_corpus_handoff.py`, `studio_operator_queues.py`, `studio_discovery_inbox_workflow.py`, `studio_candidate_review.py`, `studio_capture_inspector.py`, `studio_local_api.py`. Canonical `PassageRecord` has `TEXT_POSITION`, `PAGE_RANGE`, `MEDIA_SEGMENT_REF` and `language`; the current operator `private_candidate_batch` already supports 1–16 passages, but serial execution is not proof of cross-person correctness/throughput. `capture_pipeline.capture_content` has rights-guard hooks; `wording_contract.assess_translation` flags unsupported language risk and currently requires `human_reviewed` to reach its highest state: a future machine-assurance policy is B's responsibility, not permission to falsify this field. Corpus and operational information are private by default.

**Coverage routing:** R04 → A-NEW-05 (A multilingual text/derivation) + B's semantic assurance + C's public original/translation; R05 → A-NEW-03 and DP-419; R07 → A-NEW-06/DP-233 with B's identity/speech-act guard; R09 → A-NEW-04 and DP-204/208/233; R10 → A-NEW-03/09/10 and DP-209/210/214; R11 → A-NEW-06/08 and DP-211/212/117/418 with B's new authority; R23 → A-NEW-07 and DP-225/213, B owns insufficiency/verification; R26 → A-NEW-06; R27 → A-NEW-09 plus A-NEW-05/04, D owns scheduled bulk; R33 → A-NEW-10 with D owning budgets/timers. A-NEW-01 is the **bounded source-side pilot** on the way to the coordinator's full integrated first reader path (R28), not an alternative mission.

## All 13 pending primary tickets — disposition and preserved proof

For the matrix, "proposed status" is for canonical integration, not an immediate state mutation. All original AC remain assigned to their own ticket until proven. A checked historical AC stays checked only for its original scoped contract.

| Existing ID | Before → proposed | Preserved AC / evidence | Delta and specific remaining proof | Phase; hard / soft prerequisites; future owner |
|---|---|---|---|---|
| **DP-201** | BLOCKED → **BLOCKED** | Original five unnumbered bullets: official OmniRoute artifact, recorded route/model, meaningful schema response, persisted cost receipt, no unofficial fallback. No passing live receipt observed. | Assign stable AC-201.1..5 without checking them; test a *meaningful* constrained request through the governed official route, persisted capability + provider-cost/usage receipt, failure blocked. Do not conflate temporary plentiful GPT-6 Codex/ChatGPT-web entitlement with this route/API. | Phase 1 provider branch; hard official route/capability; soft D quota classification; pipeline/provider owner. |
| **DP-202** | BLOCKED → **BLOCKED** | Existing bullets: exactly one parent first, Giuliani audited gold, errors/latency/tokens/cost, threshold preregistration, MiniPC proof. | Number old AC without altering intent. Freeze sample and threshold before canary; produce one-parent source→canonical candidates→comparison readback, rejected hallucinated quotes and attribution metrics. DP-207's deterministic DONE does not prove this live variant. | Phase 1; hard DP-201; soft B benchmark design and D cost receipt; extraction owner. |
| **DP-203** | BLOCKED → **BLOCKED** | Existing bullets: bounded concurrency, daily/source/job breakers, idempotent replay, outage blocked, before/after queue receipt. | Tie the fanout to controlled *eligible* parents/candidate provenance, provider failure and revocation. Never materialize child jobs on unavailable capability. Preserve pre/post actual queue and cost counts; D owns global EUR budget rules. | Phase 1 then 3; hard DP-202; soft D budgets; queue owner. |
| **DP-204** | BLOCKED → **BLOCKED** | Existing bullets: out-of-Git Groq credential, bounded audio/cap, model/request/cost receipt, disagreement hold, no library fanout, MiniPC. | Define media-language and transcript-variant/source clock/segment hash readback and a negative test where negation/name/number disagreement blocks exact quotation; no model/provider switch or cost invention. Credential + budget + authorized sample remain external. | Phase 1; hard approved Groq credential and source/audio use permit; soft A-NEW-05/B quote guard, D cost; ASR owner. |
| **DP-208** | FUTURE → **FUTURE** | **AC-208.1–.10 all OPEN.** Existing metric-only harness `diarization_benchmark.py` with anonymous `TURN_*`, DER, speaker change, 250 ms collar, inserted clip and sensitive holds is historical local proof, not a live decision. | Keep preregistered ≥10-minute annotated/authorized sample and Giuliani inserted clip (414–434s), comparables, resource/license, MiniPC and GO/GO_BOUNDED/NO_GO. Anonymous speaker turns never grant Person identity or verbatim publication. Current "reviewer" decision must be owned by qualified experiment/governance role, not imagined routine editor. | Phase 3 optional engine decision; hard DP-204, DP-207, approved model/license/reference; soft B false-attribution benchmark. |
| **DP-214** | IN PROGRESS → **IN PROGRESS** | **AC-214.3 checked:** real MiniPC 30 distinct Garlasco claims, 30/30 exact indexed retrieval and linked historical Content; scoped historical-baseline search 13/13. **AC-214.1/.2/.4/.5/.6/.7/.8 OPEN** for the stipulated 100-item real collection. `garlasco_tracer` enforces manifest shape/replay; seed ledger and preflight guard results preserved. | Preserve the **100-item** outcome; do not silently substitute A-NEW-01. Current `research:garlasco` is **PAUSED with 18 included historical Content, rights UNKNOWN for all, 0 real Captures, 0 Passages/Candidates/Discovery Hits**. Need 82 additional reviewed logical items with five families, source/rights profiles, versioned manifest, real immutable captures, duplicates, Coverage Needs, repeat ingestion, PUBLISH unchanged, private/public leak checks. Official/processual material cannot be inferred clear simply because it is reachable. | Phase 3/4 Garlasco campaign after smallest integrated pilot; hard DP-209..213/117 and actual source-family permits, A-NEW-02/03/04 as applicable; soft B rights, D budget; corpus owner. |
| **DP-215** | IN PROGRESS → **IN PROGRESS** | **AC-215.1–.8 checked**, exact source-role/scope/lineage/period/source assessment contracts and MiniPC isolated canary. **AC-215.9 OPEN**. Historical rights facts and source-counts preserved. | Only close AC-215.9 on **real selected DP-214 sources**, each traceable by role, derivative grouping, context scope/time, version and rights, before promotion. A role/authority classification is not an independent public quote grant or factual verdict. Avoid a second "source ranking" system. | Phase 1 ongoing through Garlasco; hard DP-214 real corpus/rights decisions; soft B evidence requirements, A-NEW-02, D launch set. |
| **DP-233** | IN PROGRESS → **IN PROGRESS** | **AC-233.1–.9 checked; AC-233.10 OPEN.** Synthetic Camera/Senato multi-speaker and supersession contracts; independently observed immutable official Senato AKN source: commit `bfac144eb5c54820971bc1020fece11aae56ec90`, XML SHA256 `1cb2b5fc3cbc96701e52f06c34c3ae3cd494eb622aa3f124fb1a93a223e27476`, 393817 bytes. Isolated Mac/MiniPC parser produced 121 speech candidates, 5 speaker/text holds; 104 bounded Passages and 104 **HELD** Statement Candidates (22 total unavailable/oversize). | AC-233.10: a project-*approved* source family with rights + source scope, then bounded real official MiniPC source-family canary and candidate/store readback. Keep XML official speech/written provenance separate from (absent) WebTV timing and unapproved Person mapping. Ensure oversize discourse chunking strategy is reviewed instead of losing 17 candidate segments silently. Dataset notice CC BY 4.0 is scoped to the AKN repo, **not** WebTV footage/ASR/other pages. | Phase 1 source family; hard project-specific source/rights disposition DP-703/305 and A-NEW-02; soft A-NEW-04, B speaker identity; parliamentary adapter owner. |
| **DP-234** | IN PROGRESS → **IN PROGRESS** | **12/14 existing bullets checked**; the two unchecked are real approved DVNS/API/export provider integration and source-specific compatible license/schema/rights. Verified **Senato OpenData RDF** technical read-only probe: 186 assembly-sitting *metadata* records, archive SHA256 `5d6b9e3ca95c51c457d26065374389090ac0ac5ca93cf91ee921db2f3c958b29`; held DP-215 suitability/rights. | Do not treat Senato RDF sitting metadata as the AKN stenographic corpus or proof that DVNS provider itself exists. The technical MiniPC RDF canary is scoped to that official metadata family; retain unmet DVNS external gates. Recheck immutable schema/right mappings for each approved integration. | Phase 2 optional structured evidence; hard actual DVNS contract + compatibility decision; soft DP-215/228 B evidence and D license review; adapter owner. |
| **DP-416** | IN PROGRESS → **IN PROGRESS** | **AC-416.1–.4 OPEN.** Existing loopback read-only MiniPC Collection→18 historical Contents→30 claims; 28 approved-state claim text-provenance hashes are not rights clearance; 0 real Garlasco Capture/Passage/Candidate. | Real persisted Collection→source→capture→exact Passage→Candidate→promoted Claim route; paginated large corpus, no client-side full load; accessible keyboard/color-independent hierarchy; membership changes need reviewed/authorized and safe replay. No unreviewed content in public projection. | Phase 2/3; hard DP-214/414 and persisted source/candidate records, soft A-NEW-08/B promotion; Studio owner. |
| **DP-417** | IN PROGRESS → **IN PROGRESS** | **AC-417.1–.4 OPEN.** Preserve append-only triage ledger; MiniPC migration **already installed** 2026-10-10 with backup/replay and private loopback inbox HTTP 200/401/422. Current persisted Hit rows zero. `/v1/discovery/bulk-preview` handles 1–10 compatible Hits read-only and explicitly `DRY_RUN_ONLY`. | Finish all genuine queue families (changed capture/entity/candidate/coverage/quarantine) with exact provenance, specific unblock actions, real authorized conflict-detecting durable transitions/replay and state-compatible bulk. A private annotation is not reviewer approval. Wire to future unattended machine research path under B authority rather than assuming a human will empty text queues. | Phase 1/2; hard actual discovery/capture/candidate state plus reviewed authority, A-NEW-08; soft B/D; Studio ingest owner. |
| **DP-419** | IN PROGRESS → **IN PROGRESS** | **AC-419.1–.4 OPEN.** Read-only capture version compare/hash/selector diff, purge receipts and content-scoped media Candidate locator; 40/40 focused Mac + isolated MiniPC proof, but live production Garlasco Capture still zero. Historic full 2242-suite had one unrelated concurrent failure, not full green. | Real rights-permitted dual Capture versions in persistent MiniPC and operator/browser readback; body purged still legible from private receipt; exact media player seek to canonical segment/time on approved clip (current locator only metadata), safe bounded excerpt, keyboard/zoom/AT, no secrets. Expose copyable *private* audit locators, not raw body to public. | Phase 2/3; hard DP-210, DP-414, real source captures and preview/media use permits; soft A-NEW-03/B rights; Studio owner. |
| **DP-420** | FUTURE → **FUTURE** | **AC-420.1–.5 OPEN.** No authentic corpus-backed operator usability/Recall@K acceptance; synthetic UI/path evidence is insufficient. | Version **15–25 actual** tasks with frozen search gold/Recall@K, time-to-source, navigation failures, zoom, keyboard, responsive, screen-reader and design usability; record defects separately. Real Garlasco right-cleared source/candidate workflow prerequisites. No assertion of public UI quality or dataset completeness. | Phase 3 acceptance; hard DP-214, DP-415..419 and authorized corpus; soft C UX, B provenance; Studio QA owner. |

**Note on formatting/DP graph:** Old `Depends on` strings include non-DP prose (`M0`, `DP-209..213`, `external ...`). The prime should normalize *hard* `Depends on` to pure DP identifiers/ranges for `check_repository_contract` and place external approvals in a separate boundary field; do not remove those substantive prerequisites. DP-201 and DP-204 need explicit external blockers, not fabricated dependency IDs. DP-208 GO or NO_GO is completion of a benchmark **decision** only, not a grant to adopt a model.

## DONE baseline re-use and proposed deltas

No evidence in the reviewed material warrants reopening these as historically misreported DONE. Create A follow-ups only for additional **2026-10-10 target** behavior:

| DONE contracts | What remains genuinely reusable | New delta owner |
|---|---|---|
| DP-205/206 source polling/adapters; DP-209 discovery; DP-210 immutable capture; DP-211 extraction; DP-212 match; DP-213 Coverage Need | Bounded source workflows, capture/version/selector, candidate ledger and observed cost gates. No bulk or universal language guarantee. | A-NEW-01/02/04/05/06/07/09/10 as below; D owns recurring schedules. |
| DP-101/113/114/115/116/117 | Person/source identity, corpus persistence, derivation, search, controlled promotion. | A-NEW-03, A-NEW-06, A-NEW-08; B owns machine approval and false attribution. |
| DP-207; DP-216/217/218/219/220/221/222/223 | Exact span, transcript tiers, non-biometric attribution, nested quote, context, wording types and adversarial false attribution for old scope. DP-221 DONE's **PARAPHRASE-centered public baseline** is not the new exact-public target. | A-NEW-04/05/06 feed verifiable original to B/C; B owns contextual semantic assurance; C owns public verbatim migration. |
| DP-224/225/227/228 | Material citation, reviewed original-source resolver, supersession, bounded claim-specific research plans. | A-NEW-07 active source investigation, A-NEW-03 precise locators, A-NEW-10 version refresh; B owns hold/verification/correction. |
| DP-231; DP-233/234 in progress | Optional metadata/oEmbed source hints (never source approval); parliamentary AKN textual source is distinct from RDF session metadata. | A-NEW-02/03/04 source-family input; DP-233.10 and DP-234 external AC remain attached to original IDs. |
| DP-305, DP-510/511, DP-414/415 | Qualified rights/excerpt policy, publication holds, version-change revalidation; private Studio modes and search shell. | A-NEW-02 acquisition-time permits + A-NEW-08 machine workflow; B owns legal clearance, autonomous review policy and revocation; C private/public UI boundary; D scheduler. |

## New ticket proposals (temporary keys, never pre-checked)

### A-NEW-01 — Bounded multi-source private pilot before full first public slice

Status: **FUTURE**. Milestone: **M2**. Depends on: **DP-209, DP-210, DP-211, DP-212, DP-213** (hard existing core); further approved source/acquisition rights are external; follow A-NEW-02, A-NEW-03/04/05 as needed for chosen samples.

**Problem:** Production has no real Source→Capture→Passage→Candidate path from the new research corpus. DP-214 is an independent larger **100-item Garlasco acceptance**, not a reason to omit the smaller integrated first successful sample or to fake candidates.

**Outcome:** A versioned **small but representative**, approved private source set traverses the real discovery/capture/text/catalog/candidate path, with verified locators and preserved ambiguity, forming the trusted corpus input for coordinator/B/C's first fully functional public Statement→finding/position→comparison→correction slice. Include more than one Person and source language/media type where the permits allow. Bound the count and stratification in a manifest **before execution**, based on actual permitted availability; do not arbitrarily assert a numeric global coverage goal.

**Traceability & constraints:** R05/R07/R09/R10/R11/R26/R28, Q11–Q20; DP-214 AC-214.1 remains independently required. Original wording, private records, no invented identity/right, no automatic publication.

**Scope:** Candidate official written document and one genuine media item (only if licensed/authorized), people/roles, source versions/rights, capture/parser/Passage/Statement Candidate/Claim Candidate, readbacks of immutable hashes and exact selectors, Coverage Needs for failed arms, dedup and replay. Show which portions are unavailable due to permit rather than quietly substituting fixtures. Operator result is a private, frozen receipt that coordinator can consume as full-slice input.

**Non-goals:** Full 100-item Garlasco ingestion; all languages; public publication eligibility; automated factual verdict; running a background collector.

**Dependencies & sequencing:** Hard existing discovery→candidate contracts above. Source-family launch/acquisition permit qualified by A-NEW-02 and owner/legal as applicable; B machine attribution and C public wording are **soft interface coordination**, not blockers to a private capture pilot. A missing sample family is an explicit constrained selection/NO-GO, not synthetic rights.

**Acceptance criteria:**
- [ ] **AC-A01.1:** Frozen manifest specifies per-Content person/appearance candidates, language, medium, source family, authority/rights and content/retrieval limits, with every actual item selected under its own authorized permit.
- [ ] **AC-A01.2:** At least one approved written and, when explicitly authorized, media sample produces a persisted canonical Capture→Passage→Statement/Claim Candidate with exact selector/hash provenance and no fake timestamps; unavailable media yields a documented blocked arm, not a pass.
- [ ] **AC-A01.3:** Two distinct people or documented unresolved speaker candidates cannot be silently merged across one item or batch; negative wrong-source/identity cases hold.
- [ ] **AC-A01.4:** Exact replay does not duplicate logical Content/Candidates; a changed source creates a new immutable version and triggers reviewed reanalysis rather than replacing history.
- [ ] **AC-A01.5:** No public Finding/PUBLISH increase or private text leak from ingest; missing rights/attribution remains held and explicitly counted.
- [ ] **AC-A01.6:** MiniPC real store readback and private Studio navigation reconstruct each input→output chain and its failure/coverage receipt.

**Validation/proof:** Pre-registered manifest, policy decision refs, canonical SHA/input output snapshots, Postgres and private Studio MiniPC readback, replay/difference, rights/identity negatives and operational cost ledger. Do not treat source-only Mac tests as real capture proof.

**Documentation/data/migration:** Prefer existing IDs/contracts and narrow adapter extension; additive version metadata only if proved absent. Retain source snapshot/hash/rights receipt under existing retention policy; no corpus body or secrets in Git.

**Completion receipt:** **NOT IMPLEMENTED — planning only**. Future exact approved inputs, manifests, parser/provider versions, failed arms, materialized records, MiniPC hashes/counters and consumer links are required.

### A-NEW-02 — Source-family acquisition/use profile with real permission decisions

Status: **FUTURE**. Milestone: **M2**. Depends on: **DP-210, DP-215, DP-305**.

**Problem:** Current source/evidence allowlists and observed licensing metadata can coexist with zero source-specific private capture permits. `rights_status=UNKNOWN` remains normal in Garlasco and Senato AKN. An official domain, HTML reachability, CC license for a **different dataset**, or source role must not silently authorize fetch/storage/transformation/excerpt.

**Outcome:** Every operational source-family action has an inspectable effective *acquisition/use* decision bound to exact family/artifact/version and use kind, read at operation time with revocation/freshness checks. The qualified legal interpretation and **public excerpt** authority remain B/DP-305's remit; A implements its input enforcement and audit path.

**Traceability & constraints:** R08 interface, R09/R10/R05/R25, owner Q15–Q20. Separate license for underlying text, third-party transcription/translation, attached media, site photos, archives, platform terms, and publication; do not adopt blanket legal rules.

**Scope:** Reuse `rights_registry`, `private_capture_rights`, `capture_pipeline` rights-guard hooks, `source_intelligence` exact scoped role/authority and DP-305 decision version. For each `DISCOVER_METADATA`, `FETCH`, `STORE_BODY`, `PARSE/OCR`, `TRANSLATE`, `ASR/MEDIA`, `ARCHIVE`, `EXCERPT_PUBLIC` operation, model explicit permitted/denied/unresolved/expired/revoked and reason/evidence URL, effective time, source family, artifact, medium, retention, person/privacy flags. Discovery metadata may be allowed while body capture is denied. Signature/actor authority must be authenticated without minting rights from normal model output. Do not leak confidential legal notes publicly.

**Non-goals:** Issuing legal clearance within software, universal copyright threshold, bypassing B's public quote gate or cancelling safe metadata lookup.

**Dependencies & sequencing:** Hard DP-210/215/305; external qualified source-specific policy disposition and host/provider terms, soft B rights/citation and D production launch set. AKN CC BY4.0 must be evaluated only against its immutable repo artifact; OpenData RDF CC BY3.0 independently; DVNS external unrelated.

**Acceptance criteria:**
- [ ] **AC-A02.1:** Permit is bound to exact source family, artifact, use type, policy version, rights evidence and validity; unsupported/unknown families produce specific private blocked state before fetch or model work.
- [ ] **AC-A02.2:** A record cleared for metadata discovery cannot be reused for body store, OCR, transcription, public quote or WebTV; tests cover differing dataset licenses and derivative works.
- [ ] **AC-A02.3:** Expired/revoked/superseded permit causes a fresh guard failure before and after acquisition race where feasible; persisted old receipt never changes to CLEARED silently.
- [ ] **AC-A02.4:** An approved bounded private use follows existing Capture/retention path; exact replay is idempotent and records permit fingerprint; a changed permit creates auditable new decision.
- [ ] **AC-A02.5:** Operator sees resolving authority, missing evidence and specific unblock route; public readers see neither private rights notes nor raw body.
- [ ] **AC-A02.6:** MiniPC permit/capture readback proves both successful authorized and denied attempts; zero accidental writes/charges on denied branch.

**Validation/proof:** Source-family decision IDs, dated immutable licensing/source terms where applicable, reviewed policy refs, negative permission matrix, MiniPC guard/readback and revoke/replay. **Decision is required externally; this ticket does not grant it**.

**Documentation/data/migration:** Extend existing registry schema only where current `RightsSubject` cannot express use-specific artifact/medium. Preserve immutable decision history and purge/retention traces; B owns legal wording/cutover policies.

**Completion receipt:** **NOT IMPLEMENTED — planning only**.

### A-NEW-03 — Versioned exact locator and cross-format provenance chain

Status: **FUTURE**. Milestone: **M1R/M2** (prime choose nearest canonical milestone **M2**). Depends on: **DP-210, DP-216, DP-224, DP-225**.

**Problem:** Source URL alone often resolves to a changed page or an adjacent speaker; raw string offsets drift between OCR/parser/transcript versions. Studio's existing metadata inspector lacks full real-source media seek. Public readers later need a precise audited source reference without exposing raw private capture bodies.

**Outcome:** A canonical provenance/locator object binds a verifiable original **Content→Capture/TranscriptVariant→Passage/Segment→exact quote span** with checksum, selector/timebase, transform lineage, source version, author/speaker role and alternative official/archival locations. A resolver detects drift/purge/ambiguity and reports what can actually be opened.

**Traceability & constraints:** R05/R07/R10, DP-216/218/219/224/225/419. Written locators must not invent `0:00`, media locator must not fake text chars; citation of reported speech stays distinct from endorsement.

**Scope:** Compare/version existing `content_capture`, `PassageRecord` (`TEXT_POSITION`, `PAGE_RANGE`, `MEDIA_SEGMENT_REF`), quoted subspan hashes, `claim_text_provenance` and canonical timed segments; link optional original-page selector/paragraph/XPath/PDF page box, media ms and source/time zone. Keep published locator public metadata minimal; full capture/passage private. Align derivation edges for repost/syndicated/translated/archive copies and chronological supersession via DP-511.

**Non-goals:** Public corpus dump; guaranteed player seek when source platform has no stable time URI; rights clearance, identity verdict or standalone new search index.

**Dependencies & sequencing:** Hard existing quote/capture/citation/original-source contracts; soft DP-419 private inspector, C public source-link surface, B context/rights, D archival refresh; real source selector rights externally.

**Acceptance criteria:**
- [ ] **AC-A03.1:** In immutable written source, page/char/paragraph span resolves to exact original text hash and Content/Capture/version; altered bytes or out-of-range span fails closed.
- [ ] **AC-A03.2:** In timed media, canonical transcript variant and segment/timebase resolve and cannot jump to a different speaker or source; unavailable player time is explicitly marked unavailable.
- [ ] **AC-A03.3:** Reposts/archive/translation supply original→derived edges without treating a copy as independent original, and retain the unchanged original-language words.
- [ ] **AC-A03.4:** Changed Content leaves earlier Capture/locator addressable by version; purge retains hash/selector/receipt metadata and marks excerpt inaccessible.
- [ ] **AC-A03.5:** Quoted excerpt cannot cross discontinuity/turn/page/source identity silently; negative stitched quote and wrong-version tests hold.
- [ ] **AC-A03.6:** Private Studio MiniPC readback returns exact source jump; safe public projection later consumes a restricted locator only after C/B publication authority.

**Validation/proof:** Real permitted article/PDF and one actual timed sample, before/after byte/selector hashes, broken locator and altered source negatives, independently reconstructed MiniPC reference. Record supported and unsupported viewer schemes explicitly.

**Documentation/data/migration:** Prefer additive selector metadata preserving old IDs and DP-216 hashes, old API links and immutable Capture versions; no backfill of unreviewed locators with fabricated precision.

**Completion receipt:** **NOT IMPLEMENTED — planning only**.

### A-NEW-04 — Document, PDF/OCR and text extraction with role-preserving provenance

Status: **FUTURE**. Milestone: **M2**. Depends on: **DP-210, DP-211**.

**Problem:** Textual official records, historical scans and procedural/judicial documents cannot be reduced to a media transcript or machine-readable web paragraphs. Image-only PDFs, old orthography, complex columns, footnotes, stamps and incomplete pages can invert quotations or confuse the reported speaker with the author of the document. `PassageRecord.PAGE_RANGE` exists, but a real OCR source path with measured error/locator fidelity is not proven.

**Outcome:** An approved private Capture in a supported written format becomes a faithful, versioned text extraction and page-aligned `Passage` set, with ambiguous/low-confidence spans held before Candidate promotion and no manufactured multimedia timestamps.

**Traceability & constraints:** R09/R04/R05/R07, R21–R22 input to B. Allegation in a court filing is a document assertion, not established fact or necessarily a direct quote by the case subject. Protect minors/victims/third parties and handle redactions before any public output.

**Scope:** Text HTML, born-digital PDF, scan/image PDF, text/XML (including Senato AKN), optional public document image after acquisition-specific rights. Use content hashes and immutable per-page/fidelity/reading-order transforms; preserve source file, page count, page coordinate or text offsets, OCR engine/version/language/profile, original script, ambiguity/split reading-order evidence, missing pages and editor/redaction marks. Model participant-role hints (`DOCUMENT_AUTHOR`, `REPORTING_AUTHOR`, `QUOTED_SPEAKER`, `WITNESS`, `PARTY_ALLEGATION`, `COURT_FINDING`, `UNKNOWN`) as **candidates**, never evidentiary verdicts, with B owning semantic/judicial classification.

**Non-goals:** Universal OCR accuracy, automatic adjudication of guilt, lifting redactions, scraping restricted case files, treating normalized OCR as confirmed exact human speech.

**Dependencies & sequencing:** Hard canonical capture/extraction; qualified document fetch/processing permits A-NEW-02 external; soft B procedural truth/risk, A-NEW-03 locators, A-NEW-05 multilingual, D resource budgets.

**Acceptance criteria:**
- [ ] **AC-A04.1:** A real approved machine-readable text and scanned PDF produce versioned page/char selectors whose original-file hashes, extraction method/version, language and ordered page coordinates roundtrip on MiniPC.
- [ ] **AC-A04.2:** A frozen reference set includes multi-column, page break, negation, numerals/date, direct quotation, reported speech, redaction and incomplete-page cases with measured character/word error and critical-span failures; thresholds fixed before evaluation.
- [ ] **AC-A04.3:** Confidence alone cannot turn corrected OCR into `VERBATIM_ORIGINAL`; uncertain critical span is visibly held and a better original or independently checked span is sought.
- [ ] **AC-A04.4:** No speaker/court/party role is inferred merely from the filename or topic; role ambiguity and homonym yield distinct candidate identities and blocker codes.
- [ ] **AC-A04.5:** Exact replay creates no duplicate Capture/Passage; corrected OCR or new PDF version creates a new derivation/version with supersession rather than rewriting history.
- [ ] **AC-A04.6:** Rights-denied file, parser bomb, corrupt/oversize PDF and malicious embedded metadata cause bounded fail-closed failures with no disclosure in public or model output.

**Validation/proof:** Source-specific legal/retention inputs, private real-file gold and critical error matrix, hashes, accepted/held counts, MiniPC memory/time, exact selector/readback and public-leak negative. Independent reference evaluation required; do not mark 100% merely by self-grading model output.

**Documentation/data/migration:** Reuse `capture_pipeline` parser interface, `PassageRecord` and existing rights/purge; additive OCR/role fields if demonstrated. Historical paper files never become persistent public raw-body assets automatically.

**Completion receipt:** **NOT IMPLEMENTED — planning only**.

### A-NEW-05 — Multilingual original and translation derivation in the private corpus

Status: **FUTURE**. Milestone: **M2**. Depends on: **DP-210, DP-211, DP-221**.

**Problem:** Corpus holds language and translation fields, but current `assess_translation` language risk rules cover only a small list; German is not validated by those heuristics. The owner wants sources in any language, with original exact words and visibly different Italian translations. German historical sources are a practical early adversarial sample.

**Outcome:** Private text/ASR/document records retain immutable original-language spans; translation is a separately versioned derivative connected to the original source/hash, with documented language identification, uncertainty and an independently assessed meaning-risk result for each supported language pair. Unsupported languages remain discoverable and indexable as original-language material with explicit capability state.

**Traceability & constraints:** R04/R09/R27, Q11/Q15; B owns substantive machine meaning assurance/authorization, C owns public dual-language presentation. A method labeled MACHINE must never be relabeled HUMAN_REVIEWED to pass old policy.

**Scope:** Source-language detection + uncertainty, code-switch passages, original BCP-47 language and script, transcription/OCR normalization references, translation provider/model/prompt/version/hash + exact parent mapping, number/date/name/negation/modality/legal terms and quote-origin preservation. An original German text + machine IT translation is a **test pair**, not a guarantee of all languages; model/LLM entitlement and cost routed through D.

**Non-goals:** Publicly substituting translated words for quote; asserting translations are legally licensed; claiming every language reliable; requiring a full-time human translator or switching providers without gate.

**Dependencies & sequencing:** Hard corpus+wording existing DP; external source/derivative rights, soft B semantic assurance/authoritative states, C rendering and D runtime provider budget.

**Acceptance criteria:**
- [ ] **AC-A05.1:** Original capture/Passage words, encoding, script, language, offset and hash remain recoverable while Italian translation resides in distinct derived record with method/model/version/source reference.
- [ ] **AC-A05.2:** Frozen German→Italian adversarial matrix catches at least deliberate negation, number, date, subject, modality, quoted-vs-endorsed and judicial-status mismatches; report measured coverage/errors and holds, no self-certified truth.
- [ ] **AC-A05.3:** Unknown/mixed language or unsupported risk rule remains explicit and cannot be silently assumed Italian or granted exact original-quote authority.
- [ ] **AC-A05.4:** Translation cannot change the original selector's content hash and cannot reassign speaker/Person; altered source version invalidates affected translation confidence and triggers reevaluation.
- [ ] **AC-A05.5:** Replay on same original and model/config is idempotent, changed translation stays a new version, and consumer can fetch original independently of derivative.
- [ ] **AC-A05.6:** MiniPC real approved text pair passes source/translation/Passage readback with zero private-leak or unauthorized rights upgrade; B-specific meaning gate remains separate.

**Validation/proof:** B-approved adversarial reference set and decision rubric, rights and language provenance, frozen model/config and pair hashes, cross-script numerals names negations, MiniPC negative+positive, D usage receipt if real provider invoked in future authorized phase.

**Documentation/data/migration:** Extend `wording_contract`/Corpus derivative seam after B designs automated meaning-assurance state; preserve old human-review historical events, no falsified reviewers. Public output solely through C filtered schema.

**Completion receipt:** **NOT IMPLEMENTED — planning only**.

### A-NEW-06 — Bounded multi-person candidate batch with cross-source identity isolation

Status: **FUTURE**. Milestone: **M2**. Depends on: **DP-211, DP-212, DP-218, DP-222**.

**Problem:** Existing `private_candidate_batch` accepts 1–16 Passage items, but that is neither multi-person semantic acceptance nor an efficiency benchmark. Multi-speaker sessions, interviews, reported speeches and homonyms may contaminate outputs; a very large model window does not remove attribution risk.

**Outcome:** Deterministic, budgeted batch planning and candidate extraction over several Contents, languages and Persons with per-span source identity, role and context intact, per-item replay/failures and independently observed precision/cost compared with bounded single-source baseline.

**Traceability & constraints:** R07/R11/R26/Q12, DP-219/220 nested quote/context. No biometric identity, no automatic cluster equality by topic or lexical similarity. Source roles and languages are not person IDs.

**Scope:** Reuse existing Capture/Passage Candidate batch rather than replace it. Partition by capture version, source family, context continuity, speaker/author candidate and language; preserve source→span→Person/role candidate mapping per output. Freeze batch fingerprint, per-item allocation, per-stage token/audio budget, cross-item leakage detectors, fallbacks, job retries, and per-item ledger. Compare baseline isolated runs against bounded mixed batch and do not impose an unsupported universal 1-person limit.

**Non-goals:** Unlimited context windows, one-person-only policy, face/voice matching, direct publication and B's final machine reviewer authority.

**Dependencies & sequencing:** Hard original extraction/matching/speaker contract. Soft A-NEW-01 source set, A-NEW-05 language, B semantic attribution, D quota measurement. Runtime provider access still explicit gate.

**Acceptance criteria:**
- [ ] **AC-A06.1:** Versioned batch manifest contains at least two distinct approved Persons or unresolved speaker candidates, more than one Content and exact Passage selectors/source hashes; items cannot silently borrow another's source ID.
- [ ] **AC-A06.2:** Explicit adversarial wrong-speaker/quoted-voice/homonym examples yield separate held candidates, with per-segment source/speaker/author context and no public attribution.
- [ ] **AC-A06.3:** Each output Statement/Claim Candidate maps to its own source spans, extraction version and original wording; no stitched cross-source verbatim or forced speaker ID.
- [ ] **AC-A06.4:** Duplicate items, reordered batch, partial provider failure, retry and same idempotency key preserve cardinality/lineage and do not convert failed items to success.
- [ ] **AC-A06.5:** Source-level token/cost/latency/memory and false-attribution rates are measured against a preregistered isolated baseline; approve larger batch sizes only based on observed benefit and non-regression.
- [ ] **AC-A06.6:** MiniPC persisted replay and Studio operator inspection prove each candidate's correct original Content, Person candidate and hold reason; unrelated corpus/public counts remain unchanged.

**Validation/proof:** Attributed gold annotated independently; mixed Italian/German where permitted, official multi-speaker AKN fixture only as a *negative/candidate* baseline until rights clearance; per-item replay receipt, false attribution confusion matrix, D budget counters, MiniPC readback.

**Documentation/data/migration:** Reuse `private_candidate_batch`, candidate matching, DP-218/222; change only necessary per-item provenance keys, migration additive if needed; no second claim table.

**Completion receipt:** **NOT IMPLEMENTED — planning only**.

### A-NEW-07 — Active original-source recovery and finite investigation log

Status: **FUTURE**. Milestone: **M2**. Depends on: **DP-209, DP-213, DP-225, DP-228**.

**Problem:** Existing reviewed original-source resolution follows known derivation edges but does not by itself guarantee active research when identity, time, montage or full wording is uncertain. A queue labeled pending is not an investigation; many copies of one clip are not corroboration.

**Outcome:** A bounded, accountable Source Recovery attempt plan seeks the exact original or fuller context through several distinct approved methods and records why each attempt succeeded, failed, exhausted budget or remained unresolved, then opens a narrow exception with a concrete question. Newly found versions trigger revalidation, not silent historical overwrite.

**Traceability & constraints:** R05/R10/R23, Q09–Q11, B owns factual uncertainty and final machine authority; no invented query/URL, no uncontrolled crawling or copyright assumptions.

**Scope:** Reuse DP-225 original-source resolver, DP-228 scoped research plan, DP-213 Coverage Needs and DP-511 source revalidation. Deduplicated attempts to find longer originals, official primary record, transcript alternative, original poster, contemporary archive, metadata, independent copy and missing context. Record explicitly validated query/URL, expected evidence role, family/lineage, discovery receipt, legal fetch guard, success selector/hash, evidence of why likely original, attempt cap/cost, next retry triggers and temporal relevance.

**Non-goals:** A blanket truth verdict, web-wide research engine, model-generated citation URL, unbounded paid search or production publication.

**Dependencies & sequencing:** Hard core discovery/coverage/resolver/research plan. Soft B clarification/insufficiency, A-NEW-02 rights, D attempt budgets, source-family approval external.

**Acceptance criteria:**
- [ ] **AC-A07.1:** A failed shortened/edited clip case yields a versioned plan with at least two genuinely distinct permitted lookup strategies and exact target question; attempts are provenance-bound and deduplicated by original lineage.
- [ ] **AC-A07.2:** A found longer primary source binds new immutable Capture/version, candidate context and exact locator; does not upgrade uncertain attribution without B's evidence gate.
- [ ] **AC-A07.3:** Copies of the same source count as one derivation lineage, and a wrong person/changed date/unsupported claim holds despite many matching URLs.
- [ ] **AC-A07.4:** Missing search/fetch permit, exhausted budget, outage and not-found record different actionable reason codes with retry/new-evidence triggers; no endless loop or guessed success.
- [ ] **AC-A07.5:** Repeated identical attempts do not regenerate costly work; materially changed sources trigger DP-511 reanalysis/hold provenance and preserve historical records.
- [ ] **AC-A07.6:** MiniPC pilot logs and private Studio display exact attempts, unresolved question, remaining source-family gaps and next allowed action without public privacy leak.

**Validation/proof:** Bounded real authorized clip/text or independently built rights-allowed test source; source resolver before/after hash, distinct upstream lineage, attempt counts/cost/outage simulation, persisted MiniPC Coverage Need receipt, exact negative.

**Documentation/data/migration:** Add attempt-level facts to existing discovery/Coverage Need histories or one narrow additive log; retain immutable query/fetch receipts and caps. D owns background execution timing.

**Completion receipt:** **NOT IMPLEMENTED — planning only**.

### A-NEW-08 — Studio source-to-candidate machine handoff and exception lifecycle

Status: **FUTURE**. Milestone: **M4**. Depends on: **DP-416, DP-417, DP-418, DP-419**.

**Problem:** Studio inbox/collection is increasingly capable at read-only inspection and annotation, yet a queued record can stop at `QUEUED_FOR_HUMAN_REVIEW`. The owner has no ordinary human editorial reviewer. Existing annotation signature and review/promotion rights cannot be converted into fake machine/human approvals.

**Outcome:** A private operator can inspect and re-run the real ingestion→source recovery→candidate analysis pipeline; eligible rows are sent to the future governed autonomous machine authority (B), while hard provenance/rights uncertainties run bounded research or land in a **small actionable exception queue** with no pretend approval/publication.

**Traceability & constraints:** R11/R23/R25/R26/Q14, B owns machine review/final verification/publishing and current gate migration; A owns Studio/source/candidate state transitions only. Private loopback API credentials distinct from public reader/account.

**Scope:** Real persisted rows across Discovery, changed Capture, entity matches, statements/claims, Coverage Needs and held rows; inspect source rights/span/attempt chronology, preview allowed reversible actions, idempotency/CAS checks, asynchronous step progress and negative outcomes. Integrate existing `DiscoveryInboxWorkflow`, triage ledger, `studio_candidate_review` handoff and rights/source selectors with B's explicit new authority API/receipt. Clear boundaries between annotation, research plan, verified candidate and autonomous decision.

**Non-goals:** Auto-approve persons based on a model's confidence, reintroduce routine textual reviewers, bypass B publication policy, bulk publish or expose Studio remotely through OAuth.

**Dependencies & sequencing:** Hard DP-416/417/418/419 actual persisted paths; soft A-NEW-01/07 source state, B machine approval contract and transactional revocation, D background scheduler. Real transition remains blocked if authority API is unavailable, not silently simulated.

**Acceptance criteria:**
- [ ] **AC-A08.1:** Each real queue family has bounded provenance/rights/identity/action currentness and a specific machine-action or investigation/exception decision; no generic "ready" without state.
- [ ] **AC-A08.2:** Review/analysis handoff records exact source/Capture/Passage/Person candidate/rights snapshots and authority-version fingerprint; stale snapshot or source revocation forbids transition.
- [ ] **AC-A08.3:** Same action key replays identically, conflicting/stale revision fails, incompatible bulk groups cannot share a permission or promote across families.
- [ ] **AC-A08.4:** Safe eligible path reaches real candidate analysis and governed B API/receipt, including evidence of resumed downstream output; missing B authority produces explicit blocked state instead of human-reviewed=true.
- [ ] **AC-A08.5:** Negatives (secret, cross-collection, rights revoked, wrong source, publisher mismatch, provider unavailable) preserve private isolation and no public Finding/PUBLISH increase.
- [ ] **AC-A08.6:** MiniPC operator real-source path plus keyboard-accessible 320–1440 viewport/readback verified, including retry, bounded queue and exception processing.

**Validation/proof:** Real authorized run with actual persisted Discovery Hit + Candidate; state-machine and CAS adversarial fixture; loopback authenticated HTTP, MiniPC DB/authority receipt, no-public-change counters. Mocked/historical Garlasco zero-Hit paths do not close AC.

**Documentation/data/migration:** Reuse real ledger/private API, B owns machine signature trust and cutover. Append-only provenance and safe readers; never expose machine score/person opinions.

**Completion receipt:** **NOT IMPLEMENTED — planning only**.

### A-NEW-09 — Initial permanent historical corpus from mixed Italian/German primary sources

Status: **FUTURE**. Milestone: **M2/M7** (prime choose **M7** for post-slice historic expansion). Depends on: **DP-210, DP-215, DP-703**; requires accepted first full source→public→correction slice **outside this A ticket** as hard release milestone prerequisite. Coordinate A-NEW-04/05/06.

**Problem:** Hitler/Mussolini historical materials are owner-chosen initial areas, but identifying an archive's topic landing page does not authorize a transcript, a quote or a body download. Historical materials mix speeches, quotations, newsreels, reproductions, later translations and derivative films. A deceased figure's corpus grows with newly found/digitized sources; no finite crawl can claim exhaustiveness.

**Outcome:** After first full-slice acceptance, create **permanent**, versioned private historical research collections/Content for both named public figures with correctly scoped source use, original IT/DE wording, German→Italian translation links where permitted, explicit authors/speakers and documentation of missing/held source families; promoted/public entries occur only through B/C validated downstream and not automatically from acquisition.

**Traceability & constraints:** R04/R07/R09/R10/R27; original/source language protected, no endorsement inference for historical narration/quotation. Candidate archive starting points (not approved inputs): Archivio Luce Mussolini topic index and Bundesarchiv Hitler-themed holdings/digitization listings, supplied in master prompt. Their terms, artifact-level rights and personal data policy require independent decisions. No archival truth or clip quote is invented here.

**Scope:** Curate separate genuine Italian and German period sources, multi-format scans/video/transcript, immutable version/rights/discovery manifest, source/copy relations, period/origin timezone, speech/event/date/author roles and scope; track translations/editorial editions and historical scholarship as different evidence roles. Include small cross-person comparison-ready topics with source-confirmed semantic identity only; B/C own public comparisons.

**Non-goals:** Claims that the two persons' entire historical record is collected; mass uncontrolled crawling; bundled publication of archive footage; source-specific legal clearance based on death; replacing original quote by translation.

**Dependencies & sequencing:** Hard full first reader/correction path accepted at milestone gate, existing DP-210/215/703; A-NEW-02/04/05 as applicable; external Archive/Luce and Bundesarchiv source-family permits, archive-licensing/third-party transcript choices and German meaning validation; soft D bulk/cost, B/C publication.

**Acceptance criteria:**
- [ ] **AC-A09.1:** Two versioned historical manifests each identify primary originals, archive copies, modern editorial/text translations, rights/use states, precise retrieval selectors and coverage horizon; denied items are held with reason.
- [ ] **AC-A09.2:** A real permitted original-language document for each chosen person yields immutably hashed Capture/Passage and source/author/speaker status, with no accidental inference from film narrator/actor/reported speech.
- [ ] **AC-A09.3:** German original and optional authorized Italian translation have distinct fingerprints, dates, methods and named mismatch holds; translations never override original words.
- [ ] **AC-A09.4:** Same uploaded source/repost across collections dedupes logical Content while preserving independent collection membership and source provenance; replay creates no duplicate statements.
- [ ] **AC-A09.5:** A new archival transcription/version or corrected translation triggers a new retained source version, revalidation and exact impact list (candidate/public downstream), with no silent overwrite.
- [ ] **AC-A09.6:** MiniPC private readback, source/rights receipts and source coverage report are verified; public record count changes only under separately approved B/C policy and release.

**Validation/proof:** Immutable approved archive artifact refs, source-specific licenses, language/version hash, roles/origin negative checks, replay and MiniPC snapshot; a small accepted corpus can prove process, not historical completeness.

**Documentation/data/migration:** Collections and source profile reuse; add language/editorial-edition/coverage metadata only where absent; retain private files only for permitted period and explicit retention.

**Completion receipt:** **NOT IMPLEMENTED — planning only**.

### A-NEW-10 — Source coverage inventory, version refresh and incremental catalog

Status: **FUTURE**. Milestone: **M7** (post-acceptance bulk/continuity). Depends on: **DP-209, DP-213, DP-215, DP-511**.

**Problem:** A permanent corpus needs source-specific completeness statements and refresh. A fixed historic person still gains new archival scans/transcripts; a monitored active public figure or source may change daily. Re-fetching identical body and re-running models every day wastes budget; a new source may supersede an old quotation. A missing item is not evidence the person never spoke.

**Outcome:** A versioned private source/collection catalog displays exactly **what source families and time windows were attempted, accepted, incomplete, blocked, stale or changed**, with conditional reobservations and replayable delta proposals for D's future economical background scheduler; sanitized freshness/coverage information can later inform C's public readers.

**Traceability & constraints:** R10/R23/R27/R33; Q09–Q20. Continuity for followed people/topics/sources with allowance for new events; no virality-only selection, global completeness claim, inferred intention or person ranking.

**Scope:** Family/format/language/time/subject coverage unit, official-source-first candidates, observed version/hash/ETag/Last-Modified where reliable, `source_revalidation` deltas, derivation dedup, change significance, failure/rights status, work budget, retry and provenance. Distinguish stable historical backfill from current source subscription; formalize new digitization and manual correction triggers. Expose bounded `UNKNOWN`, `NOT_COVERED`, `PARTIAL`, `STALE`, `CURRENT_WITHIN_OBSERVED_SCOPE` vocabulary; no fabricated completeness ratio.

**Non-goals:** Unlimited crawling or subscription, automatic publication, all-world corpus assurance, installing a scheduler or payment provider, changing a model to fit costs.

**Dependencies & sequencing:** Hard existing discovery, Coverage Needs, evidence roles, revalidation; soft D scheduler/cap/health, A-NEW-03 version locator, A-NEW-09 historical collections, B holds/updates and C freshness display. Permissions and feed robots/rates are external source-family inputs.

**Acceptance criteria:**
- [ ] **AC-A10.1:** Inventory describes actual source families/interval/language/format, last successful observation, failed/blocked attempts, expected content class and unknown gaps, with provenance and versioned decision reasons.
- [ ] **AC-A10.2:** Re-observing unchanged permitted source produces cheap idempotent no-op; a materially changed version generates new immutable Capture/reanalysis/coverage work (after rights/relevance guards).
- [ ] **AC-A10.3:** Expired/denied source permit, outage, retried fetch, HTTP conditional inconclusive and missing catalog item remain distinct and do not become false full coverage or free-cost success.
- [ ] **AC-A10.4:** Backfill and subscribed incremental changes report separate work/cost counts; priority honors followed source/person/topic continuity plus newly relevant events with explicit fairness and source-scope criteria, no political scoring.
- [ ] **AC-A10.5:** New official archival digitization, corrected transcript and missing original reopening show exact affected record/locator versions, without using later evidence to judge prior-date knowledge.
- [ ] **AC-A10.6:** On MiniPC a frozen small permitted source set yields reproducible baseline/unchanged/changed/outage receipts and a sanitized public-ready freshness descriptor containing zero private membership/rights notes.

**Validation/proof:** Bounded online source-family acceptance **in later implementation only**, independent source version hashes before/after, run/attempt ledger, conditional fetch negative tests and MiniPC DB counters; D cost-by-stage receipt and B correction trigger readback. No guessed total-universe coverage denominator.

**Documentation/data/migration:** Extend Discovery/Source Health/Coverage Need/DP-511 version store rather than standalone catalog DB. Do not activate timers; D governs scheduled execution and cap.

**Completion receipt:** **NOT IMPLEMENTED — planning only**.

## Sequencing and exact integration boundaries

1. **Phase 0 — contracts, no implementation here:** B owns public wording/copyright/machine authority, C exact output, D cap/release. Prime allocates stable IDs and resolves qualified source/rights disposition. A-NEW-02 and A-NEW-03 are earliest source-side contract extensions.
2. **Phase 1 — first small real source path:** A-NEW-01 with A-NEW-04/05 for chosen document/language and A-NEW-06 for multiple persons; DP-201/202/204 canary paths remain separately blocked until their **actual** external route/credential. Use existing lawful deterministic source-native path where proven, without falsely marking live provider AC passed. DP-233 can contribute AKN held private source format but cannot be called authorized public statement. DP-234 RDF supplies sitting metadata only.
3. **Phase 2 — full private→reader correctness:** A-NEW-07 original-source investigation; A-NEW-08 joins DP-416/417/418/419 private Studio with B's machine final check and C's public exact Statement; DP-420 operator UX acceptance only on genuine corpus. First integrated MiniPC source→public→correction acceptance is coordinator/B/C/D owned, with no statement promoted until policy contracts pass.
4. **Phase 3 — production-quality and Garlasco 100:** DP-214 retains its 100-item requirement, DP-215.9 source suitability and DP-416/417/419/420 real acceptance. DP-208 only if speaker segmentation trial is worthwhile/eligible. D performs cost/policy/release gates.
5. **Phase 4 onward — bulk historical permanence and source continuity:** A-NEW-09 Hitler/Mussolini historical set and A-NEW-10 version refresh/catalog with D scheduling and B/C downstream reanalysis. No automatic claim of complete historical corpus.

**Overlap guard:** A-NEW-02 stops at acquisition/use enforcement + receipt; B handles qualification/rights and exact-public quotation. A-NEW-05 manages original/translated derivation; B defines machine semantic assurance and C renders originals/translation. A-NEW-07 stops at source investigation/attempts; B determines evidence insufficiency and truth. A-NEW-08 stops at Studio/candidate operational handoff; B owns machine/verification signature and publication policy, D runtime scheduler. A-NEW-09/10 own source corpus coverage; D owns recurring jobs, provider choices and operational monthly caps. A-NEW-03 supplies locators; C owns public projection/schema/API and DP-419 owns private inspector UI. DP-214 retains distinct 100-item Garlasco source acceptance; coordinator owns integrated full slice.

## Proof inventory, integration warnings and concrete remaining authorizations

- Canonical prior evidence is in original ticket receipts, `docs/ops/garlasco-pilot-seed-readback-20261008.md`, `docs/ops/garlasco-paused-baseline-20261008.md`, `docs/reviews/2026-10-08-studio-garlasco-private-members.md`; never overwrite. Current Garlasco PAUSED + 18/18 rights UNKNOWN, 30 old Claims, zero new Captures/Candidates; 30-claim stability is the only DP-214 checked AC.
- DP-215.1..8 source-role/independence/requirement-profile/assessment have MiniPC DB-backed test evidence, but none grants live evidence suitability for absent Garlasco selected sources (AC-215.9).
- DP-233 official AKN source/version/readback hashes, 104 HELD candidates on isolated MiniPC; source format success is not production import, speaker approval, public verbatim or DP-233.10. Original 121+5 candidate counts and 17 over-limit/22 total held must remain explicit.
- DP-234 official **OpenData** RDF ZIP 186 sitting records hash above, with held rights; do not conflate with AKN speeches or DVNS approved integration. Two external AC remain genuinely open.
- DP-417 production triage migration is already applied as of 2026-10-10, never describe it as absent; real Discovery Hits/triage actions still zero. DP-419 has source-only/isolated fixture proof, no live Capture compare or synchronized player seek.
- Precise external values needed later: officially fixed OmniRoute route artifact + meaning/cost receipt (DP-201); live Groq credential + approved audio sample and spend cap (DP-204); exact source-family use policy/license/retention decisions (A-NEW-02, DP-233.10, DP-214, DP-703); qualified DP-305/rights decisions (B owner); DVNS actual approved contract and compatible rights (DP-234); independent gold and model/license for DP-208; real historical artifact permissions for A-NEW-09; first full MiniPC consumer acceptance before historical bulk. None may be filled by an agent from dataset reachability.
- Canonical hard DAG should avoid making DP-214 100 items a prerequisite of the smaller first complete slice or every source adapter, while retaining its 100-item AC for later acceptance. Avoid allowing future automation to rely on a human textual reviewer the owner does not have.

## Packet validation and receipt

Planning proposal only; no application tests/provider trials/source capture/deploy run. To integrate: assign collision-free final DP IDs; copy full specs into individual canonical tickets, rewrite `AC-Axx.*` to final `AC-###.*` and update the R01..R42 matrix; preserve original ACs/receipts and states until independent proof; apply canonical `Depends on` parser rules; run `tools/check_repository_contract.py`, `tools/report_ticket_status.py --json`, `git diff --check` through prime. This packet should then be marked **absorbed**, with final ticket-ID map, by the coordinator; it is not a parallel long-term backlog.
