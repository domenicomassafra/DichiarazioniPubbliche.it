# Speaker Provenance e Public Projection v1

Data: 2026-09-22.

## Obiettivo

Questa wave rende espliciti due confini:

1. una persona non diventa speaker di un claim per inferenza implicita;
2. il dataset pubblico non è un dump del database operativo.

Per contenuti audio/video la pipeline pubblica è:

**speaker candidate -> review/approval -> claim attribution -> verification -> publication review -> public projection**.

Per fonti scritte esiste anche il ramo:

**text provenance candidate -> review/approval -> claim attribution -> verification -> publication review -> public projection**.

Il secondo ramo non crea segmenti audio/video sintetici: conserva solo selector/hash e
metadati di attribuzione bounded, mentre il testo integrale della fonte resta fuori dal
read-model pubblico.

## Speaker identity senza biometria

Schema:

`speaker_identity_candidate`

Metodi ammessi:

- `MANUAL_REVIEW`;
- `SOURCE_METADATA`;
- `TRANSCRIPT_LABEL`;
- `PLATFORM_CREDIT`;
- `OFFICIAL_RECORD`.

Non sono ammessi in v1:

- face recognition;
- voiceprint / speaker embedding identification;
- biometric matching;
- “guess the speaker” via LLM.

Una candidate contiene:

- content/person ID;
- intervallo start/end;
- speaker label opzionale;
- attribution method/version;
- source_ref strutturato;
- confidence opzionale;
- status.

Ogni candidate nasce `CANDIDATE`.

## Approval speaker

L'approvazione è atomica:

- candidate -> `APPROVED`;
- append-only `review_event`;
- propagazione `speaker_person_id` ai canonical transcript segments coperti;
- upsert dell'appearance SPEAKER;
- propagazione al claim soltanto se **tutti** i suoi segmenti hanno una singola
  identità coerente.

Il gate rifiuta:

- span senza canonical segment;
- overlap con speaker APPROVED differente;
- segmenti già attribuiti a persona diversa.

Per una fonte scritta, la stessa funzione di attribuzione è svolta da una
`claim_text_provenance` approvata che deve riferirsi allo stesso claim, Content e Person.
Un claim pubblico deve avere almeno uno dei due canali di provenance; non è richiesto un
timestamp quando il contenuto sorgente non è temporale.

Quindi una partial attribution non può trasformarsi in una claim attribution
completa.

CLI:

`PYTHONPATH=poc python3 -m dichiarazioni_pubbliche.review_admin register-person ...`

`PYTHONPATH=poc python3 -m dichiarazioni_pubbliche.review_admin add-speaker-candidate ...`

`PYTHONPATH=poc python3 -m dichiarazioni_pubbliche.review_admin approve-speaker ...`

## Publication gate esplicito

Il deterministic verifier non pubblica.

La transizione `POLICY_HOLD -> PUBLISH` avviene soltanto tramite:

`review_admin publish-finding`

Il gate PostgreSQL richiede contemporaneamente:

- verification run presente;
- verification blockers vuoti;
- almeno un claim segment;
- nessun claim segment `publication_blocked`;
- almeno una evidence del finding;
- ogni evidence collegata al claim come `APPROVED`;
- ogni evidence con almeno una observation `APPROVED`;
- speaker person presente;
- ogni claim segment attribuito alla stessa persona;
- ogni segmento coperto da una speaker identity candidate `APPROVED`.

La transizione e il relativo `review_event` avvengono nella stessa statement
PostgreSQL.

## Public read projection

Implementazione:

`poc/dichiarazioni_pubbliche/public_projection.py`

La projection legge soltanto finding con status pubblico:

- `PUBLISH`;
- `DISPUTED`;
- `CORRECTED`;
- `RETRACTED`.

In più riapplica i guardrail di transcript, evidence, review event e speaker
provenance. Quindi un UPDATE manuale del solo `publication_status` non basta a
far comparire un dossier nell'export.

Output v1:

- `index.json`;
- un JSON per finding/dossier version;
- un HTML statico per finding/dossier version.

La wave successiva aggiunge `index.jsonld`, un JSON-LD per finding version e
JSON-LD embedded nell'HTML senza cambiare il domain model. Vedi
`docs/28-claimreview-correction-reply-policy-v1.md`.

Campi pubblici principali:

- normalized claim;
- claim type;
- persona/speaker pubblica e provenance candidate IDs;
- source URL/title/date;
- segment ID/index/start/end;
- finding assessment/rationale/policy/verification ID;
- evidence URL/publisher/date/hash/reference period/rights;
- correction history solo se `public_visibility=PUBLIC`;
- right of reply solo se `public_visibility=PUBLIC`.

Non espone:

- raw transcript;
- canonical transcript text;
- evidence body;
- evidence excerpt;
- provider secret;
- operational DB dump;
- internal error detail;
- person score / truth score.

## URL e HTML safety

Le URL pubbliche devono essere HTTP/HTTPS con hostname e senza userinfo.

Il renderer HTML fa escaping di claim, speaker, rationale, titolo e URL.

Le stringhe pubbliche sono bounded.

Un record non conforme viene omesso dal bundle invece di degradare i guardrail.

## Correzioni e right of reply

`correction` e `right_of_reply` hanno ora:

`public_visibility = PRIVATE | PUBLIC`

Default: **PRIVATE**.

Il fatto che una risposta o correzione esista nel DB operativo non implica che
il suo body venga esportato.

La policy v1 finale riapplica inoltre nel read-model il relativo
`review_event APPROVED`; per una replica richiede anche `status=PUBLISHED`.
Quindi `public_visibility=PUBLIC` da solo non è un publication gate.

## Runtime proof MiniPC

Canary sintetico end-to-end:

- person registrata come public figure;
- speaker candidate creata;
- claim inizialmente senza speaker;
- speaker candidate approvata;
- speaker propagato a canonical segment e claim;
- evidence + observation approvate;
- deterministic verification -> `SUPPORTED`;
- finding iniziale `POLICY_HOLD`;
- public projection pre-gate: claim assente;
- explicit publication review;
- public projection post-gate: claim presente;
- finding_evidence count: 1;
- bundle verificato senza `canonical_text`, `raw_text` o `excerpt`;
- synthetic DB/review residue: 0.
- regression baseline: 149/149 test verdi + benchmark deterministico 5/5 su Mac e MiniPC.
- production staging projection sul MiniPC: dossier_count 0, omitted_count 0, index.json mode 0600.
- wave successiva ClaimReview/correction policy: 161/161 test + benchmark 5/5 su Mac e MiniPC; production staging rigenerato con `index.jsonld` mode 0600 e zero dossier stale.

Questo è un canary di plumbing e policy, non un finding politico reale.

## Deployment philosophy

La projection è un read model generabile on demand.

Non richiede:

- nuovo database;
- Elasticsearch;
- graph DB;
- CMS;
- server-side rendering complesso.

Per il v1 può essere generata dal MiniPC e servita come file statici. Quando il
dataset crescerà, lo stesso contract potrà alimentare API/cache/CDN senza
cambiare il source of truth PostgreSQL.
