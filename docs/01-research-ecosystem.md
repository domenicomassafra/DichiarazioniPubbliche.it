# Research — Ecosistema esistente

Data ricognizione iniziale: 2026-09-21.

Non è emerso un progetto maturo che combini bene identity/person graph, timeline longitudinale, fact-check automatico, temporal contradiction detection, cambio di posizione, evidence provenance, right-of-reply, monitoraggio continuo e AI-native access.

La strategia migliore sembra comporre donor permissivi e costruire il temporal/evidence core originale.

## Loki / OpenFactVerification

Repo: https://github.com/Libr-AI/OpenFactVerification  
Licenza: MIT.

Fa long text -> individual claims, check-worthiness, query generation, evidence search/crawling e verification. Supporta string, text, speech, image e video ed è utilizzabile come library.

Per noi: ottimo donor per claim extraction e verification; non risolve nativamente il record temporale della stessa persona.

## Claim Polygraph NG

Repo: https://github.com/moshiur00/claim-polygraph-multi-agent-evidence-investigator  
Licenza: MIT.

Principio molto vicino al nostro: un verdetto AI da solo non basta; servono evidenza, provenance, controargomentazione, limiti, policy decisionale e review history.

Feature: multi-agent investigation, supporting/contradictory evidence, source-quality analysis, numerical verification, temporal verification, citation auditing e durable recovery.

Per noi: donor per pattern e implementazioni permissive. Progetto relativamente giovane: non assumerlo production-ready.

## Meedan Check

Repo: https://github.com/meedan/check

Piattaforma collaborativa per media annotation e fact-checking. Da studiare per media objects, search, annotation workflows, API, subservizi e UX. Troppo ampia da forkare alla cieca.

## Meedan Pender

Repo: https://github.com/meedan/pender  
Licenza: MIT.

URL parsing, metadata extraction, rendering e archiviazione. Supporta Archive.org e Perma.cc. Candidate source preservation service.

## Meedan Alegre

Repo: https://github.com/meedan/alegre  
Licenza: MIT.

Text/media analysis, NLP e similarity search. Possibile donor per matching, deduplica e precedenti simili.

## CIMPLE Knowledge Graph

Repo: https://github.com/CIMPLE-project/knowledge-base

Knowledge graph aggiornato continuamente che collega fact-checking con dataset sulla misinformation. Il progetto riporta 70+ fact-checking organizations e 200k+ documenti; usa RDF/linked data e documenta URI design.

Per noi: riferimento forte per evidence graph, URI canonici e interoperabilità.

Licenza: verificare puntualmente per ogni repo CIMPLE prima del riuso di codice.

## X/Twitter Community Notes

Repo: https://github.com/twitter/communitynotes  
Licenza: Apache-2.0.

Algoritmo e dati pubblici, scoring riproducibile e documentazione aperta. Non adottare consenso/community rating come verità; riutilizzare filosofia di auditabilità e riproducibilità.

## InTruth

Repo: https://github.com/rpanigrahi222/intruth-factcheck  
Licenza: custom non-commercial.

Feature: audio capture dal tab, transcription, check-worthy claim detection, evaluation, speaker attribution, context analysis, verdict labels e BYOK Anthropic.

La licenza consente uso personale, educativo e ricerca ma vieta commercial use, vendita, licensing o incorporazione in prodotto/servizio commerciale senza autorizzazione scritta.

Conseguenza: non incorporare codice nel nostro core commerciale senza permesso. Studiare comportamento e UX; per una feature equivalente usare specifica indipendente e implementazione clean-room.

## Open Parliament TV

Architettura: https://github.com/OpenParliamentTV/OpenParliamentTV-Architecture  
Organizzazione: https://github.com/OpenParliamentTV

Architettura CC0-1.0. Tool/platform GPL-3.0. Additional Data Service AGPL-3.0.

Pipeline interessante: parliament-specific fetch/parse/merge -> formato comune -> enrichment -> validation -> publishing.

Per noi: reference per normalizzazione di fonti parlamentari e speech/video alignment.

## Check-IT!

Repo: https://github.com/Jj-source/Check-It

Corpus di fact-check politici italiani.

Versioni documentate:

- d1: 2.706 articoli, basic info + partito;
- CheckIT!: 3.527 articoli, basic info;
- d3: 1.142 articoli, basic info + piattaforma.

Periodo: 2012-10-03 -> 2023-04-26.

Campi: titolo, data, link, statement, contenuto, autore della dichiarazione, verdict ed evidence text.

Accesso: su richiesta, con autorizzazione Pagella Politica.

Per noi: benchmark italiano, regression set e test extraction/alignment/classification.

## DisinfoMM

Dataset: https://huggingface.co/datasets/Syokan/DisinfoMM

Dataset multimodale/multilingue sulla disinformazione. La release attualmente descritta contiene 25.752 record complessivi, inclusa una componente Pagella Politica / italiana di 1.752 record. Include campi come claim, verdict originale/armonizzato, explanation, fact-check URL, declaration URL, evidence links, date, keyword e tag.

Per noi: ulteriore benchmark/dataset candidate per test multimodali e italiani. Licenze e provenienza dei singoli contenuti vanno controllate prima di ingestione o redistribuzione.

## Pagella Politica

Metodologia: https://pagellapolitica.it/progetto

Principi dichiarati utili: scegliere dichiarazioni fattualmente verificabili; citare dichiarazione e fonte; citare fonti dati; preferire fonti primarie; usare in genere almeno due fonti quando possibile; consentire replica e correzione.

Pagella Politica ha inoltre spiegato che i conteggi annuali non hanno valore statistico per stabilire quali politici siano più affidabili o raccontino più bugie. Questo supporta la scelta di non creare classifiche politiche aggregate.

## Ledsav/fact-checker

Repo: https://github.com/Ledsav/fact-checker  
Licenza: MIT.

Focus: database generation per politici italiani, scraping, processing, Parquet, Firebase e visualizzazione. Utile come donor tattico.

## Openpolis / Openparlamento

Repo: https://github.com/openpolis/openparlamento  
Licenza: GPLv3.

Legacy Symfony 1. Utile come reference concettuale e per identificare fonti/dati parlamentari, non come foundation moderna.

## Schema.org Claim / ClaimReview

https://schema.org/Claim  
https://schema.org/ClaimReview

Decisione: schema interno più ricco, ma mapping verso Claim e ClaimReview in JSON-LD.

## Reddit / feedback su InTruth

Thread:
https://www.reddit.com/r/ClaudeAI/comments/1u9esua/built_a_factchecker_that_catches_politicians/

Problemi emersi:

1. source bias;
2. context omission;
3. source repetition non equivale a proof;
4. who fact-checks the fact-checker;
5. source weighting trasparente e possibilmente deterministico;
6. LLM utile per candidate claim detection e synthesis, meno adatto a essere un oracolo autonomo.

Implicazioni: separare retrieval e verification; source independence; provenance; evidence support/contradict; challenger agent; policy deterministica; nessuna citazione non realmente fetchata.

## Conclusione

Strategia provvisoria:

- Pender: ingestion/preservation donor;
- Alegre: similarity donor;
- Loki: claim extraction/verifier donor;
- Claim Polygraph: evidence-governance/adversarial donor;
- CIMPLE: evidence graph reference;
- Community Notes: transparency/governance reference;
- Open Parliament TV: parliament/video pipeline reference;
- Check-IT!/Pagella Politica/Openpolis: Italia benchmark/data/methodology;
- InTruth: UX/BYOK/real-time behavior reference, non commercial-code donor.

Parte distintiva da costruire noi:

**temporal person/claim graph + contradiction engine + change-of-position reasoning + automated publication gate + continuous monitoring.**
