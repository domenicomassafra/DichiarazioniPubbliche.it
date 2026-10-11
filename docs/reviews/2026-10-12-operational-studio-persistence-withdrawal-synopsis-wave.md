# 2026-10-12 — Studio end-to-end privato, persistenza, revoche locali, citazioni e sintesi v3

## Baseline e consegne funzionali

Baseline prima delle modifiche: `main=origin/main=13e6fff9a3f0412720b37e5003bad4c884893aea`,
checkout pulito, singolo worktree e nessuno stash. Questa nuova tranche ha
integrato dodici commit locali atomici, distribuiti in più ondate con
ownership esclusiva e review indipendente:

| Commit | Ticket | Cambiamento verificabile |
| --- | --- | --- |
| `0efeafd` | DP-519 | Worklist e tempi visuali privati persistiti SQLite, CAS per revisione, eventi immutabili e ripresa |
| `2efec34` | DP-516 | Checkpoint storici per Capture in SQLite con revisioni append-only e CAS |
| `2272356` | DP-519 | Connessioni SQLite chiuse anche dopo letture, senza warning di risorsa |
| `3d8094d` | DP-312 | Citazioni tedesche `»…«` e `›…‹` non diventano endorsement del parlante |
| `01bfda5` | DP-313 | Stato giudiziario citato da testimoni, reporter o allegazioni non diventa status istituzionale |
| `e7ec684` | DP-417/416 | Due endpoint loopback bearer/Origin/Host autenticati su PostgreSQL read-only per Capture queue e exact Passage lineage |
| `2bb76cc` | DP-516 | Readback del checkpoint locale nel planner di backfill esistente; nessun dispatch da sole ricevute locali |
| `148ee80` | DP-507 | Contratto superfici private aggiornato soltanto per le due nuove route read-only, nessun ingresso pubblico admin |
| `1a1ea5b` | DP-518 | Lettura di byte reali di release locali su 24 superfici fra HTML/API/search/sitemap/RDF/cache con negative revoca/stale |
| `84f7e5b` | DP-440 | Consumer v3 citato, pinned e opt-in Python→TypeScript→Astro SSR, no route di produzione |
| `87f6bb3` | DP-418 | Adapter PostgreSQL concreto per target Claim Candidate → Source/Passage/Capture/version/rights, Atomic Claim senza FK resta non attestato |
| `83668c1` | DP-416/417 | UI Studio interattiva Collection→Content→Capture→Passage→Candidate, capture queue, paging, focus e pulizia token/riferimenti |

## Prove e limiti

Il percorso Studio HTTP è stato provato contro socket loopback e PostgreSQL
effimero inizializzato con lo schema canonico: successi positivi, status
`401/403/405/422`, parent/Content/Capture/Passage/cursor estranei,
membership rimossa, diritti revocati, role PostgreSQL read-only, assenza di
URL/corpi privati. Sono stati verificati 48 test mirati per HTTP/PG,
50 per UI/API/queue con il runner DOM deterministico, e 53 sul target
DP-418 e suite adjacent PostgreSQL. I nuovi collegamenti non autorizzano
azioni di promozione, pubblicazione o giudizio.

La pagina Studio usa `textContent` e controlli nativi keyboard/focus, ma
una prova aggiuntiva in Chrome/CDP locale è andata in timeout: non è stata
spacciata per accettazione e il caso sperimentale non stabile è stato
ritirato. **Prova fisica manuale di Chrome/VoiceOver/200% zoom resta
OPEN**, come il corpus operativo Garlasco e il MiniPC live.

Il controllo di ritiro DP-518 usa veri file temporanei e una ricevuta privata
fuori dalla root pubblica; per 12 tipi di consumer e due entità confronta
inventario, pin, epoch e hash dei byte. Vecchio contenuto o cache simulata
sopravvissuta viene rifiutato; anche l'esito positivo è
`CONSISTENT_UNATTESTED`, non un'assicurazione sul CDN. 34 test
DP-518/320 combinati PASS. Il synopsis DP-440 consuma davvero l'output di
`prepare_public_synopsis` e compila un'isolata route Astro di prova, mentre
ritiro/expiry provocano il rifiuto. Sintesi inventate, licenze, quote o
finding non sono stati pubblicati.

I journal SQLite locali hanno testato concorrenza, riavvio, idempotenza,
immutevolezza, diritti cambiati e resoconto dei minuti. Non sono la fonte
di verità MiniPC né una quota ERP o autorità di diritti/review.

## Host e release

Audit conservativo in sola lettura: Mac Studio un checkout e nessuno stash;
MacBook Air e MateBook Linux raggiungibili, nessun checkout DP nelle sole
directory Code/Codex/src/tmp/Projects controllate; MiniPC mirror non-Git
`/home/udodo/src/DichiarazioniPubbliche.it` ~34.652 KiB lasciato
intatto, unità utente web e tunnel Cloudflare attive. Nessuna rimozione,
**0 byte di spazio nuovo recuperato**, nessun deploy o provider.

Gli AC originali DP-312/313/416/417/418/440/516/518/519 rimangono
**non tutti soddisfatti**. Non è stato creato un nuovo DONE: fonti/licenze
reali, autorità editoriale, corretta voce giudiziaria, segreti firmati e
release atomica servita, review qualificata, accessibilità fisica e MiniPC
restano gate separati. Conservare **90 DONE / 72 pendenti / NO-GO 49**.
Nessun rilascio editoriale autorizzato.

I risultati di suite completa, remote SHA e GitHub Actions del **commit
finale** vanno registrati solo quando realmente conclusi; la CI 11/11 del
vecchio `13e6fff` non certifica automaticamente questa tranche.
