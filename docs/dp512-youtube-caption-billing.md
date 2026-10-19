# DP-512 — riconciliazione dei caption YouTube (19 ottobre 2026)

Decisione operativa per la issue [#30](https://github.com/domenicomassafra/DichiarazioniPubbliche.it/issues/30), commento dell'orchestratore del 19/10 alle 07:00 (ora di Roma). Questo è il contratto dell'accertamento tecnico dei receipt effettivamente osservati, non un'attestazione di fattura o un'autorizzazione a chiamate a pagamento.

## Canale attestato dal codice

Il writer canonico `poc/dichiarazioni_pubbliche/worker_handlers_transcript.py` registra `provider_id=youtube`, `model_id=NULL`, `operation=CAPTION_PROBE` oppure `CAPTION_CAPTURE`. `YouTubeResolver` in `platform_transcript.py` usa il comando locale `yt-dlp` con `--skip-download` per i metadati e `--write-subs`/`--write-auto-subs --sub-format json3` per le caption. Le chiamate usano la via di estrazione pubblica (`--ignore-config` per i nuovi tentativi); non invocano i metodi OAuth/API key della **YouTube Data API v3** e non invocano un modello LLM. Di conseguenza:

- Costo monetario marginale *del provider di caption* per questo specifico percorso: **0 USD**. Non è una voce fatturata o una misura del costo totale del servizio.
- Quota della **YouTube Data API v3** imputabile a questi tentativi: **0 unità**, perché nessuna richiesta viene eseguita a quella API. I rate limit tecnici di YouTube/yt-dlp rimangono distinti e non rappresentano unità di quota Data API v3.
- Energia locale: **UNKNOWN**, nessun Wh misurato e nessuna attribuzione EUR/FX.
- Nessuna classificazione `EXTERNAL_PLAN` (Google AI Pro/Antigravity non è coinvolto), `MEASURED_PROVIDER_COST` o quota LLM.

Fonti: codice sopra; documentazione ufficiale di [yt-dlp YouTube extractor](https://github.com/yt-dlp/yt-dlp/wiki/Extractors) e [opzioni yt-dlp](https://github.com/yt-dlp/yt-dlp#readme); [quota e ambito della YouTube Data API v3](https://developers.google.com/youtube/v3/getting-started).

## Ricevute storiche e controllo

I 63 receipt osservati nel PostgreSQL MiniPC erano 46 `CAPTION_PROBE` e 17 `CAPTION_CAPTURE`, tutti `ESTIMATED_ONLY`, stimati 0, senza `model_id`, importi misurati o riferimenti a fattura. Non si riscrivono le righe canoniche: preservarne base originale, tentativi e replay consente di distinguere la precedente stima priva di prova dalla **classificazione tecnica source-backed** di questa versione. Il report `youtube-caption-reconciliation-v1` porta versione dell'evidenza, fonte, numero e tipo dei tentativi, classificazione originale, assessment economico e incertezza energetica; viene ricavato dalle stesse righe in sola lettura. Qualsiasi provider/operazione/modello diverso, importo non nullo, base incompatibile, collisione di replay o token LLM fa fallire la classificazione. Una nuova versione di evidence va esplicitata nel codice e nel contratto; nessuna riga viene mutata per inferenza.

Comando di verifica nell'installazione MiniPC (output senza identificativi dei receipt):

```bash
PGDATABASE=dichiarazioni_pubbliche PYTHONPATH=poc python3 -m dichiarazioni_pubbliche.ops.youtube_caption_reconciliation_v1 --since 2026-09-01T00:00:00+02:00 --until 2026-10-20T00:00:00+02:00
```

Il gate è `status=SOURCE_BACKED_ZERO_PROVIDER_FEE`, `attempt_count=63`, `caption_probe_attempts=46`, `caption_capture_attempts=17`, `assessed_zero_provider_fee_attempts=63`, `unreconciled_youtube_caption_attempts=0`, `unmeasured_local_energy_attempts=63`. Il digest generale può continuare a mostrare le basi originali `ESTIMATED_ONLY`; non è un mismatch: il report separato è la rettifica valutativa versionata e non una migrazione dei dati protetti. Non riduce da solo i gate di budget per chiamate LLM a pagamento, non autentica fatture di provider diversi e non modifica il sito pubblico.
