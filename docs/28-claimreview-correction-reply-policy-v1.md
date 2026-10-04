# ClaimReview, Correction e Right-of-Reply Policy v1

Data: 2026-09-22.

## Obiettivo

Questa wave chiude due seam del read-model pubblico senza introdurre un nuovo
domain model o nuova infrastruttura:

1. projection JSON-LD interoperabile con Schema.org `ClaimReview`;
2. lifecycle fail-closed per right of reply e correction.

Restano separati i confini già stabiliti dal progetto:

**retrieval -> approval -> verification -> publication**.

Una replica o correzione esistente nel database operativo non diventa pubblica
per il solo fatto di esistere o perché un campo visibility è stato modificato.

## JSON-LD come projection

Il source of truth resta PostgreSQL. JSON-LD è generato sopra lo stesso
read-model pubblico fail-closed già usato per JSON e HTML.

Mapping v1:

- `ClaimReview` per il finding pubblicato;
- `Claim` per il claim atomico;
- `Person` per lo speaker esplicitamente approvato;
- `CreativeWork` per source appearance ed evidence;
- `Organization` per Dichiarazioni Pubbliche e publisher evidence;
- `citation` per gli URL evidence pubblicabili;
- `PropertyValue` per metadata metodologici bounded.

`reviewRating` espone soltanto:

`alternateName = assessment`

Non espone `ratingValue`, `bestRating`, `worstRating`, reliability score,
truth score o aggregati sulla persona.

`datePublished` deriva dal timestamp del `review_event` che ha approvato la
pubblicazione del finding, non dalla creazione del finding draft.

Output:

- `index.json`;
- `index.jsonld`;
- un JSON per **finding version**;
- un JSON-LD per **finding version**;
- un HTML statico per **finding version** con JSON-LD embedded.

Il filename è derivato dal finding ID, non dal claim ID: due versioni append-only
dello stesso claim non si sovrascrivono.

Nel JSON-LD embedded in HTML vengono escapati `<`, `>` e `&` come unicode
escape per evitare terminazioni/ambiguità del blocco script.

## Right of reply

Lifecycle operativo v1:

`PRIVATE/RECEIVED -> reanalysis linked/UNDER_REVIEW -> explicit publication review -> PUBLIC/PUBLISHED`

La registrazione:

- valida body e URL evidence;
- crea ID deterministico;
- mantiene la replica `PRIVATE`;
- accoda un trigger `RIGHT_OF_REPLY` per il claim;
- collega il job di reanalysis;
- porta la replica a `UNDER_REVIEW`.

La pubblicazione è un atto separato e atomico nel database:

- il finding collegato deve essere già pubblico e avere un proprio
  `review_event(entity_type=FINDING, action=APPROVED)`;
- `status = PUBLISHED`;
- `public_visibility = PUBLIC`;
- append-only `review_event(entity_type=RIGHT_OF_REPLY, action=APPROVED)`.

La projection pubblica riapplica difensivamente tutti e tre i requisiti:

- visibility `PUBLIC`;
- status `PUBLISHED`;
- review event `APPROVED`.

Un `UPDATE public_visibility='PUBLIC'` manuale, da solo, non rende pubblicabile
il body della replica.

## Correction

Una correction non modifica silenziosamente il finding precedente.

Per essere registrata deve esistere una catena valida:

- nuovo finding e finding precedente distinti;
- stesso claim;
- `new_finding.supersedes_id = previous_finding.id`.

La correction nasce `PRIVATE`.

La pubblicazione esplicita:

- richiede che sia il finding superseding sia il precedente abbiano già
  attraversato il proprio `FINDING APPROVED` publication gate;
- rende la correction `PUBLIC`;
- marca il finding precedente `CORRECTED`;
- scrive un `review_event(entity_type=CORRECTION, action=APPROVED)` nella stessa
  statement PostgreSQL.

La projection espone una correction soltanto se esiste anche quel review event.
La stessa correction viene collegata sia al dossier precedente sia al dossier
superseding per mantenere visibile la storia in entrambe le direzioni.

`previous_finding_id` non usa delete cascade: la history non deve sparire
accidentalmente per effetto della cancellazione di un record successivo.

## Fail-closed static bundle

Il public directory è una projection rigenerabile, non un artifact store
append-only.

Ad ogni generazione vengono rimossi i file `.json`, `.jsonld` e `.html` sotto
`claims/` che non appartengono più al dataset corrente. Questo evita che un
dossier diventato non-projectable resti raggiungibile come file stale.

In caso di crash è preferibile under-publication temporanea rispetto alla
persistenza di contenuto che non supera più i gate correnti.

Restano esclusi dal read-model pubblico:

- raw transcript;
- canonical transcript text;
- evidence body/excerpt;
- secret/provider detail;
- internal errors;
- person reliability/truth score.

## Migration

`db/migrations/20260922-add-correction-reply-policy.sql`

La migration estende il review ledger a `RIGHT_OF_REPLY` e `CORRECTION` e
vincola gli status ammessi per `right_of_reply`.

## Proof

Sul Mac:

- 163/163 test verdi;
- benchmark deterministico 5/5;
- `git diff --check` verde;
- compileall verde.

Su clone isolato del database reale MiniPC:

- migration applicata con `ON_ERROR_STOP`;
- 163/163 test verdi;
- benchmark deterministico 5/5;
- canary publication-gate SQL: reply/correction restituiscono `False` senza i
  `FINDING APPROVED`; dopo due finding publication review esplicite restituiscono
  `True`, con reply `PUBLISHED|PUBLIC`, correction `PUBLIC` e finding precedente
  `CORRECTED`;
- due finding version dello stesso claim esportate in file separati;
- JSON-LD senza rating numerici;
- nessun raw/canonical transcript text o evidence excerpt nel bundle;
- rimuovendo i review event di reply/correction dal clone, i dossier restano ma
  reply/correction pubbliche diventano 0 anche con visibility già PUBLIC.

Sul database/runtime production MiniPC:

- migration applicata con `ON_ERROR_STOP`;
- 163/163 test verdi;
- benchmark deterministico 5/5;
- residui del canary `correction-canary`: 0;
- queue tornata allo stato canonico: 11 `CLAIM_EXTRACT BLOCKED`, 9
  `TRANSCRIPT_ACQUIRE_ASR BLOCKED`, 11 caption completed, 11 canonicalize
  completed, 20 resolver completed e 0 `CLAIM_EXTRACT_WINDOW`;
- projection reale rigenerata in
  `/home/udodo/.local/share/dichiarazioni-pubbliche/public/v1`;
- `dossier_count = 0`, `omitted_count = 0`;
- `index.json` e `index.jsonld` mode `0600`;
- file sotto `claims/`: 0, quindi nessun dossier stale del canary;
- source-poll, worker e health timer ancora `active`.

Lo zero dossier è il risultato atteso: il database reale non contiene finding
non-sintetici che abbiano attraversato l'intero publication gate.

## Fuori scope di questa wave

Non chiude:

- endpoint pubblico di submission;
- autenticazione;
- anti-abuse/rate limiting;
- moderation UX;
- SLA legali o retention legale definitiva;
- final legal review;
- hosting/CDN/API pubblico finale.

Questi restano seam separati e non sono prerequisito per il contract interno
append-only/fail-closed qui definito.
