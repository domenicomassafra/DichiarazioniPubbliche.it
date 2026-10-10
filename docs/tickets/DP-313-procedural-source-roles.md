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
