# UX prototypes v0

Tre direzioni volutamente diverse per **Dichiarazioni Pubbliche**:

1. `editorial.html` — newsroom/editoriale: contesto e leggibilità prima del grafo;
2. `evidence-graph.html` — provenance/evidence graph: relazioni e version history come oggetto principale;
3. `media-timeline.html` — media-first: claim track temporale + evidence drawer.

Avvio locale dalla root del repository:

```bash
python3 -m http.server 8765
```

Poi aprire:

- `http://127.0.0.1:8765/prototypes/ux-v0/editorial.html`
- `http://127.0.0.1:8765/prototypes/ux-v0/evidence-graph.html`
- `http://127.0.0.1:8765/prototypes/ux-v0/media-timeline.html`

## Dataset

`demo-data.js` deriva esclusivamente da metadata e stati già presenti nel repository:

- ContentAudit `raffagiulians-bollo-2026`;
- proof Pulp Podcast #64.

Il demo evita di ricopiare transcript integrali o media e non introduce nuovi finding. Gli identificatori, i conteggi, i tipi e gli stati sono sufficienti a testare la gerarchia dell'interfaccia.

## Guardrail condivisi

- nessun punteggio complessivo della persona;
- claim-level status, non person-level verdict;
- evidence e provenance sempre raggiungibili;
- prediction/opinion/motive-attribution distinguibili dai factual claim;
- history/correction/right-of-reply first-class;
- transcript e media non duplicati nel bundle del prototipo;
- Pulp mostrato come pipeline non conclusa: nessun finding inventato mentre claim extraction è bloccato.

## Cosa valutare

Il test successivo deve scegliere la struttura primaria del prodotto, non il colore finale del brand:

- velocità nel capire “cosa è stato detto e su quali prove si basa il finding”;
- facilità di aprire il contesto originale;
- visibilità di uncertainty e provenance;
- comprensione della dimensione temporale/versionata;
- comportamento mobile;
- rischio che l'interfaccia venga letta come scorecard politica.
