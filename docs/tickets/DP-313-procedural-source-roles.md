# DP-313 — Documento processuale: persone, ruoli, affermazioni e stati

Status: IN PROGRESS
Milestone: M2 — live pipeline readiness and source coverage
Depends on: DP-111, DP-215, DP-219, DP-222, DP-227, DP-304, DP-309, DP-312

## Problem
 OCR ufficiale o PDF leggibile non trasforma un'accusa, una citazione testimoniale o una decisione non definitiva in fatto accertato. `high-risk-assertion-v1` distingue alcuni status, ma manca un'analisi generalista affidabile di ruoli, dispositivi e versioni in atti complessi. Bloccare per principio tutti i processi tradirebbe Q18.

## Outcome
 Contratto di extraction/interpretation documentaria verificabile che conserva *chi è autore dell'atto, chi viene citato, chi sostiene l'affermazione, quale organo e stato, quale fatto viene allegato o accertato*, con locatori/versione e limiti; produce candidate private sicure per Statement e verifica mirata.

## Traceability & constraints
 R21/R22/R12/R24 e Q18. Nessuna deduzione di colpevolezza da indagine; nessuna divulgazione incidentale di minori/vittime/terzi o status sensitive senza policy.

## Scope
 Document original+OCR confidence/page/layout/version/publication/effective dates/jurisdiction → signed/authenticity source-role/evidence requirement check → identified text span to `document_author`, `reporting_body`, `quoted_person`, `subject_person`, `procedural_party`, `status_at_date` (investigato/imputato/condannato/assolto/archiviato e definizioni locali con versione) → `ALLEGATION/TESTIMONY/FINDING_ORDER/DECISION_REASONING/INSTITUTIONAL_FACT/QUOTED_TEXT` typology → private candidate with exact source hash, quote location, qualified policy/privacy/rights gates. Later appeal/supersession invalidation via DP-227/511.

## Non-goals
 Non giudica fatti extratestuali perché compare una testimonianza, non sostituisce consulenza legale, non crea nuovi documenti processuali.

## Dependencies and sequencing
 DP-312 first for reported speech; A source text/OCR before real pilot; DP-314 for independent factual outcome, DP-316 for machine eligibility, DP-307 for public legal decision. No one-person batch constraint.

## Acceptance criteria

- [ ] `AC-313.1`: Testo attribuito a testimone riportato da giudice e accusa di una parte mantengono autori/ruoli separati; nessun `FACTUALLY_FALSE/SUPPORTED` sui fatti sottostanti solo per mera citazione.
- [ ] `AC-313.2`: Confronti di status, giurisdizione, data-effetto, versione/impugnazione negano equivalenza errata (indagato ≠ imputato ≠ condannato; assolto ≠ archiviato).
- [ ] `AC-313.3`: Documento scansito con OCR errato in negazione/nome/data e omonimia è held, richiede confronto con originale/alternativa e conserva revisione.
- [ ] `AC-313.4`: Minori, vittime, terzi incidentali e dato sensibile vengono segregati/redatti, conservando citazione essenziale solo quando DP-304/307 e rights lo autorizzano.
- [ ] `AC-313.5`: Indipendenza: due siti che ripubblicano lo stesso atto formano una famiglia, non due conferme; versione aggiornata stales conclusioni con causale e replay.
- [ ] `AC-313.6`: Pilot futuro con almeno una fonte giudiziaria ufficiale realmente autorizzata attraversa original→passage→candidate→check→private/public conditional revalidation su MiniPC, includendo una negazione/allegazione; senza grant resta held.

## Validation / proof
 Test sintetici redatti come piccoli documenti con firme fittizie dichiarate, varianti e controtest, poi gold di documenti autentici con base di accesso/uso registrata; readback sui locator originali e output di ogni categoria.
## Documentation, data, and migration impact
 Nuovi role/act/status records/version links additivi solo se il domain model esistente non basta, retention/privacy audit e policy jurisdiction map.
## Completion receipt
 non implementato; pianificazione soltanto.

## 2026-10-11 — First implementation slice

Commit `6afb00f`. Added private `procedural_document_roles.py` with typed SOURCE/AUTHOR/REPORTER/WITNESS/ALLEGATION/COURT_DECISION status/role distinctions, date/jurisdiction/negation/privacy holds and no factual verdict from mere quotation. 24 new cases plus targeted semantic/high-risk regressions PASS. No real procedurally authorized document, independent OCR source proof, qualified legal permission or release/MinIPC canary has been accepted. **All original AC remain unchecked**; this is a local source-only test receipt, not permission for live publication.

## 2026-10-11 — Fail-closed author and procedural-status follow-up

Two adversarial synthetic regressions reproduced genuine `CANDIDATE_PRIVATE` fail-open decisions before the patch (focused `unittest`, 2/2 failures):

- A `REPORTER`/`QUOTED_TEXT` annotation with nonempty `quoted_author_ref=person:unregistered` could pass without an identified `DocumentPerson`; quoted-person identity is now required for **every** quoted-text role. Unknown quoted authors return `HOLD` / `QUOTED_AUTHOR_IDENTITY_UNVERIFIED`; an identified public figure remains a private candidate, never publication authority.
- A first-person `WITNESS_STATEMENT` could return a definitive `CONVICTED` procedural status candidate just because the witness text said `Mario è condannato.` and an annotation labeled it `INSTITUTIONAL_FACT`. Such a document is now held with `WITNESS_SOURCE_NOT_STATUS_AUTHORITY`. A properly annotated `COURT_ORDER` stays a private candidate; fact assessment remains `NOT_EVALUATED` in both cases.

Local proof: focused DP-313 tests **26/26 PASS**, `compileall` PASS, deterministic benchmark **5/5 PASS**, `git diff --check` PASS. Repository-wide caller search found no consumer of the private DP-313 receipt other than these tests; its v1 schema/version remains unchanged and fail-open cases now produce changed decision hashes. All original AC-313.1–6 remain **open**: no independently authorized official document/OCR original, source rights or qualified legal/privacy review, cross-module revocation/invalidation replay, MiniPC pilot or public conditional revalidation has been accepted. No public dataset/permission or deploy was produced by these local checks.

## 2026-10-11 — Embedded testimony/status authority fix (source only)

The court-document classifier previously accepted a specific procedural status
such as `CONVICTED` solely because the words appeared in a `COURT_ORDER`, even
when the annotation identified the sentence as **witness testimony**, a
**reporter's quotation**, or a **party allegation**. Three independent synthetic
adversarial subcases reproduced `CANDIDATE_PRIVATE` before the patch (RED):
`TESTIMONY/WITNESS`, `QUOTED_TEXT/REPORTER` and
`ALLEGATION/ALLEGATION`, all with a claimed `CONVICTED` status. This could
misrepresent a quoted assertion as the court's own procedural determination.

For a *specific* typed status, `evaluate_procedural_document` now requires
an institutional `AUTHOR/INSTITUTIONAL_FACT` or a court
`COURT_DECISION/FINDING_ORDER` role/kind pair; other roles produce `HOLD` with
`ASSERTION_ROLE_NOT_STATUS_AUTHORITY`, preserving the exact source wording,
attribution, and `NOT_EVALUATED` underlying-fact state. A source-attributed
institutional court statement still yields only a private candidate, never an
independent verdict or publish grant. Existing source-kind, negation, original
OCR, version, rights and privacy boundaries are unchanged.

After the fix the entire focused DP-313 suite passes **27/27**, including the
three formerly failing cases and institutional positive control. The combined
DP-313 + DP-312 speech act + high-risk assertion + DP-314 requirement suite
passes **75/75**; `ruff check`, `compileall` and `git diff --check` pass.
These are **synthetic local unit
tests only**. Original **AC-313.1–6 remain unchecked**, pending a legitimately
authorized official judicial source and original/OCR inspection, qualified
privacy/rights policy and MiniPC source-to-public conditional-revalidation
pilot. No source rights, human/machine approval, judicial truth or publication
authority is inferred.
