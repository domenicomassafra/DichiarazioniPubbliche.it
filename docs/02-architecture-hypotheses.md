# Architecture Hypotheses

Ipotesi, non decisioni definitive di stack.

## Pipeline logica

1. Discovery — siti istituzionali, RSS, testate, social pubblici, YouTube, podcast, trasmissioni, archivi parlamentari, feed/API.
2. Acquisition — metadata e contenuto necessario.
3. Preservation — URL originale, data acquisizione, hash, snapshot/archivio ove consentito, canonical URL.
4. Normalization — article, video, audio, post, transcript e official document in oggetti comuni.
5. Identity resolution — persone, organizzazioni, partiti, ruoli, alias, account e incarichi nel tempo.
6. Speech/transcript processing — transcript, diarization, speaker attribution, timestamps e confidence.
7. Claim extraction — claim atomici e check-worthy.
8. Retrieval — fonti primarie, dataset ufficiali, atti, precedenti della persona, fact-check ed evidence neighborhood.
9. Verification — support, contradict, contextualize, supersede, insufficient.
10. Temporal contradiction engine — confronto con claim simili, posizioni passate, dichiarazioni retrospettive, azioni, promesse e previsioni.
11. Adversarial review — missing context, date mismatch, circular sources, attribution error, speaker error, stale data, quote truncation, irony, ambiguity e policy risk.
12. Deterministic policy gate — PUBLISH, PUBLISH_WITH_LIMITATIONS, UNRESOLVED, NEEDS_MORE_EVIDENCE, REJECT_ATTRIBUTION, REJECT_POLICY.
13. Publication — pagina web, JSON, JSON-LD, ClaimReview mapping, audit trail e citations.
14. Continuous re-evaluation — replica, nuove fonti, dati aggiornati, correzioni, errori di attribuzione.

## Storage

Source of truth suggerita: database relazionale con semantica graph.

Possibile: PostgreSQL, tabelle/edges espliciti, full-text e vector index. Non scegliere Neo4j, RDF o Postgres-only prima dell'audit CIMPLE e delle query reali.

Object storage per snapshot, transcript, metadata, documenti e derivati.

## Search

Separare ricerca deterministica, full-text, semantic/vector retrieval e graph traversal.

## RAG

RAG trova contesto, non è il database canonico. Ogni conclusione pubblicata deve puntare a evidence objects recuperabili.

## Cost control

1. deterministic filters;
2. cheap classifier;
3. small/cheap LLM per triage;
4. strong model solo sui candidati;
5. adversarial verifier solo sui finding seri;
6. caching e semantic neighborhood.

Mai confrontare ogni nuovo claim con l'intero corpus in prompt.

## Scheduling

Inizio: cron/system scheduler. A crescita: job queue, cadence per fonte e daily scanning per persone/fonti prioritarie.

## V1 API

Read-only pubblico: people, topics, claims, findings, sources, content e search.

Write controllato: request analysis, submit correction, submit source, right of reply.

Nessun endpoint pubblico v1 che invochi direttamente i nostri modelli.

