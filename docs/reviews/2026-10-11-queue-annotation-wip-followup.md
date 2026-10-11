# Dichiarazioni Pubbliche — ulteriore consolidamento Git e worker Python

Data: 11 ottobre 2026. Sorgente autorevole:
`/Users/domenico/Code/DichiarazioniPubbliche.it`, branch `main`.

## Ricognizione WIP, branch e worktree

- Baseline `main` e `origin/main`: `1d19075` all'inizio della tranche.
  Nel repository autorevole: **un worktree, un branch locale, nessuno stash**.
  I tre refs `refs/archive/dpub-20261011/*` rimangono intatti per
  conservare gli oggetti storici, non sono rami attivi da eliminare.
- Clone QA storico `/private/tmp/dp422-clean-V4mxgTt8/repo`: Git
  `main` pulito, HEAD `1e15db5`, già antenato di `main`
  canonico. Nessun altro branch/worktree, stash o oggetto irraggiungibile
  secondo `git fsck --full --no-reflogs --unreachable`; nessun
  lettore `lsof +D`; nessun collegamento simbolico. Rimossa solo
  la directory clone, preservato il file separato
  `/private/tmp/dp422-clean-V4mxgTt8/approved-empty.json`.
  `statvfs` immediato: disponibilità **43470385152 → 43509329920**
  byte, guadagno reale **38944768 byte** (~37,1 MiB).
- Inventario di 101 nomi temporanei `dp-*`/`dpub*` sotto
  `/private/tmp`: circa **0,045 GiB allocati** in tutto prima
  della rimozione. Screenshot, zip/capture e log potenzialmente
  unici o di supporto audit sono stati preservati; nessun guadagno
  da diversi GiB è dimostrabile in questo sottoinsieme.

## Debug e refactor circoscritto

Audit Ruff originario: **42 F821** (`Undefined name`) concentrati
nelle annotazioni di `queue_runtime.py`, `queue_store.py` e
`worker_handlers_claim_evidence.py`, `worker_handlers_transcript.py`,
`worker_handlers_verification.py`.

Difetto riprodotto **RED** con `typing.get_type_hints` su sette firme
di store/worker: `NameError: name 'Mapping' is not defined` e
`NameError: name 'ProcessingJob' is not defined`.
Gli import mancanti ora sono espliciti (`Mapping`,
`ProcessingJob`, `ContentRecord`) nei moduli responsabili;
le dipendenze provengono da `queue_runtime` e non creano una
nuova infrastruttura. Nessun percorso worker/provider o query SQL
è stato eseguito dal nuovo test.

- **GREEN**: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=poc
  python3 -B -m unittest tests.test_queue_annotation_resolvability -q`
  (due metodi test, sette subcase tipizzati).
- **GREEN**: `ruff check poc tests tools --select F821 --statistics`,
  zero errori F821 nell'albero Python.
- Rispettate le importazioni reexport legacy potenzialmente usate
  da altri moduli: non eliminare automaticamente i tre
  `F401` preesistenti nel gruppo runtime/store.
- **Suite Python integrata**: `PYTHONDONTWRITEBYTECODE=1
  PYTHONPATH=poc python3 -B -m unittest discover -s tests -q`:
  **2821/2821 PASS** in **224.140 secondi**, incluso restore
  drill `RESULT: PASS` (exit 0). Alcuni test mock HTTP emettono
  `ResourceWarning`/BrokenPipe, senza fallire la suite.
- Benchmark deterministico **5/5 PASS** e repository contract PASS;
  preflight editoriale **NO-GO/49** invariato.
- Ruff globale: da 162 errori iniziali a **120**. Eliminati
  i 42 F821; restano 120 rilievi storici
  (E402/F401/E701/E731/E702/F841), non dichiarati risolti.

## Release e limiti

L'incremento tocca annotazioni/import e test introspezione,
non DB/schema, API pubblica, diritti, decisioni editoriali o servizi.
Mantiene lo stato `NO-GO/49` della release editoriale finché
non siano soddisfatti i gate esterni. La CI del checkpoint
`1d19075` era **11/11 PASS**; la suite Python sopra riguarda
il nuovo codice prima del commit, non è un deploy editoriale.

Non sono stati rimossi backup, source/licensing proofs,
rollback MiniPC o altri prodotti. Il risultato di pulizia del
clone si somma alle tre misure attribuibili della tranche
precedente (770101248 byte) ma non si confonde con variazioni
globali APFS dovute a processi concorrenti.
