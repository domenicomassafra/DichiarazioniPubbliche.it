# Dichiarazioni Pubbliche — tranche implementativa dopo ricognizione (11 ottobre 2026)

**Perimetro:** fonte Git canonica Mac Studio, dopo `b4688c2`;
quattro lane operative autonome DP-235, DP-321, DP-443 e backlog/CI.
Nessun provider, crawling, nuovo contenuto, DB di produzione, MiniPC deploy,
push o pubblicazione; tutti i nuovi riferimenti di fonte e firma nei test
sono sintetici. Questo verbale non sostituisce la firma di release.

## Change-set verificabile

### DP-235 — bounded private source-to-candidate pilot

- In `bounded_private_pilot_manifest_v1.py`: blocco se mancano URL HTTPS,
  versione e SHA-256 della fonte, Content/persona/ruolo, lingua, media/MIME
  coerenti, scope esatto per eventuale riferimento `rights:<id>`.
  Accetta `HELD` per diritti assenti o attribuzione riportata/non
  identificata, `PROPOSED` solo per descrittori strutturalmente validi.
  Rifiuta duplicati logici/byte e record/manifests alterati, con limiti
  di otto campioni, quattro source family e budget dichiarato.
- Lo SHA atteso è **input dichiarato**: non prova byte originali catturati,
  permessi, licenze o identità. Nessuna esecuzione/autorizzazione del
  dispatch. Cinque AC restano aperte, ticket `IN PROGRESS`.
- Test unitarî mirati: **13 PASS**, compresi URL, source scope,
  speaker/reporting, budget, duplicati, forged dataclass e tamper detection.

### DP-321 — benchmark indipendente

- Corretto `_counts`: l'astensione osservabile e le predizioni mancanti
  contano sull'**intero manifest congelato**, anche quando un caso
  non è stato attestato esternamente. Le metriche semantiche
  (false attribution, verdict, rights) mantengono invece il solo
  denominatore degli eventi ammessi da reference indipendente.
- I confronti drift con lo stesso conteggio di casi ammessi ora richiedono
  lo **stesso set di case ID ammessi**, tramite digest di scope;
  report legacy privi di questa prova sono incomparabili, non promossi.
- Nessuna prova indipendente accettata, threshold approvata o gold reale
  è stata introdotta; nessun risultato è eleggibile al rilascio.
  `IN PROGRESS`, sei AC aperte.

### DP-443 — primo pilot completo

- Nuovo `first_integrated_pilot_readiness_v1.py`: raccolta locale
  limitata di fingerprint di un caso per source→Capture/Passage→original
  Statement→API/HTML/search/linked-data→correzione/revoca, MiniPC host/commit,
  venti categorie di receipt positive e cinque negative `HOLD`.
  Respinge omissioni, duplicati, incoerenza del manifest/lineage,
  host/readback errato, provenienza alterata e riuso di identità di firma
  nei ruoli indipendenti.
- Un pacchetto anche strutturalmente completo produce sempre
  **`NO-GO`, `scaling_authorized=False`**: non legge o verifica
  i receipt, non attesta le firme e non apre il gate DP-243/516.
  Questo è solo uno strumento preparatorio a una prova autentica
  su fonte autorizzata e MiniPC, non il pilot stesso.
- `FUTURE` e tutte e sette le AC restano aperte, coerentemente con
  l'assenza di manifest firmato e percorso reale.

### Contratto repository e milestone

- Il gate `tools/check_repository_contract.py --only tickets` include
  ora il confronto completo `PLAN.md` ↔ specifiche ticket tramite
  `ticket_snapshot`. Una divergenza non si nasconde più dietro un
  esito strutturale verde. Il test di regressione RED→GREEN falsifica
  lo scenario DP-235 FUTURE vs IN PROGRESS.
- Allineate le tre milestone divergenti senza cambiare status/AC:
  **DP-242 M4** (handoff Studio), **DP-243 M7** (archivio storico dopo
  pilot), **DP-244 M2** (inventario source coverage). Verificati
  **162/162** header milestone coerenti con PLAN.
- `README.md` distingue il precedente riepilogo 125-ticket dalla
  ledger attuale e rimanda a HANDOFF/PLAN/ticket come autorità.

## Accettazione e gate

- Stato backlog: **162 totali; 90 DONE, 52 IN PROGRESS, 6 BLOCKED,
  14 FUTURE, 72 non DONE**, senza avanzamenti cosmetici verso DONE.
- Il preflight locale atteso rimane **NO-GO / 49 blocker**. Non indica
  bug nuovo ma gate reali non ancora soddisfatti: Q-306/legal/rights,
  provider canary autorizzato, fonte reale e gold indipendente,
  machine authority, MiniPC DB/reader/correction/rollback, owner signoff.
- Anche dopo il piccolo percorso DP-443 occorreranno separatamente
  il corpus Garlasco 100 item DP-214, le tre famiglie produzione DP-703,
  rehearsal DP-704 e approvazione release DP-705.
- Scelta redesign owner DP-441 e screen reader manuale restano
  decisioni/acceptance esterne non simulate da test.

## Repro minimali

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=poc python3 -B -m unittest discover -s tests -p 'test_dp235_bounded_private_pilot_manifest.py' -q
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=poc python3 -B -m unittest discover -s tests -p 'test_dp321_independent_reference_benchmark.py' -q
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=poc python3 -B -m unittest discover -s tests -p 'test_dp443_first_integrated_pilot_readiness.py' -q
PYTHONDONTWRITEBYTECODE=1 python3 -B tools/report_ticket_status.py --json
PYTHONDONTWRITEBYTECODE=1 python3 -B tools/check_repository_contract.py
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=poc python3 -B -m dichiarazioni_pubbliche.benchmark
PYTHONDONTWRITEBYTECODE=1 python3 -B tools/check_launch_preflight.py --expect-no-go
git diff --check
```

I controlli sintetici non sono certificati come validazione host MiniPC o
pubblicazione.

## Checkpoint QA integrato del 11 ottobre

Tutti i test sotto sono stati eseguiti sul Mac Studio dopo aver stabilizzato
la tranche e **prima** di commit documentali conclusivi:

- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=poc python3 -B -m unittest
  discover -s tests -q`: **2819/2819 PASS** in **182.932 secondi**
  con restore drill integrato **PASS** e processo terminato exit 0.
- `PYTHONPATH=poc python3 -B -m dichiarazioni_pubbliche.benchmark`:
  **5/5 PASS**, fixture deterministicamente definite e NON gold reale.
- Test mirati su DP-235, DP-321, DP-443 e repository checker:
  **51/51 PASS** nell'esecuzione unificata.
- `ruff check` sui nuovi moduli e test DP-235/321/443, più il
  repository checker: **PASS**. `ruff format --check` sui sei
  source/test dei tre ticket: **PASS**.
- `npm run check` dal progetto web: **89 Astro file, 0 errors,
  0 warnings, 0 hints**; `check:statement`,
  `check:statement-parity`, `check:search` e
  `check:projection-boundary`: **PASS**, synthetic/opt-in/empty index.
- `check_repository_contract.py`, `report_ticket_status.py` e
  `git diff --check`: **PASS**.
- Launch preflight `--expect-no-go`: **NO-GO, 49 blocker**
  (`receipt_sha256=96fb7b178b371dcaac129496ba3f436a803ca063557f1e6a28be0d6346070c3f`).

Commit coerenti già creati localmente: `7fb263d`,
`30ce724`, `970191c`, `d72b47f`.
Restano soltanto da registrare il checkpoint documentale finale e
il readback della worktree; non vi è alcun permesso di push/deploy.
