## DP-229 — Controrevisionе documentale privata

**Decisione di ricerca: `NEEDS_MORE`, limitata al mio esame documentale.** Ho letto i tre file del commit indicato e verificato l’hash dell’XML; restano da verificare le ipotesi alternative sull’identificazione dell’atto e sulla cronologia parlamentare. Non esprimo un verdetto sulla claim, né un’autorizzazione alla pubblicazione.

### 1. Evidenza effettivamente esaminata

I riferimenti seguenti sono tutti al commit `2da7d887c8125286312e88c6913fa194feb1c6ce`:

- **[X — XML](https://github.com/SenatoDellaRepubblica/AkomaNtosoBulkData/blob/2da7d887c8125286312e88c6913fa194feb1c6ce/Leg19/Atto00055177/ddlpres/01360967-ft.akn.xml)**, letto integralmente, inclusa la relazione allegata. Download diretto di **13.036 byte**; SHA256 calcolato: `57fcd8ae860d3e4593686567612e251dc0f40a4d1842bddb6eeac68bdb7ad929`, coincidente con quello fornito.
- **[R — README.MD](https://github.com/SenatoDellaRepubblica/AkomaNtosoBulkData/blob/2da7d887c8125286312e88c6913fa194feb1c6ce/README.MD)**, letto integralmente.
- **[L — LICENSE.MD](https://github.com/SenatoDellaRepubblica/AkomaNtosoBulkData/blob/2da7d887c8125286312e88c6913fa194feb1c6ce/LICENSE.MD)**, letto integralmente.

L’hash verifica la corrispondenza dei byte con il packet dichiarato, **non costituisce una conferma indipendente del contenuto storico**.

Non ho esaminato la scheda dell’iter, resoconti parlamentari esterni al file, fonti indipendenti, DP-228, database dei diritti, manifest approvati, Verification Run o ledger. Le rispettive assenze e lo stato «0/32» sono informazioni del prompt, non stati da me verificati nei sistemi.

### 2. Strongest counterexamples e confutazioni da verificare

| Ipotesi avversaria | Osservazione motivata e verifica necessaria |
|---|---|
| **«È stato scambiato un testo presentato per una legge approvata o vigente».** | È il rischio interpretativo principale. X qualifica il documento come `bill`, `originalVersion`, `DDLPRES`; il workflow riporta `outcome="Presentazione"` ([X, righe 3–46](https://github.com/SenatoDellaRepubblica/AkomaNtosoBulkData/blob/2da7d887c8125286312e88c6913fa194feb1c6ce/Leg19/Atto00055177/ddlpres/01360967-ft.akn.xml#L3-L46)). Il comma 8 contiene una **clausola proposta** di entrata in vigore il giorno successivo alla pubblicazione, non prova che tale pubblicazione sia avvenuta ([X, righe 120–126](https://github.com/SenatoDellaRepubblica/AkomaNtosoBulkData/blob/2da7d887c8125286312e88c6913fa194feb1c6ce/Leg19/Atto00055177/ddlpres/01360967-ft.akn.xml#L120-L126)). La claim candidata usa «fu presentato» e «proponeva»: l’obiezione non va trasformata in una confutazione di parole che la claim non contiene. Per qualsiasi estensione ad approvazione o vigenza occorrono gli atti successivi e l’eventuale pubblicazione ufficiale. |
| **«Il numero 1 identifica un altro atto o un’altra legislatura».** | `FRBRnumber=1` compare nei metadati del disegno di legge; il percorso è `Leg19/Atto00055177`, ma il campo tipografico `docNumber` è vuoto ([X, righe 7–18 e 58–67](https://github.com/SenatoDellaRepubblica/AkomaNtosoBulkData/blob/2da7d887c8125286312e88c6913fa194feb1c6ce/Leg19/Atto00055177/ddlpres/01360967-ft.akn.xml#L7-L67)). Questo non dimostra uno scambio, ma rende opportuno verificare nella scheda ufficiale la corrispondenza **XIX legislatura ↔ S.1 ↔ Atto00055177 ↔ titolo ↔ proponente**. La chiave «S.1» isolata è insufficiente. |
| **«Il 13 ottobre è data del documento, non dell’evento parlamentare dichiarato».** | Non è soltanto una data di file: `FRBRdate` è denominata `presentazione`, il workflow indica «Presentazione» e l’intestazione dice «COMUNICATO ALLA PRESIDENZA IL 13 OTTOBRE 2022» ([X, righe 9, 46 e 73](https://github.com/SenatoDellaRepubblica/AkomaNtosoBulkData/blob/2da7d887c8125286312e88c6913fa194feb1c6ce/Leg19/Atto00055177/ddlpres/01360967-ft.akn.xml#L9-L73)). Resta da confrontare la scheda ufficiale, distinguendo presentazione, annuncio in seduta, assegnazione e pubblicazione del testo: date diverse per eventi diversi non sono automaticamente una contraddizione. |
| **«La proposta era precedente al 2022».** | La relazione menziona espressamente **S.2400 e C.3387 della legislatura precedente**, definendo S.2400 «corrispondente al presente disegno di legge» ([X, riga 173](https://github.com/SenatoDellaRepubblica/AkomaNtosoBulkData/blob/2da7d887c8125286312e88c6913fa194feb1c6ce/Leg19/Atto00055177/ddlpres/01360967-ft.akn.xml#L173)). È una pista concreta contro un’eventuale pretesa di novità assoluta, **non contro la presentazione di S.1 nel 2022**. Vanno separati antecedente e ripresentazione. |
| **«Il testo riguarda tutti gli organismi bicamerali o impone uniformemente 10+10».** | Sarebbe un’estensione indebita. I commi 1–7 propongono modifiche differenti; la relazione distingue organismi da venti e da dieci componenti ed esplicita esclusioni: COPASIR, anagrafe tributaria, organismi misti e commissioni d’inchiesta ([X, righe 77–117 e 179–187](https://github.com/SenatoDellaRepubblica/AkomaNtosoBulkData/blob/2da7d887c8125286312e88c6913fa194feb1c6ce/Leg19/Atto00055177/ddlpres/01360967-ft.akn.xml#L77-L187)). «Alcuni organismi» evita questa generalizzazione. Il comma 1, inoltre, propone anche un’abrogazione: la sintesi 15+15 → 10+10 non esaurisce quel comma. |

### 3. LIMITATION, CONTEXT, UPDATE e dipendenze temporali

**LIMITATION.** Il packet documenta un testo nella versione presentata. Il README definisce `ddlpres` proprio come il testo «così come presentato dal proponente» ([R, riga 38](https://github.com/SenatoDellaRepubblica/AkomaNtosoBulkData/blob/2da7d887c8125286312e88c6913fa194feb1c6ce/README.MD#L38)). Il singolo evento nel workflow non autorizza né «non fu mai approvato» né «è tuttora pendente». L’assenza di eventi successivi **in questo documento** non è assenza di eventi nell’iter.

**CONTEXT.** La relazione è materiale dello stesso atto, non un riscontro indipendente. Le sue valutazioni sulla funzionalità degli organismi o sul rischio di paralisi devono rimanere attribuite al testo proponente, senza diventare fatti accertati dalla controrevisione. Anche la legge costituzionale n. 1/2020 richiamata nel titolo va distinta dal disegno di legge ordinario in esame.

**UPDATE.** Un successivo emendamento, assorbimento, ritiro, approvazione o intervento legislativo parallelo potrebbe cambiare la descrizione dell’iter o della disciplina vigente; non cancellerebbe automaticamente l’evento storico della presentazione. Qualunque aggiornamento deve indicare una **data di riferimento** e collegare documentalmente gli atti. Il README riporta «Ultimo aggiornamento: 01:00:02 21/10/2026» ([R, riga 60](https://github.com/SenatoDellaRepubblica/AkomaNtosoBulkData/blob/2da7d887c8125286312e88c6913fa194feb1c6ce/README.MD#L60)): è un’indicazione del repository, non la data dell’evento parlamentare o una certificazione dell’iter di S.1.

**Falsi positivi da evitare.** Sono particolarmente esposti a errore il «n. 1» della legge costituzionale contro S.1; omonimi di numerazione in altre legislature; S.2400/C.3387 contro S.1; la data di annuncio contro quella di presentazione; la formula «la presente legge» nel progetto contro una legge promulgata.

Prima di qualsiasi Finding andrebbero ricercati:

- la scheda ufficiale del Senato e il testo tipografico/PDF corrispondente, come controllo d’identità, pur nello stesso origin group;
- i resoconti pertinenti alla presentazione e all’annuncio;
- gli eventuali passaggi alla Camera e, solo se emerge un collegamento verificabile, Gazzetta Ufficiale e Normattiva;
- una fonte esterna con raccolta o analisi propria, verificandone la genealogia. Un mirror o una notizia che copia il Senato non acquisisce indipendenza per il solo cambio di dominio.

### 4. Indipendenza e ambiente

L’ambiente visibile è **Pi Agent su Linux**, con directory di lavoro `/home/matebooklinux`. Le variabili interrogate dichiarano **`PI_MODEL=gpt-6.1-sol`** e **`PI_PROVIDER=codex`**. Sono etichette dell’ambiente, non una certificazione esterna dell’identità o della genealogia del modello.

Non conosco il modello che ha generato la claim o le precedenti revisioni: **non posso attestare indipendenza di famiglia, provider o processo**. Non ho accesso a informazioni sufficienti per certificare assenza di conflitti organizzativi o interessi. Questa è una seconda lettura della medesima fonte, guidata anche dal prompt: non una testimonianza indipendente.

XML, README, licenza e relazione allegata non costituiscono quattro corroborazioni autonome.

### 5. Budget, versione, diritti e controlli deterministici

**Budget.** In questa sessione ho eseguito **zero query di ricerca**; ho effettuato letture dirette degli URL del packet. Non ho prodotto receipt di ricerca provider. Il conteggio aggregato DP-228 «0 su 32» resta dichiarato dal prompt: non posso certificarne l’aggiornamento, né assumere come i download siano contabilizzati dal sistema.

**Versione.** L’oggetto effettivamente esaminato è `claim-candidate-senato-s1-v1` confrontato con i tre file del commit indicato. Il commit immutabile e l’hash XML non sostituiscono un manifest `material-v3` approvato. Manifest e receipt non vanno ricostruiti retroattivamente fingendoli esistenti.

**Diritti.** Il README attribuisce i dati a «Senato della Repubblica - Servizio dell’Informatica» e dichiara CC BY 4.0 ([R, righe 50–56](https://github.com/SenatoDellaRepubblica/AkomaNtosoBulkData/blob/2da7d887c8125286312e88c6913fa194feb1c6ce/README.MD#L50-L56)); L contiene il testo della licenza. La sezione 3 disciplina attribuzione e indicazione delle modifiche in caso di condivisione; la sezione 2(a)(6) esclude un’implicita approvazione del licenziante; la sezione 5 non garantisce accuratezza. Queste osservazioni **non equivalgono allo status diritti nel DB**, che non ho letto.

**Gate deterministici.** Identità/versione della claim, hash e riferimenti degli artefatti, approvazione del manifest, budget aggregato, receipt autentiche, registrazione dei diritti, incorporazione nella Verification Run e ledger durevole devono essere verificati dai rispettivi controlli del sistema. Questa risposta non li esegue e non li sostituisce. Le loro carenze non sono, da sole, confutazioni della claim storica.

### 6. Cinque query proposte, non eseguite

1. `site:senato.it "XIX" "S. 1" "Parrini" "13 ottobre 2022"`
2. `site:senato.it "2022" "disegni di legge" "annunzio" "Parrini" "bicamerali"`
3. `site:senato.it "2400" "3387" "composizione" "bicamerali"`
4. `(site:gazzettaufficiale.it OR site:normattiva.it) "adeguamento della composizione degli organismi bicamerali"`
5. `"Parrini" "organismi bicamerali" "2022" -site:senato.it -site:camera.it -site:github.com`

Le query sono piste di verifica, non risultati. In particolare, un esito della quarta richiederebbe comunque di dimostrare il collegamento con S.1, anziché dedurlo dalla sola somiglianza del titolo.
