# DichiarazioniPubbliche.it — consolidamento tecnico e pulizia controllata, 14 ottobre 2026

**Natura della prova:** receipt Git e test locali; NON approvazione di fonti, diritti, fatti, editoriale, MiniPC, CDN, deploy o produzione.

## Stato verificato prima di questo follow-up documentale

- Repo canonico Mac Studio `/Users/domenico/Code/DichiarazioniPubbliche.it`, `main == origin/main` **`33b4590e37a06b0ee31ceb1a2c4ef6ae4f7296fe`** e checkout pulito.
- Integratore `integrate/dp-20261014-all-lanes` **`28f57c4cdbe9a363a2b35d30647535ea4e6002f3`**: **11 merge Git reali**, tutte le teste sorgente incluse come antenate, 70 file cambiati, `git diff --check` PASS e nessun marker di conflitto nei ticket; la sovrapposizione delle ricevute nei ticket DP-314, DP-429 e DP-439 è stata preservata senza scartare sezioni.
- **Full Python finale su questi file:** `python3 -B -m unittest discover -s tests -q` **3.624/3.624 PASS, exit 0, 460.402 secondi**; log locale `/tmp/dp-20261014-integrated-11-leaf-FULL.log` (non artefatto di CI).
- Focused Python DP231 48, DP314 64, DP320 50, DP439 37, DP440 42, DP431 7, DP436 25, DP438 19 e correction propagation 12 = **304/304 PASS**; benchmark deterministico **5/5 PASS**.
- `npm run check` su Astro **129 file, 0 errori, 0 warning, un hint preesistente**; test Node pinned Python→TS per DP439 pubblico/operatore, Statement search v3 e cross-reader tutti PASS; parità DP431 **9 build TypeScript reali** e `check:rebuild` demo con quattro iniezioni fail-closed PASS; browser isolato DP429 vuoto/demo, tastiera, AX, zoom e confine di produzione PASS.
- Ruff sui 40 file Python cambiati: **non PASS globale**, F401 import inutilizzato storico in `tests/test_dp314_requirement_research_batch_20261014.py`; `ruff format --check` segnala 14 file storicamente non conformi. Non è stato applicato un refactor massivo non revisionato.
- Reviewer indipendente `worker-11` **READONLY** sul diff integrato: 141/141 test mirati DP320/431 e DP231/440, 9 build TS, attacchi source-only DP439 URL paging/privacy, DP231 metadata vuoti, DP440 lineage condivisi, blob parity con quattro leaf; nessun nuovo P1/P2 riprodotto **nel perimetro**. Non ha rieseguito la full suite né controlli fisici.
- Gate GitHub: **zero PR**, main richiede **11 controlli e PR review**; interrogazioni read-only Copilot account/repo restituiscono HTTP 404, quindi auto-review a pagamento non dimostrata OFF. **`PR_HELD_AUTOREVIEW_BILLING_GUARD`**, niente merge diretto/main, nessun claim di CI exact-head.
- `python3 tools/report_ticket_status.py --json`: **162 ticket**, DONE 90, IN PROGRESS 52, BLOCKED 6, FUTURE 14, READY 0, PLAN e ticket coerenti. Status/AC immutati.

## Prove raccolte e limiti del recupero da quattro host

Mac Studio sorgente Git autorevole; MacBook Air e MateBook Linux raggiungibili via SSH senza checkout/cache di progetto trovati nei percorsi di sviluppo esaminati. MiniPC `/home/udodo/src/DichiarazioniPubbliche.it` è **mirror runtime non Git**, servizio web e tunnel attivi; mirror ~34.652 KiB, rollback protetto ~281.336 KiB, backup progetto ~96.552 KiB, transcript ~35.100 KiB. **Non toccati** deploy, servizi, rollback, backup, file sorgente o transcript raw. Canonical `web/node_modules` ~238.496 KiB (rigenerabile solo condizionatamente, non rimosso). Nessun Docker container/volume nominato del progetto rilevato dal survey bounded.

Questa tranche ha ritirato **50 worktree** dopo preflight: 8 clean già in main (268.820 KiB), 6 copie byte-identiche (185.216 KiB), 3 WIP DP240/312/319 superati dalle regression test correnti (86.088 KiB), 3 worker DP431/438/435 superati (100.044 KiB), 24 checkout leaf inclusi nell'integratore remoto (770.140 KiB), 4 vecchi scratch con tutti i test nominati già rappresentati (115.156 KiB), DP314 doc WIP con 2 file identici e 35 righe già integrate (40.660 KiB), DP514 diagnostica già in main con 6 test presenti (28.992 KiB). Totale **1.595.116 KiB nominali**, non misura APFS netta. Due worktree in uso restano: canonical `main` e integratore; tutti gli altri eliminati o valutati conservativamente. Nel precedente turno erano già stati ritirati DP405 clean merged (28.368 KiB) e uno scratch verificato (29.064 KiB): totale storico nominale **1.652.548 KiB**, non 10 GiB.

Il progetto NON contiene 10 GiB di residui dimostrati eliminabili senza distruggere dati unici o rollback/produzione. Non eliminare dipendenze in uso o dati di altri progetti per raggiungere il target numerico.

## Riferimenti remoti sorgente interamente contenuti nell'integratore

Verificati con SHA remoto esatto, `git merge-base --is-ancestor SHA integrate/dp-20261014-all-lanes` e zero PR aperte prima della rimozione dei riferimenti, con push condizionale `--force-with-lease`. I commit restano raggiungibili tramite il merge integratore GitHub (e successivo PR, se autorizzato).

| Branch sorgente assorbito | SHA pubblicato prima della pulizia |
| --- | --- |
| `feat/dp231-private-metadata-cohort-20261014` | `e84c67fcb4c4f2f24f72421682c049fe340758fc` |
| `feat/dp231-private-source-coverage-20261014` | `d89ea88c927528c6eaf3cec5be36eab853707a81` |
| `feat/dp231-private-source-metadata-review-20261014` | `7ecf207f5dcda70433b4c4124de8e00a99b40392` |
| `feat/dp314-private-profile-transitions-20261014` | `89805b95080862f0f0075dda1776a2119c094afd` |
| `feat/dp314-private-research-wave-20261014` | `cd4a5ff595e772ad61690c6eb289cc030429382b` |
| `feat/dp314-requirement-coverage-20261014` | `2d674351c56ea62dbed1168aa25c730727cb8970` |
| `feat/dp314-research-delta-20261014` | `925ea416ac339f2351a1e5965191e6203f46141f` |
| `feat/dp320-dp431-search-integrator-20261014` | `dce7e8e649b167f63d6c3e345b62f42aa8dbd081` |
| `feat/dp320-private-release-transition-audit-20261014` | `cd44af6faa249b4fa41c5e5a7df91fff48542488` |
| `feat/dp320-private-served-surface-fence-20261014` | `38bb87073ea0d370d82683dc76ea4da7eb792557` |
| `feat/dp320-rdf-search-fence-20261014` | `a51f7df5e038181a54b869986106eac7e9d49323` |
| `feat/dp429-active-filters-mobile-20261014` | `9a3bf873d794b2d697d37283370f390465c200a9` |
| `feat/dp439-private-cohort-continuity-20261014` | `787855cde5c99fc533110b67008f97c11b8a2f38` |
| `feat/dp439-private-explore-ssr-20261014` | `44bdbb006c7b619f3f3c593f87af9cf2727006d9` |
| `feat/dp439-private-monthly-change-review-20261014` | `3ac9e8dc82ac3541059f56209173a9a66e5b40b4` |
| `feat/dp439-source-pinned-explore-20261014` | `97ebf539565bc7323f828d56900ae0ff8044789b` |
| `feat/dp439-temporal-facet-preview-20261014` | `ddb6d030c41a0e9f3a8c2ec4cdbc95f3e3fc0dc6` |
| `feat/dp440-private-citation-evidence-20261014` | `d3a7aa2b80310b03766d2e9c645a69af9f16f136` |
| `feat/dp440-private-refresh-cohort-20261014` | `f2ce1f78ccd8c86c27d70fa7cfba47ad3068d08b` |
| `fix/docs-owner-round-dp-20261013` | `49301643d68c34a5553866d7dffd1d0cb283085e` |
| `fix/dp431-search-metadata-integrity-20261013` | `089461ab9572f06ed77b6696fa1bd7bf0d55163e` |
| `fix/dp436-direct-component-pin-20261013` | `20dd33755cecd38ef00bf49b34afe560fcaf40b4` |
| `fix/dp438-homonym-after-identifier-hold-20261013` | `04409bd413fa433bac4bef1c575617a83133bf8d` |
| `fix/dp439-empty-pager-20261014` | `752941e08962e2903785aed476432e223d4e18be` |
| `fix/dp439-operator-share-filter-20261014` | `0e4d67cbd707562617073a1ff1342289476c044f` |

## Pending e gate non chiusi

1. **Merge main:** verificare realmente OFF auto-review Codex a livello account e repository oppure ottenere consenso esplicito ai possibili costi; poi aprire la PR sull'esatto HEAD integrato, ottenere `PR_MERGE_GATE_PASS`, CI exact-head e 0 thread irrisolti; soltanto allora merge e readback `main`. Non utilizzare push diretto bypassando la protezione.
2. **Diritti/fonti/editoria:** DP-214/215 owner/source gated, nessun GET body/capture; DP-409 `archive_added_at` per Statement non autorizzato, DP-443 pilot reale e tutte le acceptance editoriali/legali e accessibilità manuale aperte. Retrieval ≠ approvazione fonte ≠ fact-check ≠ pubblicazione. Nessuna diffusione v3/Statement storici o identity/private transcripts.
3. **DP-514:** causa radice PostgreSQL/SQLSTATE 57014 ancora non determinata. La diagnosi confinata a DB disposable e log sanitizzati già integrata in `main` NON è una cura né una giustificazione per retry/timeout speculativi.
4. **Prove fisiche:** MiniPC, ritiro HTTP/CDN, PostgreSQL operativo, provider e rights/media hosting non validati dalla suite sintetica. Release `NO-GO` finché i proprietari dei gate non forniscono prove reali.
5. **Chat On Steroids:** diverse sessioni worker hanno fallito l'acquisizione di un composer browser o non hanno consegnato report; alcuni comandi dell'integrazione restituiscono blocchi intermittenti. Cause radice NON accertate; miglioramenti proposti: probe di lease/composer e tab prima del dispatch, persistenza di command-id/commit SHA/evidence, replay idempotente senza raddoppiare i worker, limite ai revival inutili, fallback seriale, log di errore strutturati e verifiche di health nel Core e nel Desktop. Non dichiarare fix implementati senza modifiche/test dell'app.

Nessuna nuova PR, nessun merge a `main`, nessun deploy, DB di produzione, provider pagato, costo infrastrutturale o pubblicazione editoriale in questa tranche.
