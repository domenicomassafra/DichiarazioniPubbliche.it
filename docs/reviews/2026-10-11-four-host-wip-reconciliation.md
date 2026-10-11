# Dichiarazioni Pubbliche — ricognizione WIP, Git e quattro host (2026-10-11)

**Stato:** ricognizione locale e remota in sola lettura; normali controlli QA
correttivi separati sul solo checkout autorevole. **NON** è un'autorizzazione
al deploy, alla pubblicazione, all'ingestione o a spese/provider.

## Autorità, perimetro e limiti

- **Sorgente Git canonica:** Mac Studio `mac-studio-dodo`,
  `/Users/domenico/Code/DichiarazioniPubbliche.it`.
- **Runtime autorevole:** MiniPC `udodo`, mirror
  `/home/udodo/src/DichiarazioniPubbliche.it`, **senza `.git`**.
- **Altri host SSH raggiunti:** MacBook Air `macbook-air-dodo`
  (alias `macbookair`) e MateBook Linux `matebooklinux`.
  Nei percorsi `~/Code`, `~/src` e nelle directory di progetto
  esplorate non risultano copie Git di DichiarazioniPubbliche.it né
  del precedente public-claims-italia. Questo non esclude copie su
  volumi non montati, path non enumerati o account diversi.
- **Alias alternativo `matebook`:** timeout SSH; non attestato.
  Non va equiparato a un quinto host accessibile né dichiarato
  verificato tramite il boot Linux.
- Tailscale lato Mac Studio segnala online MacBook Air, MateBook Linux e
  MiniPC; il peer Windows MateBook è offline. Handoff ControlCenter/nota
  Obsidian nei due laptop coincidono per hash con copie Mac Studio,
  ma sono snapshot storici (mtime 4 ottobre), non un nuovo checkout.
- Gli allegati e gli handoff del 10 ottobre sono **storia**, non autorità
  per HEAD, stato ticket, database, pubblicazione o licenze al 11 ottobre.

## Fotografia Git prima delle correzioni QA locali

| Aspetto | Evidenza |
|---|---|
| Mac Studio / branch | `main` su `725ac0fe798b4d3857a8c12a51dbfee79d731f0d` (2026-10-11 12:17 CEST) |
| GitHub `origin/main` | `ebdc4f83c8ab322bbad4529d0dca6b583409c912`, verificato anche con `git ls-remote` non mutante |
| Differenza | 66 commit solo locali (+66/-0); 185 file toccati, di cui 110 aggiunti e 75 modificati |
| Branch / worktree / stash | una branch locale `main`, una worktree, stash vuoto, nessun merge/rebase/cherry-pick in corso |
| Tracked dirty | nessun file tracciato sporco alla ricognizione |
| Untracked preservato | `tasks/prompt2prompt/20261010-231757-backlog-post-grilling/lane-01-backlog-master/001-backlog-master.response.md` (11.025 byte) |
| Altri beni fuori Git | 3 file sorgente/evidenza ignorati sotto `poc/content/raffagiulians-bollo-2026/raw/` (circa 44 KB) |
| Backup nascosto Git | `.git/worker17-web-backup-20261010` (circa 420 KB: archivio, patch, immagini, checksum) |

### Oggetti non raggiungibili: **non fare `git gc` / `git prune`**

`git fsck --full --no-reflogs --unreachable` ha rilevato
**3 commit, 8 tree, 55 blob**. I commit sono:

- `30c3c895` — lane Ollama/ASR locale; patch diversa dai commit raggiungibili
  correlati.
- `53076941` — governance fonti/provider/rollback Wave 26; patch diversa
  dal commit correlato raggiungibile `f0357ba`.
- `2f594812` — contesto brand; patch-id identica al commit raggiungibile
  `fad9189`, dunque non va trattata come nuova feature da applicare.

I primi due richiedono un confronto hunk-per-hunk prima di dichiarare recuperato
ogni frammento. Conservare gli oggetti e l'eventuale backup **senza**
creare branch/merge o eliminare artefatti automaticamente.

**Confronto supplementare, stesso giorno:** la differenza dell'oggetto
`30c3c895` rispetto al successivo reachable `1e15db5` nel
`local_claim_ollama.py` è la rimozione del segnaposto
`LOCAL_NO_REMOTE_KEY` a favore di una stringa vuota, con commento che
chiarisce che il trasporto locale non manda credenziali: il comportamento
successivo risulta più sicuro e non va ripristinato quello dell'orfano.
Il diff tra l'oggetto `53076941` e il successivo `f0357ba`
consiste in 27 righe di inventario fixture e 15 righe di generatore
aggiunte/modificate nel commit successivo, non in un file di esecuzione
perso. La terza patch brand è già identical per patch-id. **Non sono
state trovate patch orfane da applicare alla cieca**, e tutti gli
oggetti sono conservati sotto ref dedicati per eventuali verifiche
successive.

**Preservazione attiva eseguita dopo l'audit:** creati tre ref di sola
conservazione `refs/archive/dpub-20261011/orphan-{ollama-30c3c895,
ops-53076941,brand-2f594812}` mediante `git update-ref`
con old OID zero (create-only). Sono ref locali, non nuovi branch,
non spostano `main` e non sono stati pubblicati. Non eliminarli fino
alla revisione dettagliata delle due patch non equivalenti.

## MiniPC — fotografia runtime distinta dalla storia Git

- Mirror attivo: circa 279 MB, non repository Git.
- Quattro rollback conservati:
  `~udodo/src/.dpub-rollback-20261010-pre-e345911` (275 MB),
  `.dpub-backend-rollback-20261010-pre-b3fd56a` (148 KB),
  `.dpub-dp415-rollback-20261010-pre-54c906c` (184 KB) e
  `.dpub-dp417-rollback-20261010-pre-830f9a` (160 KB).
- `python3 tools/check_minipc_mirror_parity.py` ha verificato 688
  percorsi runtime tracciati: **527 MATCH, 57 DRIFT, 104 MISSING,
  0 STALE_REMOTE, 0 UNSAFE_PATH** rispetto al HEAD Mac ante-correzione.
  Tutti i 161 non-match erano compresi nei file modificati dalla storia
  Git dopo l'ultimo sync storico `ea63db0`: zero differenze inattese
  *nel perimetro controllato*.
- Un secondo controllo checksum `rsync -rnic --delete` (**dry-run**,
  nessuna cancellazione) su un perimetro più ampio, esclusi
  `.git`, cache, env, build, DB e dati, ha rilevato
  **169 file solo Mac Studio, 126 condivisi ma diversi, 0 solo MiniPC**.
  I due conteggi NON vanno sommati: esaminano insiemi di file differenti.
- **Liveness, non release:** sul MiniPC i servizi user systemd
  `omniroute`, `cloudflared-dichiarazioni-pubbliche` e
  `dichiarazioni-pubbliche-web` risultavano `ACTIVE/RUNNING`;
  i cinque timer worker/source-poll/daily/health/edge-guard erano
  `ACTIVE` con trigger osservati il giorno 11 ottobre. Questo non
  dimostra un canary riuscito né quale commit sia effettivamente in uso.
- La pagina `web/dist/index.html` installata sul MiniPC ha SHA-256
  `60e76f42a138b8a5fde390cee1c21c8b2053ee3f661c7a3ef78f49aebe49a1b0`,
  mtime 8 ottobre, ed è compatibile con il precedente receipt:
  **il frontend statico è vecchio rispetto al nuovo codice sorgente**.
  Il Mac Studio non conserva una copia `web/dist/index.html` confrontabile.
- Nessun `*.rej`, `*.orig`, `*.bak`, `*.patch`, `*.tmp` o nome
  `*wip*` trovato nelle directory `poc/tools/tests` verificate
  sul MiniPC; la ricerca non copre indiscriminatamente DB, dati o volumi.

**Decisione operativa:** non sincronizzare in massa il mirror e non
utilizzare l'opzione `--delete`. Il mirror può avere configurazione e
data-plane locale intenzionalmente diversi. La parità dei sorgenti
non implica runtime acceptance, aggiornamento DB, diritti o rilascio.

## Backlog / test / release — differenze effettive

Il `PLAN.md` ante-correzione contava **162 ticket:
90 DONE / 51 IN PROGRESS / 6 BLOCKED / 15 FUTURE**. Il file
`docs/tickets/DP-235-bounded-multi-source-private-pilot.md` indicava
invece `IN PROGRESS` dopo il commit `725ac0f`, a fronte
di `FUTURE` in PLAN: `report_ticket_status.py` e il test
`test_ticket_status` fallivano. La normalizzazione locale porta i
conteggi a **90 DONE / 52 IN PROGRESS / 6 BLOCKED / 14 FUTURE**,
sempre **72 non DONE**; nessuna acceptance DP-235 è stata chiusa.

Ulteriori differenze documentali non ancora normalizzate:

- milestone DP-242: M2 in PLAN / M4 nell'header ticket;
  DP-243 e DP-244: M2 in PLAN / M7 negli header;
- DP-423..428 hanno DONE con 4–6 AC non spuntate ciascuno,
  DP-433 un'AC futura condizionale non spuntata: riesame dei
  receipt/checkmark prima di modificare DONE;
- README conserva il conteggio storico 125 ticket; HANDOFF riporta
  l'ottava tranche al commit `4e1b49f`, precedente a `725ac0f`.

### DP-235 — limite dell'ultimo commit

Il nuovo `bounded_private_pilot_manifest_v1.py` e tre test dimostrano
un ordinamento/hash privato e un rifiuto del dispatch. **Non** attestano
rights di una fonte vera, una versione/locator, persone/ruoli, formati
ammessi, cardinalità, dedup Content, DB o MiniPC. In particolare erano
accettati `rights_reference=None`, metadati sconosciuti e stesso
`content_id` sotto sample ID diversi. Non inventare approvazioni.

Prima della correzione, il HEAD aveva anche **10 finding Ruff**
sui nuovi file e un test CI rotto dalla divergenza PLAN/ticket.
Il checkpoint storico **2789/2789 Python PASS** appartiene a una tranche
precedente e non certifica il nuovo HEAD.

### Stabilizzazione QA effettuata dopo la ricognizione

Interventi circoscritti: `PLAN.md` DP-235 passa a `IN PROGRESS`,
la ricevuta del ticket descrive il prototipo senza sovrastimare i
controlli, le importazioni dei test sono esplicite e i due nuovi
file Python sono formattati. Nessun diritto, capacità di dispatch,
provider, contenuto pubblico, checkpoint runtime o AC viene inventato.

- `report_ticket_status.py --json`: **162, 90 DONE, 52 IN PROGRESS,
  6 BLOCKED, 14 FUTURE; files_agree_with_plan=true**.
- `PYTHONPATH=poc python3 -B -m unittest discover -s tests -q`:
  **2792/2792 PASS**, 156.862 secondi, restore drill PASS.
- Tre test mirati DP-235 e tre `test_ticket_status`: PASS.
- Benchmark deterministico sintetico: **5/5 PASS**.
- `check_repository_contract.py`: PASS; `git diff --check`: PASS.
- `ruff check` e `ruff format --check` sui due nuovi file DP-235:
  PASS. Il controllo Ruff molto più ampio `poc tests tools`
  segnalava **162 finding esterni ai due file**, quindi **non**
  si certifica lint globale.
- Launch-preflight: **NO-GO/49** invariato, come richiesto dai gate.

Questi test locali NON sostituiscono le prove del MiniPC o le firme
editoriali e legali. La sincronizzazione completa del mirror non è
stata tentata.

**Verifica aggiuntiva del 11 ottobre, precedente alla successiva tranche
di implementazione:** nel checkout `web`, `npm run check`
ha esaminato 89 file Astro con 0 errori, 0 warning e 0 hint;
`check:statement`, `check:statement-parity`,
`check:search` e `check:projection-boundary`
sono PASS. Sono controlli sintetici su consumer/indice/isolamento
della proiezione: non dimostrano una release pubblica su dati approvati.

### Gate di prodotto non superati

- `check_launch_preflight.py --expect-no-go`: **NO-GO / 49 blocker**.
- Sei ticket BLOCKED: DP-201/202/203 (OmniRoute), DP-204 (ASR remoto),
  DP-406 (dossier Tema), DP-408 (traccia/relation).
- Diritti/fonti e review qualificata DP-236/317/307/702, 16 questioni
  Q-306, gold indipendente DP-321 e autorità DP-316 restano gate reali.
- DP-443 (prima fonte autentica autorizzata fino al reader,
  correzione/revoca/rollback e readback MiniPC) è FUTURE con **7 AC
  aperte**. Prima di averne un GO-for-scaling firmato, non avviare
  bulk DP-243/516. Garlasco 100 item DP-214, tre famiglie DP-703 e
  release DP-705 sono accettazioni distinte.
- La scelta visuale resta dell'owner DP-441; l'accessibilità
  con screen reader reale e la prova sul sito non sono sostituite
  da fixture/Chrome.

## Ordine di ripresa sicuro

1. **Preservare** `.git`, i tre ref archivio e i due commit
   orfani potenzialmente unici,
   backup `worker17`, untracked Prompt2Prompt, tre file raw ignorati e
   rollback MiniPC. Documentare eventuali nuove copie prima di ripulirle.
2. **Stabilizzare la baseline Mac Studio:** allineare stato DP-235,
   documentare fedelmente il prototipo, ripristinare lint e test CI;
   rieseguire suite e verifiche sul commit risultante.
3. **Riconciliare le anomalie documentali residue** (milestone
   DP-242/243/244, AC DONE, README/HANDOFF) soltanto con ricevute
   corrispondenti, senza falsi passaggi a DONE.
4. **Non distribuire** automaticamente i 66 commit di sviluppo sul
   MiniPC: approvare diff, source/prod safety, costi, rights, test e
   rollback per la singola release; preservare la separazione tra
   codice, DB, contenuti e sito statico.
5. **Ripresa funzionale vera:** chiudere i gate di fonte/diritti e
   preparare un piccolo pilot DP-235→DP-443 consentito e verificabile
   su MiniPC, con negativi, metrica gold indipendente e correzione.
   Il redesign e i batch storici vengono dopo i rispettivi gate.
6. **Follow-up accesso:** verificare a parte l'alias MateBook inattivo,
   volumi eventualmente non montati e possibili checkout fuori dalle
   directory esaminate; non dichiarare queste superfici controllate.

## Comandi di prova (tutti eseguiti senza push/deploy)

```bash
git status --short --branch
git branch -avv
git worktree list --porcelain
git stash list
git fsck --full --no-reflogs --unreachable
git ls-remote origin refs/heads/main
python3 tools/check_minipc_mirror_parity.py
python3 tools/report_ticket_status.py --json
python3 tools/check_launch_preflight.py --expect-no-go
git diff --check
```

L'inventario è un readback per i path e i controlli descritti, non una
garanzia di aver ispezionato ogni byte dei quattro dischi. Nulla in
questa review costituisce autorizzazione a modificare produzione.
