# DP-438 — Person pubblica autonoma, anche senza Statement

Status: FUTURE
Milestone: M4 — public product/API
Depends on: DP-105, DP-222, DP-402, DP-437

## Problem

DP-405.3 descrive Person pubblicamente approvata ma ancora priva di record; la proiezione corrente e il client estraggono le Person solo da Dossier con Finding, quindi tale pagina non esiste. Una persona che esiste soltanto nel database privato deve invece continuare a essere indistinguibile da un identificativo ignoto.

## Outcome

Una risorsa PublicPerson autonoma, con identity/publication review e stable public URI, che può avere zero PublicStatements e fornisce a DP-405 una cronologia effettiva quando ci sono registrazioni approvate; mantiene ruolo temporalmente valido, no score, no private roster leak.

## Traceability & constraints

R16/R20/R25/R36, DP-105/222/405; il vecchio DONE DP-105 prova il person-derived-from-dossier model, non una persona approvata senza finding. Non pubblicare qualsiasi Person ricercata solo perché in DB o nominata in una fonte. Approved roles intervals non sono automaticamente biografia esaustiva.

## Scope

Progetto di record PublicPerson con stable ID/slug, approved display name e identity disambiguator pubblico quando autorizzato, approved role intervals con source refs/valid_from/valid_to, public identity decision, version/status, privacy/sensitive policy refs, bounded profile scope e membership di statement IDs autonomi. Join dei PublicStatements solo dopo gate source/context/attribution; la cronologia deve distinguere emission_date vs pubblicazione/verified dates. La proiezione possiede un first-class people collection, mentre il vecchio algoritmo derivato da dossier è compatibilità v2 dichiarata. API/read/static pages/index consumano lo stesso set; zero-record approved Person produce empty state del record pubblico e link a Esplora/Metodo. Gli unknown, private, revoked e non-public Identity ID non appaiono e restituiscono uguale 404/generic unavailable.

## Non-goals

Database di persone mondiali, scraping CV/biografia privata, score, immagini non approvate, verifica biometrica e person-level verdict; Topic membership è DP-439 e non si deduce da nome nel testo.

## Dependencies and sequencing

Hard DP-105/222/402 e DP-437 dopo assegnazione del vero ID; B/A confermano speaker identity and approved time/context; D owns dataset release/caches. Soft DP-405/409/422 e DP-430 taxonomy; il nuovo schema deve essere predecessore del positivo AC-405.3 e non viceversa.

## Acceptance criteria

- [ ] `AC-438.1`: Person first-class approved ma con zero Statements produce route, API entry e approved empty state senza check/score/placeholder.
- [ ] `AC-438.2`: unknown/private-only/held/revoked Person non compare né come search suggestion/facet/cursor/sitemap e restituisce stesso boundary osservabile di sconosciuta.
- [ ] `AC-438.3`: Person con Statement e senza Finding è navigabile con fonte, original quote e data; claim-only/titolo fonte che cita il nome non ne fa un'affermazione della Persona.
- [ ] `AC-438.4`: dated role label si applica solo agli intervalli approvati che coprono statement time e con provenance; gli intervalli assenti/contraddittori non generano ruolo corrente inferito.
- [ ] `AC-438.5`: multilingua e due omonimi hanno stable IDs distinti; merge/split identity o role review revocato propaga ricostruzione e mantiene history solo quando pubblicabile.
- [ ] `AC-438.6`: repeat build di una Person unchanged produce stesso fingerprint/route; private membership changes non incidono in modo osservabile sul set pubblico salvo nuova decisione pubblicata.

## Validation / proof

Fixture matrix approved-zero, approved-one-opinion-no-Finding, multiple dated roles, two homonyms, one private-only/unknown collision, revocation, source quotation of person without endorsement; tests validator/API/search/static routes + no-private counts; MiniPC isolated readback approved zero Person vs unknown same response, real approved populated Person once eligible.

## Documentation, data, and migration impact

Additive public people collection with approved-vs-private identity discriminant; update public projection/API OpenAPI compatibility, search generation and canonical Person route; no auto-exposing legacy private people. Existing DP-405.3 remains unchecked until runtime proof.

## Completion receipt

Non implementato; pianificazione soltanto. Future schema replay, identity approval refs, public projection SHA, zero-record live Person and private/unknown negative evidence, rollback.
