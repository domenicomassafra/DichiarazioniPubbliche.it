# DP02 / ControlCenter 297 — inventario delle dichiarazioni e dei documenti pubblici

**Rilevazione sorgente:** 2026-10-14, checkout `DP-20261014-all-lanes-integrator`, branch `integrate/dp-20261014-all-lanes`. **Classificazione:** inventario read-only delle evidenze, **non** autorizzazione editoriale, parere legale, certificazione di deploy o chiusura di ticket. Le parole «presente» e «implementato» descrivono file/route sorgente; non attestano contenuto pubblicato su MiniPC/CDN. Il numero di dichiarazioni pubbliche effettivamente approvate va letto dalla proiezione/runtime autorizzati al momento del rilascio, non da fixture o dal solo sorgente.

## Autorità e perimetro

- Mandato esterno: `/Users/domenico/ControlCenter/src/controlcenter-ops/tasks/20260929-main-release-closure/297-handoff-restart-20261012/02-dichiarazioni-pubbliche.prompt.md`, con `README.md` nella stessa cartella. Il mandato conserva separati ricerca, prova, revisione, pubblicazione e accettazione runtime (sezioni «Git pubblico, runtime e prove» e «Loop fino alla chiusura»). La presente nota è un inventario subordinato, non una modifica al packet ControlCenter.
- Regole autorevoli: [GOVERNANCE](../../GOVERNANCE.md) per gerarchia di decisione e release; [PRODUCT](../../PRODUCT.md) per invarianti e superfici pubbliche; [CONTEXT](../../CONTEXT.md) per semantica della dichiarazione/claim/finding; [ARCHITECTURE](../../ARCHITECTURE.md) per proiezione fail-closed e autorità MiniPC; [PLAN](../../PLAN.md) e [specifiche dei ticket](../tickets/README.md) per stati/acceptance. Il contratto delle cartelle è descritto in [docs/README](../README.md) e in [AGENTS](../../AGENTS.md).
- [LAUNCH](../../LAUNCH.md) distingue le **sei pagine informative** dall'**archivio editoriale**. Il suo snapshot registra una proiezione approvata vuota e nessuna autorizzazione a pubblicare claim reali; la situazione live successiva richiede verifica indipendente. Il [preflight informativo](../ops/informational-preview-bundle-preflight-20261010.md) separa esplicitamente `--bundle-only` dalla decisione umana: un controllo meccanico verde mantiene `launch_authorized=false`.

## Artefatti rivolti al lettore — riscontro nel tree

| Artefatto o destinazione | Percorso sorgente effettivo | Stato accertato nel sorgente / limite |
| --- | --- | --- |
| Home `/` | [`web/src/pages/index.astro`](../../web/src/pages/index.astro) | Route presente; dati solo da proiezione approvata; non prova di contenuto editoriale pubblicato. |
| Ricerca `/esplora/` | [`web/src/pages/esplora.astro`](../../web/src/pages/esplora.astro) | Route presente; indice/filtri soggetti allo stesso confine della proiezione. |
| Metodo `/metodo/` | [`web/src/pages/metodo.astro`](../../web/src/pages/metodo.astro) | **Testo pubblico presente:** provenienza, distinzione citazione/parafrasi/traduzione, attribuzione, incertezza, AI, correzioni; descrizione metodologica, non certificazione di conformità. |
| Correzioni `/correzioni/` | [`web/src/pages/correzioni.astro`](../../web/src/pages/correzioni.astro) | **Registro pubblico condizionale presente:** legge soltanto `projection.dossiers[*].corrections`; stato vuoto esplicito. Non equivale a canale approvato di reclamo, replica o appello. |
| Dati & API `/dati/` | [`web/src/pages/dati.astro`](../../web/src/pages/dati.astro) | **Testo pubblico presente:** link ad API v1, schema `dichiarazioni-pubbliche-public-v2`, separazione dei diritti del codice da quelli dei terzi. Link/shape da verificare nel build/runtime effettivo. |
| Progetto `/progetto/` | [`web/src/pages/progetto.astro`](../../web/src/pages/progetto.astro) | **Testo pubblico presente:** missione, repository, limiti; dichiara espressamente che contatti non confermati non sono definitivi. Non contiene titolarità/contatto/indipendenza editoriale formalmente approvati. |
| Documenti nel footer | [`web/src/layouts/BaseLayout.astro`](../../web/src/layouts/BaseLayout.astro) e [`SiteHeader`](../../web/src/components/SiteHeader.astro) | Footer source: Metodo, Correzioni, Dati & API, Progetto, Accedi, GitHub. Non espone qui Privacy o Contribuisci. Un link nel layout non dimostra deploy. |
| Dichiarazione e schede collegate | [`web/src/pages/dichiarazioni/[slug].astro`](../../web/src/pages/dichiarazioni/[slug].astro), [`persone/[slug].astro`](../../web/src/pages/persone/[slug].astro), [`temi/[slug].astro`](../../web/src/pages/temi/[slug].astro), [`contenuti/[slug].astro`](../../web/src/pages/contenuti/[slug].astro), [`tracce/[id].astro`](../../web/src/pages/tracce/[id].astro) | Template presenti, soggetti ad attribuzione, diritti, revisione, versione e proiezione consentita. L'esistenza di template non certifica un claim pubblicabile. |
| Percorso archivio / serializzazione | [`public_projection.py`](../../poc/dichiarazioni_pubbliche/public_projection.py), [`web/src/lib/projection.ts`](../../web/src/lib/projection.ts), [`web/README`](../../web/README.md) | Confine backend → bundle v2 → frontend; demo/fixture esplicita di sviluppo **non è** evidenza editoriale o dataset lecito da distribuire. |
| UI accesso personale | [`web/src/pages/accedi.astro`](../../web/src/pages/accedi.astro), [`account.astro`](../../web/src/pages/account.astro) | Sorgenti presenti, ma [PRODUCT](../../PRODUCT.md) e [DP-517](../tickets/DP-517-reader-google-login.md) mantengono login reale subordinato a OAuth, privacy/retention/contact e sicurezza MiniPC. Nessuna autorizzazione alla raccolta pubblica deriva dalla UI. |

La [architettura di prodotto v3](../35-public-product-architecture-v3.md) prevede nel footer anche **Privacy** e **Contribuisci** e chiede a Progetto contatti, responsabilità editoriale e informazioni su indipendenza/funding. La ricognizione di `web/src/pages` non ha individuato route `privacy`, `termini`, `contatti`, `reclami` o `contribuisci`. Questo è un **gap di superficie/documentazione**, non un invito a riempire i testi con titolari, basi giuridiche o recapiti presunti. Per Contribuisci, [DP-508](../tickets/DP-508-public-intake-abuse-controls.md) e intake/legal devono prima autorizzare il percorso.

## Documenti giuridici/editoriali e formalità richieste

| Documento / decisione | Riscontro esatto | Stato formale e autorità mancante |
| --- | --- | --- |
| Registro legale Italia/UE | [`docs/policy/legal-closure-register.md`](../policy/legal-closure-register.md), [DP-306](../tickets/DP-306-italy-eu-legal-research-closure-checklist.md) | **Registro costruito, non clearance:** Q-306-01..16 = **14 OPEN, 2 BLOCKED, 0 DECIDED, 0 CLOSED**, tutte 16 con impatto `BLOCKER`; fonti giuridiche raccolte non sono parere né valutazione della norma italiana applicabile. |
| Informativa privacy / titolare / basi giuridiche / diritti / retention | [`dp-304-privacy-policy.md`](../policy/dp-304-privacy-policy.md), [DP-304](../tickets/DP-304-privacy-minimization-sensitive-person-policy.md), Q-306-05/08/09/10/15 | Policy interna/versionata e inventari tecnici esistono. **Nessuna informativa pubblica approvata** né decisione qualificata su ruoli, basi giuridiche, periodi di conservazione, log/cookie e contatto; DP-304 `IN PROGRESS`. |
| Termini d'uso, canale pubblico contatti/reclami, responsabilità e disclosure | Q-306-14/15 nel [registro](../policy/legal-closure-register.md); [DP-701](../tickets/DP-701-brand-domain-handle-clearance.md), [DP-702](../tickets/DP-702-prelaunch-legal-security-privacy-review.md) | **Documentazione/decisione pubblica ancora da approvare**; DP-701 `IN PROGRESS`, DP-702 `FUTURE` con lancio `BLOCKED`. Nessun recapito fittizio. |
| Reclami, rettifiche, repliche e ricorsi | [`dp-303-challenge-workflow.md`](../policy/dp-303-challenge-workflow.md), [DP-307](../tickets/DP-307-qualified-legal-review-adr-policy-changes.md), Q-306-03/04/06/07 | Workflow privato/di policy presente; obblighi, notice, tempistiche, identità, diritto di replica e pubblico intake richiedono decisioni qualificate. La route Correzioni è un **registro di record approvati**, non un portale di invio. |
| Estratti, citazioni, trascrizioni, audio/video e fonti terze | [`dp-305-excerpt-policy.md`](../policy/dp-305-excerpt-policy.md), Q-306-11/12/13 e [DP-307](../tickets/DP-307-qualified-legal-review-adr-policy-changes.md) | Decisioni su diritti **source-family/use specifiche** ancora OPEN; nessun consenso/licenza per ogni materiale deducibile dalla pubblicità della fonte o da Apache-2.0. |
| Revisione qualificata e firma owner | [DP-307](../tickets/DP-307-qualified-legal-review-adr-policy-changes.md), [DP-702](../tickets/DP-702-prelaunch-legal-security-privacy-review.md), Q-306-01..16 | DP-307 `FUTURE`, `BLOCKED`; reviewer qualificato, scope/giurisdizione, date, dispositions accettate, ADR e pubblico notice mancano. Un agente non può attribuirsi tale autorità. |
| Sicurezza e comunicazioni incidenti | [`SECURITY.md`](../../SECURITY.md), [`docs/ops/operator-runbook.md`](../ops/operator-runbook.md) | **Canale privato interno**: contattare l'owner tramite canale di accesso al repository. Il runbook specifica che email di sicurezza e canali pubblici sono decisioni pre-lancio: non è un contatto pubblico approvato. |
| Accessibilità e verifica del sito informativo | [DP-410](../tickets/DP-410-accessibility-performance-seo-acceptance.md), [`LAUNCH.md`](../../LAUNCH.md) | DP-410 `IN PROGRESS`: il sorgente, build e automazione non sostituiscono l'accettazione manuale/device richiesta dalla ticket. |

Il blocco editoriale è distinto dal blocco di pubblicazione del codice: [PRODUCT](../../PRODUCT.md), [ARCHITECTURE](../../ARCHITECTURE.md) e [DP-307](../tickets/DP-307-qualified-legal-review-adr-policy-changes.md) richiedono attribuzione e prove revisionate, legal/privacy/source-use per caso, autorizzazione editoriale e proiezione fail-closed. L'attuale owner quick-check visivo descritto in PRODUCT non è una firma di fact-checking testuale. Un build `index,follow` o la CI di branch non modifica queste condizioni.

## Mappa SOP / Skills / Rules / Operations / handoff

Queste etichette sono una **mappa delle superfici realmente esistenti**, non nomi di cartelle editoriali nuove o approvazioni equivalenti:

| Ambito | Percorso effettivo e ruolo | Confine |
| --- | --- | --- |
| SOP / procedure | [`docs/ops/operator-runbook.md`](../ops/operator-runbook.md), [`informational-preview-bundle-preflight-20261010.md`](../ops/informational-preview-bundle-preflight-20261010.md), [`docs/ops/`](../ops/) | Procedure operatore e prove di bundle; non policy di privacy per i visitatori e non licenza di pubblicare. Nessuna directory autonoma `SOP/` risulta nel repository. |
| Skills / agenti | Nel repository DP non risulta un `SKILL.md`; [DP-607](../tickets/DP-607-optional-sdk-mcp-skill.md) ha chiuso la decisione **NO-BUILD** per skill/SDK/MCP esterni v1. Le skill owner riutilizzabili stanno fuori da DP, in `/Users/domenico/.dstack/package/skills/`. | Le skill per l'esecuzione di agenti non costituiscono norme pubbliche né diritti, pareri o reviewers autorizzati. |
| Rules / governance | [`AGENTS.md`](../../AGENTS.md), [`GOVERNANCE.md`](../../GOVERNANCE.md), [`PRODUCT.md`](../../PRODUCT.md), [`CONTEXT.md`](../../CONTEXT.md), [`ARCHITECTURE.md`](../../ARCHITECTURE.md), [`docs/policy/`](../policy/), [`docs/adr/`](../adr/) | AGENTS governa operatori/agenti; registro legale e policy sono vincoli interni, non informativa pubblica firmata. |
| Operations / sicurezza | [`docs/ops/operator-runbook.md`](../ops/operator-runbook.md), [`SECURITY.md`](../../SECURITY.md), [`docs/ops/threat-model.md`](../ops/threat-model.md), [`docs/ops/retention-matrix.md`](../ops/retention-matrix.md) | Operatore incidenti MiniPC nominato a livello interno; canale pubblico e retention richiedono Q-306/DP-702. |
| Handoff e coordinate del lavoro | [`HANDOFF.md`](../../HANDOFF.md), [`2026-10-14-postconsolidation-handoff.md`](2026-10-14-postconsolidation-handoff.md), [`2026-10-14-all-lanes-consolidation-receipt.md`](2026-10-14-all-lanes-consolidation-receipt.md), più mandato/README ControlCenter 297 ai percorsi esterni sopra | Stato e provenienza del lavoro, subordinati alle specifiche/ticket; nessuna pagina web o prova legale nasce dall'handoff. |

## Confini della prova e azioni con autorità

1. **Sorgente accertato:** route/metodo/documenti enumerati sopra; assenza nel tree controllato delle route per Privacy/Termini/Contatti/Contribuisci; esistenza di registro legal/policy/runbook con blocchi espliciti. L'audit non ha interrogato MiniPC, CDN, DNS, mailbox pubbliche o qualifiche di professionisti.
2. **Per i testi pubblici obbligatori:** owner e consulente qualificato devono fissare entità responsabile, recapiti, canali, condizioni, basi privacy, termini, versioni e review datata per il profilo scelto (informativo o archivio). Registrare le disposizioni in Q-306 e DP-307, poi rifletterle nelle superfici approvate e nei ticket; **non** popolare dati presunti.
3. **Per dichiarazioni reali:** usare solo corpus e fonte con permesso verificato, attribuzione controllata, criteri evidenza/periodo, review e autorizzazione della singola proiezione. Solo dopo gli altri gate MiniPC/reader/API e rollback può confermare il materiale effettivamente esposto; il pilot [DP-443](../tickets/DP-443-first-integrated-source-reader-pilot.md) precede l'espansione massiva secondo [PLAN](../../PLAN.md).
4. **Per le sei pagine informative:** il loro scope è distinto dall'archivio; il [preflight](../ops/informational-preview-bundle-preflight-20261010.md), gli AC di privacy/legal/accessibilità/titolarità e il readback dell'host restano requisiti separati. Non usare `--bundle-only` come autorizzazione editoriale o deploy.

**Stato di questa consegna:** `INVENTORY_ONLY / NO_APPROVAL / NO_DEPLOY`. Solo questo documento è di proprietà della corsia DP02 inventory; nessun ticket, PLAN, handoff, policy, route, firma o stato di pubblicazione è stato alterato da questa nota.

## Verifica ripetuta sul checkpoint integratore `0eba7fb` e runbook DP-517

Una scansione reale `Path.exists()` di tutti i collegamenti Markdown relativi,
escludendo solo URL HTTP(S), `mailto` e ancore locali, ha verificato **117/117
destinazioni esistenti, 0 mancanti** nei seguenti sei artefatti: questo inventario
(68), ricevuta DP02 (2), handoff post-consolidamento (5), `HANDOFF.md` (41),
runbook operatore (1), runbook OIDC (0). Il controllo è **di esistenza del path**,
non prova che una SOP sia autorizzata o che un link host/CDN risponda 200.
Le coordinate del packet Ops 297 rimangono esterne al repository DP e sono
state verificate separatamente nel checkout ControlCenter.

Nel sorgente `web/src/pages/` risultano presenti `metodo.astro`,
`correzioni.astro`, `dati.astro` e `progetto.astro`; risultano **assenti**
`privacy.astro`, `termini.astro`, `contatti.astro`, `contribuisci.astro`.
Conseguentemente queste ultime quattro pagine **non possono essere
considerate complete o pubblicate**. Il loro contenuto vincolante attende
owner, Q-306 e revisione legale/privacy DP-304/307/702; non va sostituito da
titolarità, recapiti, diritti o promesse di retention inventate. Il controllo
Astro e la build demo opt-in non mutano questo risultato.

## 2026-10-14 — Quinta tranche: crosswalk rivalidato con documenti e lane Ops

Lo scanner dei link Markdown relativi è stato rieseguito **dopo** gli
aggiornamenti reali di `HANDOFF.md`, `PLAN.md`, ricevuta e post-handoff:
**138/138 link esistenti e 0 path mancanti** in sette file (questo
inventario 68; ricevuta DP02 5; postconsolidamento 9; HANDOFF 46;
operator-runbook 1; runbook OAuth 0; PLAN 9). I locator esterni nominati
esplicitamente sono stati verificati per esistenza nel Mac Studio:
`ControlCenter/.../297-handoff-restart-20261012/02-dichiarazioni-pubbliche.prompt.md`,
la sua `02-dichiarazioni-pubbliche.response.md` e la directory skills
`~/.dstack/package/skills/`. Questo prova navigabilità del checkout,
**non** semantica/approvazione delle SOP, autorizzazione delle Skills,
link pubblici HTTP, dati reali, CI PR, endpoint MiniPC o retention.
I file route `metodo`, `correzioni`, `dati`, `progetto` sono presenti;
`privacy`, `termini`, `contatti`, `contribuisci` sono **ancora assenti**.
Il registro Q-306/DP-304/307/701/702, le responsabilità/recapiti e i
diritti rimangono gate esterni. Non si è aggiunta alcuna pagina sostitutiva
o dichiarazione pubblica con approvazione fittizia.

## 2026-10-14 — Ottava tranche: dichiarazioni, privacy e crosswalk confermati

Sul source integratore `dfd178d3ae05cf3d11e8f6ec78f574902023e022`
restano realmente presenti le quattro route sorgente Metodo, Correzioni,
Dati/API e Progetto; non ci sono ancora `privacy.astro`, `termini.astro`,
`contatti.astro` o `contribuisci.astro`, né una dichiarazione reale con
ricevuta di diritti, reviewer e pubblicazione MiniPC attestata. Lo
Statement v3 e la parità backend/Astro testati sono solo fixture demo
esplicite e noindex, non contenuto autorizzato.

La [regressione DP-312](../tickets/DP-312-speech-act-context.md) mantiene
separata la citazione completa (`QUOTE/NON_COMMITTAL`) dall'endorsement
diretto su delimitatori CJK e occidentali; la sua full suite 3665/3665
appartiene allo SHA `4873a2f`. La [protezione account DP-517](../tickets/DP-517-reader-google-login.md)
ha ricevuto un ulteriore guard contro hardlink di SQLite/WAL/SHM e del
secret OAuth su `dfd178d`, con test locali 156/156, e il
[runbook OIDC](../release/account-oidc-activation.md) avverte che la
protezione non equivale a isolamento fisico/proxy certificato.

La scansione locale dei link Markdown relativi nei sette documenti correnti
è **153/153 destinazioni esistenti, zero mancanti** (inventario 76,
HANDOFF 49, PLAN 10, ricevuta di execution 5, postconsolidamento 12,
operator-runbook 1, runbook OIDC 0). È un controllo di esistenza dei path,
non un HTTP 200 o un'approvazione. I locator del mandato
e della risposta `02-dichiarazioni-pubbliche` nel packet ControlCenter 297
esistono e restano un riferimento esterno, non un'approvazione della release.
Le directory canoniche SOP (`docs/ops/`), Skills owner
(`~/.dstack/package/skills/`), Rules (`AGENTS.md`, `PRODUCT.md`, policy e ADR)
e Operations (operator-runbook, threat model, retention) continuano ad avere
ruoli distinti e nessuna fornisce di per sé diritti o consenso.

Il registro mantiene **162 ticket, 90 DONE, 72 non DONE**; preflight release
**NO-GO/49** per Q-306, artefatti e ticket di lancio. Nessuna pagina
Privacy/Termini/Contatti/Contribuisci è stata creata senza owner e legal,
nessun ticket con AC esterne è stato marcato DONE e nessun deploy avviato.
