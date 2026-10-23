# DP-244 — ciclo di aggiornamento osservato e Capture immutabili

Stato: implementato e provato su fonte HTTPS reale il 23/10/2026; **pubblicazione
non attivata**. Modulo: `poc/dichiarazioni_pubbliche/immutable_capture_store_v1.py`.
Canary riproducibile: `tools/dp244_refresh_cycle_canary.py`.
Issue: [#52](https://github.com/domenicomassafra/DichiarazioniPubbliche.it/issues/52).

## Cosa aggiunge

`dp244_conditional_probe` osserva e restituisce una ricevuta, ma dichiara
esplicitamente che la persistenza atomica spetta al chiamante: non esisteva
alcun archivio delle Capture. `immutable_capture_store_v1` è quella
persistenza, e nient'altro:

- **indirizzamento per contenuto**: il nome del file è lo SHA-256 dei byte,
  quindi lo stesso contenuto non può finire sotto due nomi e un corpo diverso
  non può sostituire una Capture esistente;
- **scrittura unica**: `O_CREAT | O_EXCL` più ricevuta in file `0600`; ripetere
  lo stesso corpo è una lettura idempotente del record esistente, mai una
  riscrittura, e un file corrotto viene segnalato, non riparato sul posto;
- **nessun metadato inventato**: lunghezza e digest sono misurati qui, il costo
  resta `None` (= sconosciuto) salvo misura esterna, `publication_authorized` è
  sempre `False`.

## Ciclo provato sul caso reale

Fonte: repository ufficiale `SenatoDellaRepubblica/AkomaNtosoBulkData`, documento
`Leg19/Atto00055187/resaula/01457617-ra.akn.xml`. Licenza letta dal `README.MD`
del commit (contiene `CC BY 4.0`) e attestata dal modulo DP-317: usi permessi
`FETCH` e `STORE_BODY`.

| Stadio | Osservazione reale | Esito |
| --- | --- | --- |
| baseline | `GET` 200, 393817 byte, ETag | `CHANGED` (prima versione nota), Capture immutabile `1cb2b5fc…` |
| unchanged | `GET` condizionale `If-None-Match` → **304**, 0 byte | `UNCHANGED`, nessuna nuova Capture, versione conservata |
| changed | seconda versione reale dello stesso documento (commit precedente), 394147 byte | `CHANGED` + proposta di revisione `SOURCE_REVALIDATION_REVIEW`, Capture immutabile `6afe4c8a…` |
| outage | `GET` su locator assente → **404** | `UNAVAILABLE` / `UNSUPPORTED_HTTP_STATUS`, nessuna Capture, backoff applicato |

Catalogo: 3 osservazioni versionate su un'unità con intervallo dichiarato
2025-06-01 → 2026-12-31, `delta_proposal=REVIEW_CHANGED_SOURCE`,
`state=STALE`, `COVERAGE_CHANGED_SOURCE_REANALYSIS_PENDING`,
`public_freshness_descriptor=None`, `dispatch_authorized=False`,
`enumeration_complete_within_scope=False` (assenza dati marcata esplicitamente),
`cost_micro_eur=None` (UNKNOWN). Con l'outage in coda lo stato resta `STALE`
con `COVERAGE_RECENT_ATTEMPT_UNVERIFIED`.

## Confini

Nessuna scrittura su database o sul mirror di servizio, nessuna pubblicazione,
nessun provider a pagamento, nessuna Capture promossa a corpus pubblico. Il
canary usa un archivio temporaneo locale: il collegamento all'archivio di
produzione e la revisione editoriale restano passi separati.

## Riproduzione

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=poc python3 -m unittest tests.test_dp244_coverage_catalog tests.test_source_coverage_report tests.test_dp244_immutable_capture_store -v
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=poc python3 tools/dp244_refresh_cycle_canary.py
```
