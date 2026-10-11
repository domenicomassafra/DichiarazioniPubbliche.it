# Dichiarazioni Pubbliche — integrazione Git e code review 11 ottobre 2026

## Ambito verificato

- Host/repository: Mac Studio `/Users/domenico/Code/DichiarazioniPubbliche.it`.
- Base remota precedente: `ebdc4f83c8ab322bbad4529d0dca6b583409c912`.
- HEAD integrato e pubblicato: `f21c15ccf40028b4ba3b82291c584cf267b04b14`.
- Delta: 74 commit locali recuperati e poi inviati con `git push
  --porcelain origin main` **fast-forward, senza force**.
- Readback `git ls-remote origin refs/heads/main` esattamente
  `f21c15ccf40028b4ba3b82291c584cf267b04b14`.
- Working tree `main...origin/main` pulita, un solo worktree,
  nessun altro branch locale o stash.
- L'unico prompt2prompt storico rimasto fuori da Git è ora custodito
  nel commit `f21c15c`, non cancellato. I tre commit Git orfani sono
  conservati nei refs `refs/archive/dpub-20261011/*`; nessun reset
  o git-gc distruttivo.

## Code review — asse Standards

Baseline secondo `AGENTS.md`, `PRODUCT.md` e `ARCHITECTURE.md`;
identità dei byte della review `git diff
ebdc4f83c8ab322bbad4529d0dca6b583409c912...f21c15c |
git hash-object --stdin`:
`92e73b4f603629ae3cc01fea5af2c54c32d32764`.
Verificati manifest/permission boundaries, proiezione pubblica,
denominatori/benchmark, gate DP-443, checker ticket, configurazione CI
e i cambi nel range prima del push.

Controlli: `git diff --check` sull'intero range PASS;
repository contract, licensing/version e contributor acceptance PASS;
51 test mirati DP-235/321/443/repository PASS; verificati scanner
repo hygiene e assenza di file aggiunti con estensioni tipiche di
credenziali/DB/archivi.
In `public_projection.py` la validazione di bundle non è stata
eliminata: continua in `public_schema.validate_public_bundle`,
invocato col gate v3 esplicito. Nessuna rimozione verificata dei
vincoli di proiezione, no auto-publish o scorciatoia per diritti,
provider, pubblicazione.

**Esito Standards:** nessuna violazione deterministica ad alta
confidenza negli scope verificati, nessun refactor indiscriminato
di codice live. Non si afferma che 192 file siano stati ispezionati
manualmente riga per riga; lint/test/CI sono prove complementari e
non un audit privacy o di sicurezza esaustivo. La struttura source-only
separata dai runtime consumer è intenzionale.

## Code review — asse Specifiche e acceptance

Le specifiche `docs/tickets/DP-235*`, `DP-321*`, `DP-443*`
esigono proof/rights/gold/owner e MiniPC. La tranche aggiunge guard
locali falsificabili e test negativi senza trasformare l'esistenza
di descrittori o SHA dichiarati in prova:

- DP-235: manifest `HELD/PROPOSED` e dispatch non autorizzato;
  fonte/diritti esterni e Capture/Passage/MiniPC non provati.
- DP-321: denominatori astensione sull'intero manifest, scope digest
  su ammessi; gold/threshold esterni non accettati.
- DP-443: 20 slot positivi + cinque `HOLD` negativi, ma ogni
  valutazione è **NO-GO**, nessuna prova runtime o firma autenticata.

**Esito Spec:** implementazioni preparatorie coerenti con i
vincoli di non-pubblicazione; acceptance di live pilot, source rights,
independent gold, legal/privacy, owner approval e MiniPC ancora
**aperte**, non assimilabili a `DONE`.

## CI remoto e produzione

GitHub Actions workflow `ci`, run `38155719467` sul commit
`f21c15c`: **11 job su 11 `success`**, inclusi otto backend
Ubuntu/macOS per Python 3.11–3.14, clone pulito, repository contract
e web statica con projection boundary fail-closed. Il workflow
ha permessi contents read e **non esegue deploy**.

`check_launch_preflight.py --expect-no-go`:
**NO-GO, 49 blocker**;
receipt SHA256 `96fb7b178b371dcaac129496ba3f436a803ca063557f1e6a28be0d6346070c3f`.
La CI verde non approva fonte, copyright, privacy/legale,
Machine authority, independent gold né real MiniPC readback.
L'aggiornamento GitHub source **non** è una stable-v1 release,
un bulk storico o un cambiamento di servizio attivo.

## Ticket/issue

Backlog `PLAN.md`: 162 ticket, 90 DONE, 52 IN PROGRESS,
6 BLOCKED, 14 FUTURE, **72 non DONE**; status PLAN/ticket coerenti.
GitHub Issues pubblici: `gh issue list --state open` => 0
alla verifica. Le future chiusure dipendono dalle rispettive
acceptance e non da un reset globale di labels/stati.

## Pulizia selettiva Mac Studio — risultato verificato

Audit del worker dedicato con `lsof` senza reader, percorsi esatti,
ownership e sorgenti di reinstallazione prima di rimuovere 11 sole
directory rigenerabili: il clone temporaneo
`/private/tmp/dp422-clean-V4mxgTt8/repo/web/node_modules` e `.astro`,
`build`, `.ruff_cache`, `web/.astro` e sette cache Python
`__pycache__` del checkout autorevole.

- `df -Pk` immediatamente **prima**: used 407156540 KiB;
  available 45702980 KiB.
- `df -Pk` immediatamente **dopo**: used 406898336 KiB;
  available 45961184 KiB.
- **Delta osservato: 258204 KiB disponibili in più,
  264400896 byte = 252,15 MiB**. I blocchi allocati delle
  undici directory eliminati sono 267038720 byte. Su APFS i valori
  non devono necessariamente coincidere.
- Nessuna eliminazione di source, commit/archive refs, cache di
  evidenza privata, media, stato database, rollback o web/node_modules
  canonical (quest'ultimo conservato durante le verifiche).
- Il df hostwide successivo può fluttuare a causa di altre operazioni
  concorrenti: la misura causalmente attribuibile è solo la coppia
  immediata prima/dopo. Il worker ha verificato `git status` pulito
  e stesso HEAD/remote anche dopo la rimozione.

## Pulizia supplementare Mac Studio — frontend canonical

Dopo la **conclusione completa della CI remota**, verificati
`lsof +D` e i processi node/npm/astro/vite: nessun file aperto né
job frontend in esecuzione nella directory
`web/node_modules`. `web/package.json` e
`web/package-lock.json` presenti per un ripristino nativo.
Eliminata **solo** la directory rigenerabile exact-path tramite
`shutil.rmtree` con guard su symlink/path/Git worktree.

- `statvfs` immediato: disponibili prima **47603986432 byte**,
  dopo **47853379584 byte**, recupero **249393152 byte**.
- Nessun file Git modificato. In caso di nuovo lavoro frontend
  sul Mac Studio, rigenerare con `cd web && npm ci`. La
  distribuzione MiniPC non dipende dai pacchetti npm del Mac.

## Audit e pulizia degli altri tre computer

- **MacBook Air:** SSH raggiungibile; nessun checkout del progetto
  nei percorsi esaminati `~/Code`, `~/src`, `~/tmp`,
  `/tmp` e cache specifiche. Nessuna rimozione eseguita.
- **MateBook Linux / Omarchy:** SSH raggiungibile;
  stessi percorsi esaminati, nessun checkout e nessuna rimozione.
  L'alias MateBook Windows non era raggiungibile, quindi non si
  attribuisce copertura a quella partizione/sessione.
- **MiniPC `udodo`:** `/home/udodo/src/DichiarazioniPubbliche.it`
  è un **deploy mirror privo di .git**, non un branch/worktree.
  Checksum dry-run su tracked Studio rispetto al mirror:
  **304 file differenti o mancanti**, nessuna sincronizzazione
  effettuata. I quattro rollback rimangono protetti
  (281336/148/184/160 KiB) insieme allo stato privato.
  L'unica eliminazione riguarda
  `/home/udodo/src/DichiarazioniPubbliche.it/web/node_modules`,
  duplicato rigenerabile via `web/package-lock.json` dopo
  controllo processi, FD/cwd, `lsof`, link/mount, owner e service.
  `df` immediato: used 368746612 → 368496312 KiB,
  free 96335256 → 96585556 KiB:
  **250300 KiB = 256307200 byte recuperati**.
  Rimasti attivi il servizio web e cloudflared; GET
  `http://127.0.0.1:18090/` restituisce **HTTP 200**.
  `web/dist` è conservata.

**Recupero fisico osservato complessivo sulle due macchine
interessate: 770101248 byte ≈ 734,43 MiB ≈ 0,717 GiB**
(somma dei tre delta immediati delimitati).
Non si inventa un recupero di gigabyte: gli altri grandi
artefatti erano runtime/rollback, evidenza non rigenerabile
o dati di altri prodotti fuori dal mandato.

I servizi MiniPC funzionanti dimostrano continuità del sito
informativo esistente, NON la parità sorgente/runtime,
né un pilot editoriale o un nuovo deploy. Mantenuto
`NO-GO/49` per una release editoriale; le 304 differenze
tracked richiedono un successivo cutover esplicitamente
separato, con build pubblica da proiezione autorizzata,
readback API/DB, backup e rollback.
