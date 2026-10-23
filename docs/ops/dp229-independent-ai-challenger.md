# DP-229 — Procedura AI challenger indipendente (20 ottobre 2026)

Fonte normativa: [issue #40](https://github.com/domenicomassafra/DichiarazioniPubbliche.it/issues/40) e [decisione owner del 20 ottobre](https://github.com/domenicomassafra/DichiarazioniPubbliche.it/issues/40#issuecomment-6299904112). I challenger sono **sempre AI**. Due challenger AI distinti dal generatore primario cercano errori, controesempi e limiti: non votano sulla verità di una dichiarazione e non autorizzano pubblicazione. Il controllo finale su diritti, evidenze, Finding e projection resta deterministico.

## Input approvati e isolamento

1. Scegliere una **claim e versione del record** interna identificabili e acquisire, con permessi di sola lettura, il fingerprint *corrente* `challenger-material-inventory-v3` da `load_challenger_material_inventory()` su PostgreSQL. Conservare la ricevuta di query/snapshot (host, istante, claim/versione, digest, conteggi, blocker, policy). Il fingerprint include il record **corrente** di `private_source_rights_record`, versione/policy, permessi d'uso e obblighi di attribuzione; l'inventario accetta soltanto una clearance con receipt/reviewer/data validi, uso `CHALLENGER_PRIVATE_RESEARCH` e locator URL identico alla fonte canonica dell'evidenza. Una revoca append-only, scadenza, fonte discordante o registry assente rende il materiale pending e cambia/invalida il digest. `evidence.rights_status=CLEARED` da solo non basta. Verificare comunque separatamente autorità del reviewer, licenza, source lineage, source role, periodo e autenticità della **fonte primaria**: il registro è un record operativo, non una firma indipendente. L'inventario aggregato non attesta l'approvazione editoriale né la pubblicazione; nel dubbio HOLD.
2. Preparare un manifest **versionato e approvato da un'autorità materiale separata**: claim/versione, inventory SHA256, insieme completo di evidenze ammesse (anche CONTRADICT/LIMITATION/CONTEXT/UPDATE), fonti primarie ammesse, receipt ID e identità dell'autorità. Vietato derivare un manifest approvato dalle affermazioni del generatore, dalle sole quote di ricerca o dal solo flag `approved=True` del modello. Se manca l'autorità: HOLD.
3. Riutilizzare `compile_challenger_research_request()` dal DP-228 `ClaimResearchPlan` opt-in e dalla PR [#236](https://github.com/domenicomassafra/DichiarazioniPubbliche.it/pull/236). Ricontrollare `READY`, adapter ammessi, domini/host, domande, stop conditions, **MAX_QUERIES=32 aggregato**, max risultati, costi e timeout del sistema provider. Cost cap inferiore può essere imposto; nessun aumento silenzioso, nessuna chiamata senza permessi attivi e preflight budget. Salvare per ogni tentativo query, parametri, stato, risultati e receipt del provider. Ricerca non effettuata non equivale a ricerca completata.
4. Usare un **AI generatore** identificato da provider, famiglia, modello, credenziale pseudonimizzata (fingerprint), run ID, sessione e prompt SHA; congelare il packet proposto e gli ID originali. Il generatore non approva il proprio packet e non crea direttamente ricevute di reviewer, di materiali o di pubblicazione.
5. Assegnare due **AI indipendenti** a sessioni nuove e ruoli diversi: `COUNTEREVIDENCE` (cercare le confutazioni più forti, fonti originali) e `LIMITATIONS` (temporalità, copertura, interpretazioni alternative, aggiornamenti, conflitti). Famiglie modello differenti dal generatore e fra loro; identità, sessioni, credenziali e prompt distinti. Evitare che vedano le conclusioni o i voti reciproci prima della loro risposta. Registrare modello/fornitore, versione, sessione, prompt hash, costo e **dichiarazione dei conflitti** (fonte comune, proprietà del contenuto, accesso incrociato, famiglia/derivazione, incentivi, istruzioni condivise). Conflitto o provenienza incerta => HOLD.
6. Ogni AI deve riferire il `packet_id`, il manifest/inventory SHA, la claim/versione, i receipt di ricerca e l'elenco degli ID di evidenze **effettivamente esaminate**, inclusa almeno una fonte primaria approvata. Riportare controesempi documentati, `CONTRADICT` e `LIMITATION/CONTEXT/UPDATE`, con identificatori di fonti e gruppo di derivazione. `NEEDS_MORE` è legittimo e comporta HOLD; *assenza* di controprove non prova verità. La risposta AI non può aggiungere nuove fonti all'insieme ammesso: nuovi risultati tornano all'intake/review e cambiano il digest.
7. Il reviewer indipendente del **dossier esatto** (autorità separata dai tre run AI, anch'essa AI nella policy owner) verifica ricerca/limiti, diritti, manifest, packet incorporato nell'esatto record/versione, citazioni e timestamp, policy e potenziali conflitti. Solo il writer append-only autorizzato può persistere gli eventi del reviewer con attestazione esterna risolta. Il controllo deve rileggere lo snapshot corrente e rifiutare eventi stantii, collisioni, replay di altra claim, conflitto di interesse e receipt auto-emessi. Un eventuale waiver è una decisione qualificata separata ed esplicita; non esiste waiver implicito o approvazione per majority vote AI.

## Gate ed esecuzione ripetibile

- **Gate offline attuale:** `audit_ai_challenger()` verifica due ruoli distinti, separazione attore/sessione/credenziale/famiglia/prompt, conflitti, claim/versione, packet e inventory esatti, fonte primaria, controesempi e limitazioni, budget e receipt. Restituisce soltanto `HOLD` o `NON_AUTHORITATIVE_REVIEW_CANDIDATE`; `publication_authority=False` in ogni caso. I campi di identità/manifest/receipt sono **autodichiarati** finché non verificati presso una authority distinta: un SHA consistente non è firma né accesso a fonte primaria.
- **Comando test offline, MiniPC con lock:** `flock -w 1800 /tmp/DichiarazioniPubbliche.it-heavy.lock env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=poc python3 -m unittest tests.test_dp229_challenger_ai_audit tests.test_dp229_challenger_query_budget tests.test_challenger_research tests.test_countercase tests.test_challenger_material_inventory -q`. I test utilizzano dati sintetici; non interrogano provider né cambiano stato di produzione.
- **Gate runtime attuale:** `evaluate_publication_eligibility()` scarta sempre il `challenger_readiness` e il waiver costruiti dal chiamante. Non collegare `NON_AUTHORITATIVE_REVIEW_CANDIDATE` all'eligibility composer o alla projection. Questa limitazione si rimuove soltanto dopo un’autorità attestata/registrata e replay esatto; la decisione owner che i reviewer siano AI non dimostra che il writer/attestatore esista già.
- **Prova reale AC-229.8 futura:** su MiniPC, con fonti primarie e diritti ammessi, usare query effettive entro budget e receipt durevoli; eseguire e attestare i reviewer AI separati; registrare packet incorporato e riesaminato sul materiale esatto; ripetere dopo introduzione di una CONTEXT/UPDATE o revoca diritti e verificare che un vecchio packet/review rimanga HOLD. Verificare poi replay dal ledger, blocco del forged READY e proiezione invariata. Registrare in #40 timestamp, SHA, comandi, risultati, decisioni e link, senza contenuti privati o segreti.

### Attestazioni effettive e loro perimetro

Archiviare ogni run in `docs/attestations/dp229/<data>-<fonte>/`: `packet.md` con hash/diritti/insieme fonti e stato dei gate, prompt esatto congelato, stdout integrale per modello, `attestation.md` con comando/modello/orario/hash/esito e limiti dell'indipendenza. Gli hash delle risposte non sostituiscono una receipt provider autenticata o il ledger dell'autorità materiale. Se i due reviewer non vedono lo stesso materiale corrente, segnare la differenza e richiedere un nuovo esame per quel digest; se il generatore e il challenger condividono una famiglia modello, **non dichiarare indipendenza piena**.

Il [canary documentale Senato S.1 del 21/10/2026](../attestations/dp229/2026-10-21-senato-s1/attestation.md) contiene due vere invocazioni Pi (`codex/gpt-6.1-sol` e `antigravity/gemini-3.8-flash-tiered`) su uno stesso prompt, risposte `NEEDS_MORE`, verifica di fonte/CC BY e il limite di indipendenza rispetto al generatore. Rimane `HOLD`: manca ogni attestazione corrente di origine DB, completamento DP-228 e incorporation/review append-only high-risk. Conservare il canary come prova della controrevisione eseguita, mai come prova di publication readiness.


### Canary DP-228 → DP-209 su feed ufficiale, 22/10/2026

Il feed Camera `official-camera-temi`, già incluso in
`config/source-registry.v1.json`, viene ora eseguito tramite il parser
`PublicRssAdapter` esistente. La modifica nativa è solo l'ammissione
della famiglia `public_rss` in `ConfiguredRegistryDiscoveryAdapter`.
La regressione `tests.test_research_discovery.ResearchDiscoveryTests.test_configured_registry_adapter_dispatches_authorized_official_rss`
falliva perché non veniva invocato il parser e ora passa. Non sono
state adottate nuove dipendenze o licenze.

Sul MiniPC, in un database PostgreSQL **privato e separato** da quello
del servizio, con socket Unix in una directory 0700, il comando

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=poc python3 tools/dp229_official_rss_canary.py --state-dir /home/udodo/.local/state/dp229-senato-s1-rss-20261022
```

crea una Coverage Need e un manifest limitati da
`compile_challenger_research_request()`, quindi esegue la discovery
nativa. Budget fissato: **1 query, 2 risultati complessivi, 1/host e
USD 0**, con ripetizione idempotente e readback della receipt.
L'esecuzione del 22/10/2026 ha restituito
`run:dp229:senato-s1:official-camera:20261022` `COMPLETED`,
un tentativo `HEALTHY`, zero hit, costo osservato USD 0.
Questo è **un tentativo reale con astensione motivata**; l'assenza di
hit non verifica né confuta il Senato S.1 e non completa una
ricerca per ogni fonte. Non accede al database produzione e non
importa articoli o trascrizioni. La prova locale deve essere ripetuta
solo sotto workload admission sul MiniPC, come previsto dal contratto
operativo.

Un replay privato ulteriore su PostgreSQL disposable, con i **byte realmente
scaricati** del Senato S.1 e la scheda d'iter (SHA256 registrati),
ha creato una *claim dichiaratamente sintetica e non attribuita* e due
candidati CONTRADICT/CONTEXT, sempre pending. Il registro diritti nativo
`PrivateRightsRegistryStore.record_rights()` ha registrato in append-only
la CC BY 4.0 limitatamente all'XML, poi una **revoca simulata solo in
sandbox**, senza affermare che il Senato abbia revocato la licenza.
L'inventory v3 è cambiato da
`b3a572c702b89ead5cc1ea5cf028952978b968d804b1ccb0a3367608628cc149`
a `25a843c35d9f2c0b2b0a2e1ff6473abe0a952259c4f33e9921f8a46f91a84d47`.
Il risultato high-risk `evaluate_challenger_readiness(...,high_risk=True)`
è `STALE` per `CHALLENGER_PACKET_NOT_READY`,
`HIGH_RISK_CHALLENGER_REQUIRED` e
`HIGH_RISK_CHALLENGER_REVIEW_REQUIRED`.
Non essendoci un editor/reviewer attestato, il countercase rimane
`INCOMPLETE` e il consumer operativo non ha ricevuto alcuna nuova
evidenza né autorizzazione. La ricevuta e lo script esatto sono
conservati in area privata sul MiniPC.

Il documento Senato AkomaNtoso S.1 proviene dal repository
[SenatoDellaRepubblica/AkomaNtosoBulkData](https://github.com/SenatoDellaRepubblica/AkomaNtosoBulkData)
al commit `2da7d887c8125286312e88c6913fa194feb1c6ce`,
oggetto `Leg19/Atto00055177/ddlpres/01360967-ft.akn.xml`;
SHA256 dei 13.036 byte `57fcd8ae860d3e4593686567612e251dc0f40a4d1842bddb6eeac68bdb7ad929`.
Il repository dichiara **CC BY 4.0** per questi dati, con
attribuzione al Senato: il permesso documentale è limitato al
testo legislativo/versione indicati, non si trasferisce ad altre
fonti, immagini, audio né alla scheda di iter. La pagina d'iter
ufficiale è stata consultata il 22/10; il materiale integrale
rimane privato sul MiniPC. Non esiste ancora una clearance registrata
sul DB operativo per una claim high-risk, né una receipt firmata
dell'autorità AI indipendente: **HOLD**, zero autorità publish.

**Stato:** i canary del 22/10 provano la ricerca realmente eseguita e l'invalidazione nel database privato con fonte autentica, ma **non** soddisfano da soli l'AC runtime high-risk. Mancano rights current in produzione, incorporation del packet nel Finding/Verification Run effettivo e attestazione separata del reviewer AI sulla versione esatta. Restano obbligatori replay del ledger e verifica di staleness sull'evento di review autorevole. Nessuna pubblicazione, waiver o autorizzazione di spesa deriva da questi risultati.
