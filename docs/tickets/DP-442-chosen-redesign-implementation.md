# DP-442 — Implementazione futura del redesign scelto e migrazione controllata

Status: FUTURE
Milestone: M4 — public product/API
Depends on: DP-425, DP-441, DP-436

## Problem

Un brief e una direzione approvati restano inerti se l'attuale frontend continua ad avere altezza, gerarchie, stati e classi legacy non coerenti. La presenza di stili v4 e circa 3.000 righe legacy CSS è un debito verificabile, ma la rimozione indiscriminata rischia regressioni e va giustificata da consumer reali.

## Outcome

Dopo **scelta owner DP-441**, applicare la nuova grammatica nelle nove famiglie pubbliche con differenze visibili/operative misurate, riutilizzando componenti locali e garantendo source-first, exact original quote, summary/translation separati, optional Finding, corrected chronology, Story Person/Topic e Persona×Tema. Ogni pagina resta leggibile nel legittimo empty live e nei popolati approved records.

## Traceability & constraints

R02/R03/R16/R20/R35/R36, DP-412/425 e page-owners DP-405..410/422/426..429. Il redesign è visual/reader architecture downstream delle scelte; privacy/rights non cambiano, nessun fake person/quote/media/verified badge. Un'immagine assente resta assente, non viene inventata.

## Scope

Dal design owner-approved creare route-level migration map, tokens/type hierarchy/responsive density spec, compositi SourcePath/OriginalQuote/OptionalFinding/Summary/Translation/Chronology/IntersectionFilter/EmptyState, piano di progressiva sostituzione per classi duplicate legacy solo dove actual readers migrano, with deletion audit e bundle-budget control. Page owners implementano il layout specifico, DP-412/425 la shared grammar; questo ticket controlla convergenza e QA artefact, versioned prototypes/visual proofs e final routes. Mobile 320/375/390/430 prima-class; per 200% true browser zoom controllare 640 CSS rendered e non solo viewport emulation. Le pagine con corpus zero non usano finti timeline/placeholders/quote; i link disponibili si allineano a feature realmente servite sul MiniPC (account, Studio, API, footer).

## Non-goals

Selezione owner, rewriting DB/public projection, importare un framework, generare foto non autorizzate, sostituire AT con check CSS, pubblicare fixture; il gate release appartiene a D/DP-702.

## Dependencies and sequencing

Hard DP-425 come baseline riutilizzabile; **DP-441 owner-selection è hard gate**, da aggiungere al Depends on solo dopo ID reale, come DP-436/05 se un component dipende da nuovi public records. DP-412 può ricevere delta token ma non diventare dipendenza circolare; DP-405/406/407/408/429 sono page owners e non hard parent, con milestone QA DP-410 finale. Soft coord D MiniPC release, DP-422 routes e DP-401 hosting.

## Acceptance criteria

- [ ] `AC-442.1`: implementazione copia fedelmente **decisione owner** con checklist dei component contracts/tokens/page jobs; almeno un cambiamento di UX misurabile oltre alle differenze cromatiche, comparabile al baseline.
- [ ] `AC-442.2`: Home/Esplora live empty mostrano stato vero e invito utile above fold a 320/390, non «modifica la ricerca» quando totale indice è zero; Metodo non satura il primo schermo con indice e Progetto non ha overflow.
- [ ] `AC-442.3`: popolato approvato su Statement/Person/Topic/Content/Trace e filter Persona×Tema mantiene quote originale prioritario, fonte precisa, summary/translation separate, optional Finding, correction/version and no-intent rule.
- [ ] `AC-442.4`: 320/375/390/430/768/1440, exact 200% zoom, VoiceOver desktop + mobile screen reader, contrast and keyboard focus/reading order, reduced motion/touch 44px pass documented QA; no horizontal scroll regressions.
- [ ] `AC-442.5`: CSS/components removed only after route consumers migrate and screenshot/behavior diff confirms no break; no new large deps, measured JS/perf budgets DP-410, no fake external network calls.
- [ ] `AC-442.6`: approved empty vs no-match/stale/private omitted are distinct where safe; navigation, canonical/meta/sitemap/search do not advertise non-existent account/intake, Studio or demo routes.
- [ ] `AC-442.7`: clean clone QA, pinned MiniPC actual release-mirror readback and rollback artifact link compare same projection fingerprint across APIs/search/HTML; no fixture shipped public.

## Validation / proof

Before/after screenshots with input provenance at each viewport for nine public families and empty/populated/partial/revoked states; real browser DOM and focus, AT human receipt, responsive pixel overflow, Lighthouse/lab perf and JavaScript bundles; test source/citation path and source rights during redesign; D MiniPC immutable release and authoritative HTTP/API/search readback. Defer aesthetic subjective final sign-off until owner choice and review.

## Documentation, data, and migration impact

Update only chosen design tokens, style/semantic component contract, migration map, versioned docs/UX and route screenshots; preserve old DP-411/424/425 historically correct receipts. No schema/data migration in redesign, only consumer field changes governed by DP-436.

## Completion receipt

Non implementato; pianificazione soltanto. Future design decision, commit/visual/perf/AT checks, removed legacy diff, source unchanged proof, MiniPC public readback and rollback.
