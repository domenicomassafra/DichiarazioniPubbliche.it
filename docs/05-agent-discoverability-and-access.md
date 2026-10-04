# AI-agent Discoverability & Access

## Obiettivo

Il sito deve essere facile da consultare da ChatGPT, coding agent, research agent, assistenti personali, motori di ricerca e sistemi RAG.

L'utente dovrebbe poter chiedere al proprio agente di trovare tutte le dichiarazioni di una persona su un tema con le fonti, senza scraping fragile.

## V1 public read surface

- URL stabili per people, topics, claims, findings, sources e content.
- rappresentazione JSON degli oggetti chiave.
- JSON-LD con Schema.org Person, Claim, ClaimReview, CreativeWork e Organization.
- OpenAPI ufficiale.
- search endpoint con testo, persona, topic, data, tipo finding e source class.
- valutare llms.txt.
- sitemap separate.
- RSS/Atom feed di nuovi finding e correzioni.
- endpoint incrementale changes-since quando il volume lo richiederà.

## Citation contract

Ogni risposta API deve poter restituire claim id, quote/normalized claim, source URL, source date, access date, speaker, timestamp, evidence ids, finding version e policy version.

## MCP

Possibile ma non necessario in v1. Prima progettare una buona REST/JSON API; poi aggiungere wrapper MCP se utile.

Regola: MCP deve rimanere un adapter sottile sopra la stessa API pubblica, non un secondo dominio applicativo da mantenere.

## Skill/plugin

Possibile strato leggero: tool specification che interroga l'API pubblica e documentazione per agent builders.

## BYOK futuro

Preferire direct-to-provider/local key quando tecnicamente possibile: la chiave resta locale e il nostro server non la vede.

Server-mediated BYOK è più complesso per secret handling, logging, leakage e provider terms.

## Abbonamento con nostre API key

Possibile con trial, quota giornaliera/mensile, modelli low-cost di default, escalation a modelli forti, hard spending caps, abuse detection, queue e accounting.

## V1 policy

Nessun endpoint pubblico che consenta di consumare arbitrariamente i nostri modelli.

Gli utenti possono leggere, cercare, inviare una request e inviare rettifica, replica o fonte.

## External fact-check lookup

Prima di usare ricerca web costosa, interrogare anche nostro database, Google Fact Check Tools API e dataset ClaimReview esterni autorizzati.

Google Fact Check Tools:
https://developers.google.com/fact-check/tools/api/reference/rest

## llms.txt: optional, not foundational

Spec proposta:
https://github.com/AnswerDotAI/llms-txt

Può essere aggiunta come documentazione AI-friendly, ma il prodotto non deve dipendere dalla sua adozione. La discoverability principale deve venire da HTML pulito, JSON-LD, OpenAPI, sitemap e API stabili.
