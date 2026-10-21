# DP-240 / issue #48 — prova con fonti reali e revisione AI, 21 ottobre 2026

**Stato dell'accettazione: PARZIALE / NO-GO pubblicazione.** Dati, prompt e ricevute qui sono il risultato di un esperimento privato sul MiniPC con due contenuti autentici. Non sono un evento editoriale, una licenza per materiale di terzi o il superamento degli AC-240.1–.6.

## Fonti, diritti e confini degli estratti

| Item | Fonte originale e data | Attribuzione nel documento | Note legali specifiche |
| --- | --- | --- | --- |
| Meloni | [Politiche di Coesione, 17/09/2024](https://politichecoesione.governo.it/it/ministro/comunicazione-ministro/notizie-dal-ministro/campania-siglato-accordo-per-la-coesione-il-governo-assegna-3-5-miliardi-di-euro/) | Giorgia Meloni, Presidente del Consiglio dei ministri; l'articolo menziona anche Raffaele Fitto | [Licenza dichiarata CC BY 3.0 salvo eccezioni](https://politichecoesione.governo.it/it/note-legali/) |
| Mattarella | [Dipartimento per le disabilità, 03/12/2019](https://disabilita.governo.it/it/notizie/giornata-internazionale-delle-persone-con-disabilita-conte-annuncia-istituzione-ufficio-permanente/) | Sergio Mattarella, Presidente della Repubblica, distinto dai testi attribuiti a Giuseppe Conte, ISTAT, INAIL e altri | [Licenza dichiarata CC BY 3.0 salvo eccezioni](https://disabilita.governo.it/it/note-legali/) |

Alla lettura del 21/10/2026 i due HTML di fonte hanno SHA-256 rispettivi `7758606e1e54a03a59b17341d26b29493d29148de424cccebc4adf2a5ec95345` e `3ce37d210078603755f330d6fdffd6541eb48bea7f725b54d3db8de7eb60760d`. Le due pagine di note legali hanno SHA-256 `7ab52d00939cb87563529980935d2f1f291308f5182375e0808bfe3e4a55a546` e `55b30faf0963b9ddb5602a2c9e40909729c9fdfc990c79ec18b48ac23f80c6ea`. Sono hash di risposte HTML osservate, non firme del sito. L'attestazione AI riguarda **soltanto** le citazioni brevi testuali con attribuzione, a scopo di test privato. Materiale audiovisivo, foto, loghi, parti con indicazione diversa, contenuti e diritti di terzi restano fuori da questa clearance. Nessun registro operativo `CLEARED` è stato aggiornato.

`material.json` è il pacchetto **immutato** ricevuto dai revisori e inviato al modello benchmark. `original-passages.json` conserva il testo dei Passage esattamente come nell'HTML (tolte solo le differenze di whitespace introdotte dal parser). L'estratto Meloni coincide con la fonte; l'estratto Mattarella dato al modello ometteva una virgoletta interna prima di «non è» presente nell'originale, dunque è una **derivazione normalizzata**, con due SHA distinti e differenza dichiarata. La prova MiniPC usa l'originale per `passage_sha256` e blocca l'esecuzione se l'estratto non è ritrovato nell'HTML corrente; non presentiamo la normalizzazione come verbatim. Il modello è stato misurato sul testo normalizzato, non su una nuova esecuzione dell'esatta grafia del Passage.

## Due revisioni AI indipendenti via CLI

Il medesimo prompt `review-prompt.md` con pacchetto materializzato è stato inviato, senza accesso a tool o risposte altrui, tramite Pi CLI su `matebooklinux`:

- `review-sol.json`: provider `codex`, modello dichiarato dalla route `gpt-6.1-sol`, thinking high, 4.992 token reported, 78,979 s wall SSH. Revisore privacy AI incaricato secondo AGENTS. Speaker Meloni/Mattarella corretti sul contesto fornito; controllo negativo Conte e testo redazionale non attribuibili all'altro speaker; **GO privato condizionato / HOLD pubblico**.
- `review-gemini.json`: provider `antigravity`, modello `gemini-3.8-flash-tiered`, 5.472 token reported, 44,455 s wall SSH. Conferma le due attribuzioni e i controlli negativi; **GO privato circoscritto / HOLD pubblico**.

Entrambe le attestazioni registrano prompt integrale, SHA-256, istante UTC, comando CLI, modello richiesto, risposta originale, usage e stato d'esecuzione. Le etichette `expected_*` erano visibili ai revisori; il giudizio non è un gold *cieco* in senso rigoroso. Gemini condivide famiglia col generatore del benchmark; Sol è di famiglia distinta. Le risposte non provano che i modelli abbiano aperto e verificato autonomamente URL esterni (tool disabilitati); la lettura live e le note legali sono verificate separatamente dallo script deterministico. Nessuna attestazione può autorizzare pubblicazione.

## Confronto preregistrato singoli / batch Gemini

Il protocollo `benchmark-protocol.md` era fissato prima delle tre chiamate riuscite; `cli_probe.py` esclude `expected_speaker` e `expected_role` dall'input del generatore e richiede `id`, `content_id`, speaker, ruolo, stato e URL della fonte.

| Metrica Pi | Due chiamate singole (somma) | Una chiamata mixed (2 item) |
| --- | ---: | ---: |
| Attribuzioni coerenti con fonte/ruolo/Content/URL | 2/2 | 2/2 |
| Errata attribuzione o Content incrociato | 0/2 | 0/2 |
| Token input+output totali dichiarati | 3.724 | 3.161 |
| Tempo wall SSH+Pi | 184,429 s | 40,604 s |
| Costo dichiarato dal meter Pi | 0 | 0 |
| Costo fatturato e RSS provider | UNKNOWN | UNKNOWN |

Risparmio osservato: **563 token (15,12%)** su un campione di due record, senza inferenza statistica. I tempi includono SSH, inizializzazione e variabilità del provider. Due tentativi singoli *prima* dell'esecuzione sequenziale hanno prodotto `stopReason=error`, nessun output, dopo un retry interno Pi; sono conservati in `benchmark-single-*-provider-failure.json` e contano come **due fallimenti per item**; i retry seriali sono nuove invocazioni con ricevuta separata. La sommatoria nella tabella riguarda i due run riusciti e non attribuisce falsamente i fallimenti al numeratore. Per costo realmente fatturato e memoria non è disponibile una misura fonte-specifica affidabile. Non si approvano batch di dimensioni maggiori.

`evaluate.py` ricalcola la corrispondenza per ID, Person/ruolo, Content/URL, stato, errori per item e token su output JSON Pi originali; `benchmark-metrics.json` contiene risultati, limitazioni e policy HOLD. I controlli negativi (citazione di Conte e narrazione redazionale) sono stati esaminati **dai revisori** e dagli invarianti deterministici; non vengono conteggiati come casi reali eseguiti nella baseline provider di tre chiamate.

## Prova vera del consumer MiniPC, privata e isolata

Riuso delle API esistenti `multi_person_batch_v1`, `multi_person_batch_store_v1`, `studio_machine_candidate_handoff_v1`. `studio_probe.py` ricarica HTTPS entrambe le fonti e note legali, verifica HTTP, SHA e presenza esatta dei Passage originali nell'HTML; costruisce due Content, Capture, Passage e speaker candidati distinti. Il manifest da due item è bounded a 900 token stimati e 2 partition ID. Una osservazione con Content di altro item viene rifiutata `MULTIPERSON_RESULT_SOURCE_MISMATCH`.

In SQLite temporaneo con permessi privati: `register` e `resume` del piano sono idempotenti (revision 0: nessuna osservazione modello falsamente inserita). Una **seconda** SQLite temporanea, con Source/Capture/Passage/rights separati, alimenta il consumer `LocalPersistedBatchMachineHandoff`; l'operator preview restitusce due source-bound item con speaker e stato `HELD_SOURCE_OR_ATTRIBUTION` e motivo `MULTIPERSON_QUOTATION_NOT_ENDORSEMENT`, senza accodamento o pubblicazione. La prova di persistenza Studio è su un adapter locale *disposable*, non sulla tabella PostgreSQL operativa. `minipc-studio-proof.json` registra fingerprint piano, ricevuta, due SHA sorgente Passage, snapshot della licenza e item del reader.

Comando utilizzato su MiniPC con lock (copia degli script nel percorso privato temporaneo):

```bash
flock -w 1800 /tmp/DichiarazioniPubbliche.it-heavy.lock \
  env PYTHONDONTWRITEBYTECODE=1 \
  PYTHONPATH=/home/udodo/Code/.worktrees/DichiarazioniPubbliche.it-48-replay-20261021/poc \
  python3 -B /tmp/dp240-48-20261021-private/studio_probe.py
```

**Risultati di controllo:** 2 item, 2 partizioni, 2 Passage originali esatti, rifiuto cross-source PASS, replay SQLite PASS, 2 HELD Studio e `publication_authority=false`. Sullo stesso MiniPC, suite `tests.test_dp240_multi_person_batch tests.test_dp240_durable_batch_next tests.test_private_candidate_batch tests.test_dp242_studio_machine_handoff`: **81/81 OK** sotto lock. Check repository Mac: **8/8 OK** e `OK: repository contract satisfied`. Servizio MiniPC `active`; `/api/v1/health` stato `ok`, `dossier_count=0`, impronta `501348d9638ee3c4d929205d2e6dca7eb2c8a552ac006dee837ea032a739ae7a` invariata nel readback osservato. Nessuna modifica a database operativo, projection o sorgenti applicativi.

## Limiti AC e decisione

Gli AC-240.1 e 240.2 hanno ricevute reali di source identity, citazioni e failure negative, ma le Person non sono approvate nel corpus operativo e il gold non era perfettamente cieco. AC-240.3 resta **parziale**: output JSON reali e Passage originali separati, nessun output provider autenticato nel ledger dei Candidate, né candidate Statement/Claim tracciato nella pipeline reale. AC-240.4: retry/failure provider osservati ed esatti, replay privato e suite per cardinalità/per-item passati, ma fallimenti provider non sono persistiti come attempt nella prova sorgenti live (gli item quoted restano HELD). AC-240.5: confronto concreto token, tempo e false-attribution sui due positivi; mancano costo fatturato/memoria, benchmark completo su negativi e benefici robusti, quindi **NO-GO aumento batch**. AC-240.6: provenienza e hold verificati su consumer SQLite disposable al MiniPC e projection stabile; manca una registrazione autenticata/approvata dei *medesimi* Content nel corpus/Studio operativo con readback PostgreSQL e conteggi pre/post.

Tutte le prove restano private. La release e la pubblicazione dei due casi sono **HOLD** fino alla risoluzione degli AC residui mediante il percorso autorizzato per Capture, review e persistenza; non è necessario scegliere di nuovo temi, revisori o referenti con l'owner.
