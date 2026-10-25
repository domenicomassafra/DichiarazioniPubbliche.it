# #329 — DVNS MCP → Evidence privata (25 ottobre 2026)

## Fonte, entitlement e scopo esatto

- DVNS upstream: `Italian-Builders-Org/DoveVannoINostriSoldi`, revisione `da54b73a6a30bae310fb43776b45950424d5daa9` verificata il 25/10/2026; contratto MCP ufficiale `docs/MCP.md`, blob GitHub `448d2669a432aa03273ba050f9361d2efb19cabc`.
- Accesso MCP dichiarato pubblicamente **senza autenticazione**, solo tool di lettura `list_datasets` e `query_dataset`: <https://www.dovevannoinostrisoldi.com/api/mcp>. Prova HTTPS Mac Studio: `POST tools/call query_dataset({"dataset":"opencoesione_progetti"})` → HTTP 200, `text/event-stream`, una risposta JSON-RPC `ok=true`.
- Dataset OpenCoesione: un solo aggregato nazionale per tema `ricerca-e-innovazione` e metrica `projects` con URL primario <https://opencoesione.gov.it/it/api/aggregati/temi/ricerca-e-innovazione> (HEAD 200 il 25/10). DVNS è **fonte aggregata secondaria**, non autorità primaria, non una licenza generale su altri dataset e non un permesso a usarne codice AGPL.
- Licenza della fonte originale: <https://opencoesione.gov.it/it/licenza/> osservata su HTTPS il 25/10: nota di riuso **CC BY 4.0**, salvo eccezioni, con attribuzione alla fonte e URL. SHA-256 dell'HTML ufficiale letto: `84bd780b0a6d975932af3d5d6ec952830f00120dd8d7496527d92d3f988d421a`. Metadati DVNS `source.owner=Dipartimento per le Politiche di Coesione`, `source.license=CC BY 4.0`, `source.endpoint=https://opencoesione.gov.it/it/api/aggregati/`. La verifica del notice avviene su host ufficiale con redirect negati; se cambia e non è rivalutata, il gate va in HOLD.
- Riscontro della **fonte primaria corrente** via `GET` HTTPS limitato a un aggregato: 25/10/2026, HTTP 200 JSON, `data_aggiornamento=20260630`, `aggregati.totali.progetti=46437`. Il payload derivato DVNS dichiara invece `referenceDate=2026-04-30` e `projects=46402`, `generatedAt=2026-08-20`. È una differenza temporale verificabile, non un errore di trasporto né il valore corrente. Il bridge memorizza il digest/versione primaria letta direttamente e segnala `dvns_snapshot_superseded=true`; la Evidence derivata è `record_status=SUPERSEDED`, osservazione **solo CANDIDATE**, senza promozione a fact-check. Se un payload DVNS dichiara la stessa data della fonte primaria ma valore discordante, o una data più recente della fonte primaria, la scrittura va in HOLD.
- Grant tecnico privato, fonte specifica e con scadenza a 30 giorni: rights subject `DVNS_OPENCOESIONE_AGGREGATES` + **URL primario esatto**, policy `dp329-dvns-opencoesione-private-v1`, use `FETCH` + `STORE_BODY` (quest'ultimo copre la sola memorizzazione del valore normalizzato), attribuzione e link di licenza obbligatori, reviewer tecnico macchina. Il registro append-only del progetto è il controllo corrente; revoca, scadenza, policy, receipt o URL discordanti impediscono nuove scritture. La valutazione tecnica della licenza è limitata all'aggregato già pubblico, non delega all'automatismo approvazione editoriale/pubblica.

## Mapping e consumer

`poc/dichiarazioni_pubbliche/dvns_mcp_private_evidence.py` legge con POST tipizzato, GET ufficiale limitato allo stesso tema, timeout 15 s, limite 150 kB, URL fissi, senza credenziali, redirect o scansioni. Accetta soltanto `data.schemaVersion=1`, `scope=national-overview`, fonte/tema/date coerenti; produce una singola riga nel contratto `dvns-style-readonly-evidence-v1`, un `source_version=sha256:<hash JSON canonico dei dati dello snapshot>`, `source_record_id=opencoesione_progetti:themes:ricerca-e-innovazione`, selector esatto `$.data.themes[0].projects`, `referenceDate` e timestamp di ricezione. **`generatedAt` è la generazione dello snapshot derivato**, non la pubblicazione originale dell'aggregato: resta distinguibile nel metadata `publication_date_is_downstream_snapshot_generation`.

La fonte compare nel registro e in DP-215 con ruolo `SECONDARY_REFERENCE`, mai `PRIMARY_RECORD`. La compatibilità DP-215 è richiesta prima del write. Le API esistenti `QueueRuntimeStore.upsert_evidence`, `insert_evidence_observation` registrano identificativi content-addressed, digest, diritti correnti, field provenance e review fingerprint in `evidence` + `evidence_observation.status=CANDIDATE`; nessun claim link, Finding, Statement pubblico o approvazione nasce dall'operazione.

Consumer sul MiniPC con PostgreSQL locale autenticato come utente Unix `udodo`:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 tools/dp329_dvns_private_evidence.py --database-url dichiarazioni_pubbliche
PYTHONDONTWRITEBYTECODE=1 python3 tools/dp329_dvns_private_evidence.py --database-url dichiarazioni_pubbliche --apply-private-evidence
```

Senza `--apply-private-evidence` il primo comando è lettura + preflight e, senza record valido, restituisce `HOLD` senza DB write. L'apply crea il grant solo dopo verifica della nota ufficiale, ripete i controlli prima di persistere e rileggere Evidence/Observation tramite l'utente PostgreSQL del consumer. La query di readback vincola ID, metric, URL, record, valore, stato e selector. La prova negativa deve impedire la scrittura in caso di `SOURCE_USE_REVOKED`, `SOURCE_USE_EXPIRED`, `SOURCE_USE_NOT_PERMITTED`, policy/receipt divergente, schema/fonte/payload invalido o errore MCP.

## Regressioni

Mac Studio, tramite `workload_launcher.py --max-wait 300 build --`:

- `tests.test_dvns_source_suitability tests.test_dvns_official_source_probe`: **20 test PASS**; compresi gli HOLD precedenti Senato.
- `tests.test_dvns_mcp_private_evidence`: **7 test PASS**; mapping, SSE MCP, errore remoto, licenza negativa, versione originale, differenza snapshot ufficiale, contraddizione temporale/valore, permessi assenti/scaduti/revocati e scrittura candidata in memoria.
- `tests.test_repository_contract`: **8 test PASS**.
- `tests.test_source_intelligence tests.test_source_intelligence_schema`: **38 test PASS**.

Preflight sul MiniPC autenticato (`udodo` PostgreSQL peer, DB `dichiarazioni_pubbliche`) con il codice candidato: **HOLD**, exit `2`, `written=false`, `DVNS_MCP_CURRENT_LICENCE_RIGHTS_REQUIRED`, quando il registro conteneva **zero** grant DVNS. Il prossimo passaggio dopo il merge è la ricevuta positiva del MiniPC, con SHA del codice distribuito e stato del record, conservando intatto il deployment pubblico.
