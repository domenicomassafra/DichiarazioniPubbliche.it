# DichiarazioniPubbliche.it — mandato unico post-grilling: backlog completo, quattro subagenti nativi

Questo è l'unico prompt esterno da avviare, una sola volta, in una nuova chat ChatGPT-web
con il progetto DichiarazioniPubbliche.it e il connettore Chat On Steroids Core.
L'owner ha concluso il grilling e autorizza la preparazione completa del backlog.
Non fargli ripetere le risposte. Non avviare implementazione, raccolte o deployment.

<external-worker-contract>
Sei il coordinatore principale di un lavoro autorizzato dall'owner sul repository
/Users/domenico/Code/DichiarazioniPubbliche.it. Esegui il lavoro di pianificazione e
scrittura dei ticket fino alla consegna completa; non limitarti a proporre come farlo.

Autorità: le istruzioni esplicite dell'owner e i contratti locali applicabili prevalgono.
L'ultima risposta Q19 limita questo incarico a creazione, modifica e aggiornamento dei
ticket e della documentazione di pianificazione necessaria. L'implementazione è separata.
Le risposte dell'owner riportate qui sostituiscono le vecchie ipotesi del grilling.

Orchestrazione: crea esattamente quattro subagenti attraverso le capacità native di
Chat On Steroids, poi usa messaggi, status e handoff nativi. Tu sei il solo integratore.
I quattro subagenti non sono quattro chat che l'owner deve avviare manualmente.
Non sostituire questo con Orca, Codex collaboration, Oracle, un council o processi fittizi.

Scritture: preserva ogni modifica concorrente o non pertinente. I subagenti producono
pacchetti distinti, il coordinatore integra le modifiche nei file canonici in serie.
Nessun subagente modifica direttamente gli stessi ticket o documenti di un altro.

Git: lavora su main, un worktree, senza branch/worktree aggiuntivi, reset/clean distruttivi,
stash nascosti o force push. Committa solo le modifiche documentali pertinenti dopo i check.
Non fare push, non creare issue esterne, non inviare messaggi a terzi.

Completamento: continua fino al backlog completo e verificato, oppure registra il preciso
blocco reale. Un limite di contesto/tempo non rende completato un lavoro parziale.
Una proposta di ticket non è una feature implementata; un AC riscritto non è superato.
Nessuna disponibilità di modello, fonte, diritti, quota, approvazione o runtime può essere inventata.

Handoff esterno: soltanto tu scrivi la risposta terminale completa nel file adiacente:
/Users/domenico/Code/DichiarazioniPubbliche.it/tasks/prompt2prompt/20261010-231757-backlog-post-grilling/lane-01-backlog-master/001-backlog-master.response.md
Scrivila come ultima azione sul filesystem prima della risposta finale. Non creare ora
una risposta vuota, un segnaposto o una risposta dichiarata COMPLETE anticipatamente.
I quattro worker usano il canale nativo di finish/result; non producono risposte Prompt2Prompt.

Chat finale dopo avere salvato la risposta: soltanto
Risposta salvata in: /Users/domenico/Code/DichiarazioniPubbliche.it/tasks/prompt2prompt/20261010-231757-backlog-post-grilling/lane-01-backlog-master/001-backlog-master.response.md
</external-worker-contract>

# Mission

Trasforma tutta la ricognizione e il grilling in ticket realmente eseguibili: aggiorna
l'intero backlog esistente, crea tutti i ticket ulteriori necessari per gli outcome
approvati, elimina le ambiguità del piano e consegna una sola sequenza ordinata.

La missione del sito è integrata:
- sapere chi ha detto esattamente cosa, quando, dove e in quale contesto;
- aprire la fonte pubblica e il punto preciso che sostiene l'attribuzione;
- capire cosa le verifiche stabiliscono, smentiscono o lasciano senza prove sufficienti;
- confrontare la stessa proposizione o posizione tra persone e nel tempo;
- esplorare schede Persona, Tema, Contenuto e tracce longitudinali;
- rispondere a «cosa ha pubblicamente espresso X sul tema Y?» con documentazione datata;
- preservare correzioni, repliche, cambiamenti e storia delle versioni.

Non proporre all'owner di scegliere fra archivio, fact-checking e confronti.
Non ridurre la prima esperienza utile a un archivio privo delle altre capacità.
Un campione tecnico limitato serve a validare la missione completa, non a cambiarla.
Politici, influencer/creator, attori, conduttori, presentatori, storici e altre figure
pubbliche rientrano nell'ambito delle dichiarazioni di interesse pubblico.
Non restringere il prodotto a politici italiani, a una sola persona o a una sola lingua.

# Repository and current state

## Autorità e bootstrap

Repository Git autorevole:
 /Users/domenico/Code/DichiarazioniPubbliche.it
Repository remoto:
 https://github.com/domenicomassafra/DichiarazioniPubbliche.it
Branch:
 main
Runtime backend autorevole:
 MiniPC, host SSH minipc, utente/home osservati udodo /home/udodo
Mirror runtime:
 /home/udodo/src/DichiarazioniPubbliche.it — NON è un checkout Git
Database operativo:
 PostgreSQL dichiarazioni_pubbliche sul MiniPC
Hosting osservato:
 Cloudflare Tunnel verso MiniPC; un push GitHub non aggiorna la build servita.

Leggi le istruzioni locali prima del lavoro. Il contratto home /Users/domenico/AGENTS.md
vieta modifiche al sorgente/test dei servizi e applicazioni usati (Orca, OmniRoute core,
Chat On Steroids e analoghi). Questa è una repo dell'owner, ma questo mandato autorizza
solo documentazione e ticket, non modifiche applicative o a quelle applicazioni.

Se esiste tasks/index.md nel progetto, leggi index e goal/plan/worklog pertinenti.
Al checkpoint della ricognizione non esisteva: PLAN.md è il piano canonico.
Non sostituirlo con una task globale DStack di un altro progetto.

Leggi nell'ordine:
1. AGENTS.md.
2. PRODUCT.md.
3. CONTEXT.md.
4. ARCHITECTURE.md.
5. PLAN.md, soprattutto gli aggiornamenti dell'owner Q9–Q20.
6. HANDOFF.md come indice, non backlog duplicato.
7. docs/reviews/2026-10-10-independent-pre-grilling-reconnaissance.md.
8. docs/reviews/2026-10-10-open-ticket-reprioritization.md.
9. docs/reviews/2026-10-10-ux-redesign-audit-and-brief.md.
10. MEGA-HANDOFF-2026-10-10.md, LAUNCH.md.
11. FINAL-PENDING-GRILLING-2026-10-10.md e
    PROMPT-NUOVA-CHAT-VALUTAZIONE-POI-GRILLING-E-REDESIGN.md come mandati PRECEDENTI:
    questo prompt li sostituisce per il prossimo lavoro.
12. docs/tickets/README.md e tutti i ticket docs/tickets/DP-*.md.
13. ADR, policy e fonti tecniche pertinenti prima di specificare i ticket.

Le istruzioni vecchie «grilling una domanda alla volta», «missione archivio O verifica»,
«scegli prima una sola persona», «solo italiano», «trova reviewer umani ordinari» e
«implementa subito il vertical slice» sono superate dalle risposte esplicite qui riportate.
Preserva i documenti storici e segnala la supersessione senza fingere che il passato avesse
già il nuovo contratto. Lo stato runtime attuale resta distinto dal target futuro.

Skill:
- Usa plan-tickets per ticket verticali, tracciabilità, dipendenze e copertura.
- Usa plan-spec e plan-domain-modeling proporzionatamente se disponibili.
- L'owner ha già chiesto la scrittura del backlog: non inventare una nuova approvazione
  conversazionale per poter scrivere i ticket autorizzati.
- Rispetta il formato canonico docs/tickets/DP-*.md, non creare un secondo tracker .scratch.
- Non riattivare il grilling generale. Le domande tecniche trovano risposta nel codice.
- Prompt2Prompt riguarda solo questo trasporto esterno. Non invocarlo nei worker nativi.

## Fotografia Git e ticket

Baseline remota della ricognizione: ebdc4f83c8ab322bbad4529d0dca6b583409c912.
Ultimo commit prima della preparazione finale: 59a175cbc4fdb66cc0e2662176f4a30cae65bccd.
I commit successivi alla baseline sono documentali; al checkpoint c'erano otto commit
locali non pushati. La preparazione di questo prompt può aggiungere altri commit.
Rileggi git status/log e non imporre l'HEAD storico come preimage corrente.

Fotografia coerente riletta il 10 ottobre 2026:
125 ticket = 90 DONE + 20 IN PROGRESS + 6 BLOCKED + 9 FUTURE.
35 ticket non DONE, zero READY. PLAN e intestazioni dei ticket concordano.

I 35 sono:
DP-201, DP-202, DP-203, DP-204, DP-208, DP-214, DP-215, DP-229,
DP-233, DP-234, DP-301, DP-304, DP-307, DP-405, DP-406, DP-407,
DP-408, DP-409, DP-410, DP-412, DP-416, DP-417, DP-418, DP-419,
DP-420, DP-421, DP-422, DP-429, DP-507, DP-508, DP-701, DP-702,
DP-703, DP-704, DP-705.

Tutti devono avere una disposizione finale e requisiti/prove ancora aperti.
Leggi anche tutti i DONE per trovare capacità da estendere o errori di completamento:
nuovo requisito successivo != vecchio ticket falsamente completato.
Mantieni il DONE storico se provato per il contratto precedente e crea un delta/follow-up
tracciato; riapri soltanto se un AC già dichiarato superato fallisce realmente o ha prova
insufficiente. Non riscrivere un receipt storico come prova del nuovo target.

## Evidenze esistenti e limiti

Questa sezione è una fotografia datata, non una dichiarazione di freschezza futura.

- CI GitHub 38074800874 su ebdc4f8: 11/11 job verdi.
  https://github.com/domenicomassafra/DichiarazioniPubbliche.it/actions/runs/38074800874
  Non è una CI sul nuovo prompt né un canary di fonti reali.
- Preflight stable-v1: NO-GO, 49 blocker; 16 disposizioni Q-306, 4 artefatti, 29 gate ticket.
  Receipt SHA256:
  96fb7b178b371dcaac129496ba3f436a803ca063557f1e6a28be0d6346070c3f
- Il mirror aveva 627 percorsi selezionati: 543 MATCH, 41 DRIFT, 43 MISSING.
  Non erano tutti i file remoti. claim_promotion/public_api avevano drift; parti più
  recenti Senato/provider/local/account mancavano.
- Web/tunnel attivi e cinque timer attivi non provano che la nuova pipeline sia operativa.
- La build servita era datata 7 ottobre. SHA HTML:
  60e76f42a138b8a5fde390cee1c21c8b2053ee3f661c7a3ef78f49aebe49a1b0
- Proiezione /home/udodo/.local/share/dichiarazioni-pubbliche/public/v1/index.json:
  SHA adffa37fcd7c3b85af33c9c09ce0cb8b3c37925ed529894473dd5621f769dc73,
  zero dossiers/topics/contents, generation 7 ottobre.
- API corretto /api/v1/index.json; /api/v1/index non era l'endpoint corretto.
  Health ok, public-v2 DRAFT, fingerprint
  501348d9638ee3c4d929205d2e6dca7eb2c8a552ac006dee837ea032a739ae7a.
  Search records=[].
- SELECT produttivi READ ONLY: content_capture, passages, statement_candidate,
  claim_candidate tutti zero; private_source_rights_record zero.
  source_profile 13 non significa 13 autorizzazioni valide.
- Garlasco PAUSED, 18 included con diritti UNKNOWN, capture_authorized=0, discovery_hits=0.
  I 30 claim storici non provano la nuova catena Source→Capture→Candidate.
- Migrazione triage installata ma ledger vuoto: non ripetere «migrazione non distribuita»
  prendendolo da una nota più vecchia.
- DP-233: 104 Passage e 104 HELD Statement Candidate in store temporaneo Mac/MiniPC;
  non corpus produttivo. AKN pin bfac144eb5c54820971bc1020fece11aae56ec90,
  blob bec30c067a1a79e8b377af483cfc4bfb44d13896,
  393817 byte, SHA
  1cb2b5fc3cbc96701e52f06c34c3ae3cd494eb622aa3f124fb1a93a223e27476.
  121 speech candidate, cinque held per problemi specifici; source-family AC-233.10 aperto.
- DP-234: Senato RDF, 186 record in probe temporaneo, 12/14 AC; non grant DVNS generale.
- DP-417: tabella presente ma workflow reale non accettato.
- DP-422.1 real populated routes riaperto; DP-422.8 v4 comparison verificato.
- Fonte visibile, parser corretto e test verdi non danno da soli l'autorità di pubblicazione.

Non ripetere un audit infrastrutturale completo se questa evidenza basta a specificare
i ticket. Rileggi solo gli stati e i percorsi necessari; nuovi dubbi devono avere una
domanda concreta. Per SSH, solo read-only se serve; nessun sync, migrazione o deploy.

# Decisioni definitive dell'owner

## 1. Wording: parole esatte, mai sostituzione con parafrasi

L'ultima risposta è vincolante per il prodotto:
«il pubblico deve ricevere le parole esatte dette».
La parafrasi può stare soltanto nel riassunto separato della dichiarazione.

Specifica quindi:
- un'origine autenticata, parole originali e contesto necessario;
- nessuna parafrasi nel campo dichiarazione, come quote principale, come sostituto di
  una dichiarazione su card/lista/confronto o nella serializzazione del testo citato;
- una proposizione normalizzata può esistere internamente per atomizzazione, ricerca,
  matching/verifica; non è la dichiarazione del pubblico;
- un riassunto pubblico può parafrasare SOLO se è un componente/campo distinto,
  identificato come riassunto/sintesi e non prende il posto della dichiarazione;
- le parole esatte restano quelle della lingua originale;
- una traduzione italiana è una rappresentazione identificata come traduzione, collegata
  all'originale; non è la prova che la persona abbia pronunciato quelle parole italiane;
- non correggere semanticamente negazioni, modalità, numeri, nomi, tempi o termini legali;
- non migliorare editorialmente una citazione e poi chiamarla verbatim;
- omissioni, passaggi discontinui e interruzioni devono restare visibili e tracciabili;
- frammenti troppo brevi che alterano il significato non soddisfano il requisito;
- ASR/OCR possono sbagliare anche con una fonte autentica: prova della fedeltà, non slogan;
- nessun dato demo o frase immaginaria per riempire schermate apparentemente reali.

Il codice attuale vieta molti source/derived body nel pubblico e proietta una
PARAPHRASE: questo è un gap concreto, da risolvere con ticket di modello/proiezione/UI,
non dicendo che la parafrasi basta o che DP-221 DONE soddisfa già la nuova esperienza.

## 2. Fedeltà della citazione e diritti sono questioni separate

L'owner ha anche detto che non esisterebbe copyright sulle parole esatte dette.
Registra il desiderio di mostrare wording originale, non promuovere questa affermazione
a una regola giuridica universale. Parole isolate e opere/estratti creativi sono distinti;
la CGUE tratta come possibile riproduzione protetta anche un estratto breve originale:
https://eur-lex.europa.eu/legal-content/IT/TXT/?uri=CELEX:62008CJ0005
Questo non significa che ogni frase sia protetta, né che ogni citazione richieda permesso.

Il backlog deve ricercare e specificare il percorso lecito per citazioni esatte:
licenze, pubblico dominio verificato, eccezioni applicabili e source-family policies,
distinguendo testo, trascrizione, traduzione/edizione, fotografia, registrazione e embed.
Non inventare un limite universale di parole/caratteri o un grant per fonte raggiungibile.
Non assumere che tutto un documentario storico sia libero perché la persona è deceduta.

Importante: se il pubblico non può ricevere quel wording, non rimpiazzarlo con una
parafrasi nella dichiarazione. Conserva il caso privato con il gap preciso e ricerca
fonti alternative lecite, permessi o una base di uso effettiva. L'astensione non è
una soluzione di prodotto da celebrare: prima occorre tentare concretamente di risolvere.
Non creare un blocco legale generico per tutta la pianificazione o per tutte le fonti.
Qualified decisions già richieste nei registri restano tali; un ticket non le self-approva.

## 3. Context e speech act

L'owner ha usato un esempio ipotetico di uno storico che riporta e critica slogan
fascisti. Il frammento «viva il fascismo» preso da solo può rovesciare il significato.
NON registrare l'esempio come frase reale di Barbero: non è una fonte.

Distinguere almeno:
- parole pronunciate dall'attuale parlante;
- autore/persona citata nel discorso;
- discorso riportato e ricostruzione storica;
- imitazione/recitazione;
- ironia/sarcasmo dove documentabili;
- adesione, distanza, critica e confutazione;
- domanda dell'intervistatore, risposta, negazione e qualificazione;
- montaggi, riusi e discontinuità fra fonti/scene.

Non attribuire come posizione della Persona una frase pronunciata per citare,
imitare o confutare qualcuno. Nessun conteggio di secondi garantisce contesto.
Può bastare una scena coerente; occorre ampliarla se il significato dipende da prima/dopo.
Un video nascosto può avere contesto sufficiente nella scena, ma non si auto-autentica:
provenienza, montaggi, attribuzione, tempo e condizioni d'uso restano da valutare.
Il target deve prevedere indagine attiva, non tenere per sempre ogni caso in review.

## 4. Verifica, assenza di prove, opinioni e relazioni

L'owner accetta:
- astensione quando identità, contenuto o conclusione non sono sostenibili;
- «prove insufficienti» come risultato di un controllo effettuato, distinto da
  «non ancora verificato»;
- una piccola coda dei casi dubbi, rapida e orientata a una domanda concreta;
- ricerca attiva per risolvere chi/quando/perché/contesto prima di escalation.

«Mettere pending» non equivale a risolvere il caso.
Prevedi tentativi documentati, deduplicati e vari: originale, versione più completa,
archivi, metadati, trascrizioni alternative, documento primario, fonte indipendente.
Il budget operativo impone limiti misurabili, non una ricerca infinita gratuita.
Quando non si risolve, conservare lacuna e tentativi, evitare il verdetto inventato,
riaprire per nuove prove o versioni pertinenti. Non chiamare «falso» ciò che è solo
non supportato, non verificabile, opinione o ancora non controllato.

Le opinioni/posizioni sono contenuto rilevante per schede e confronti anche senza
verdetto true/false. Definire un public Statement che non esista solo come figlio
di un Finding fattuale. Non trasformare ogni posizione in una falsa affermazione.

Un cambio di posizione della stessa persona è diverso dalla divergenza tra persone.
Confrontare stesso take richiede equivalenza della proposizione e compatibilità
di tempo/scope/condizioni, non soltanto parole simili o lo stesso Tema.
Contraddizione != falsità di entrambe le frasi != prova di bugia intenzionale.
Non creare score/ranking della Persona o diagnosi di dolo/motivo.

## 5. Negazione di una precedente dichiarazione

L'owner ha usato un esempio ipotetico con un nome reale: una persona dice
«non ho mai detto X» e una fonte autenticata mostra una precedente frase X.
Non trasformarlo in un'accusa reale o in una dichiarazione attribuita senza fonte.

Scomponi:
1. atto di parlare/attribuzione e formulazione esatta precedente;
2. significato contestuale precedente (adesione oppure citazione/critica);
3. significato/scope della negazione successiva: «detto», «sostenuto», «inteso»;
4. verifica della negazione come affermazione storica;
5. relazione longitudinale documentata;
6. verifica separata del contenuto proposizionale X se ha senso fattuale.

Un riscontro autentico pertinente può smentire una negazione universale.
Non trovare la frase in un corpus incompleto non prova che non sia mai stata detta.
Non confondere «non ho mai sostenuto X» con «non ho mai pronunciato X».
Nessuna conclusione automatica sull'intenzione di ingannare.

## 6. Automazione finale, anche processuale

L'owner vuole automazione forte di ricerca, attribuzione, interpretazione,
verifica finale, scrittura dei risultati e futura pubblicazione per risultato
dopo validation/acceptance. Zero disponibilità per revisione editoriale testuale ordinaria.

Ha respinto l'idea di escludere genericamente i casi processuali: molti sono
documenti testuali e devono essere trattati con alta automazione.
Non riproporre come futuro requisito «un umano deve leggere ogni fact-check».
Non nascondere l'autonomia solo dietro una finta queue di review umana.

Per documenti processuali distinguere:
- autenticità/versione del documento e testo originale;
- estensore, autore, citato, dichiarante, organo giudiziario e Persona interessata;
- verbale che riporta una testimonianza vs accertamento dell'evento raccontato;
- affermazione di una parte, accusa, ipotesi, dispositivo e motivazione;
- indagato/imputato/condannato/assolto/archiviato e stati locali esatti;
- giurisdizione, data, efficacia, eventuale impugnazione/supersessione;
- identità/omonimia, OCR e documento incompleto;
- dati di minori, vittime o terzi incidentali che non diventano automaticamente pubblici.

Facilità di leggere parole in un documento non prova il fatto esterno riportato.
Specifica prove richieste e machine authority per classe di verifica, audit delle
decisioni, controlli avversari, revoca/rianalisi e fail-closed sulle lacune effettive.
I gate umani attuali DP-309/310/311 devono avere una proposta esplicita di migrazione;
non fingere che più credenziali di macchina siano due reviewer umani indipendenti.
Più agenti o più risposte dello stesso modello non creano fonti indipendenti.

Non promettere «infallibile» o 100% in generale. La richiesta di rigore diventa
errori misurati, casi adversarial, provenienza riproducibile, gold/reference credibile,
copertura/astensione, false attribution e false verdict distinti.
Una conclusione valutata dal medesimo generatore non è da sola ground truth.
I ticket devono distinguere autonomous verification, publication eligibility e
cutover/autorizzazioni ancora richieste dal runtime; questo incarico non li attiva.

## 7. Multi-persona, multilingua, permanente

Analizzare più persone insieme è consentito e desiderato quando utile.
Non imporre un solo soggetto per batch. Dedup, isolamento tra persone, lineage,
chunking, batching e replay devono impedire contaminazioni e perdere meno contesto.
Non basarti sull'ipotesi di una finestra infinita o di 500k–1M token disponibili.

Tutte le lingue delle fonti sono in ambito; non usare «solo italiano» come soluzione.
Conserva originale, language, traduzione italiana esplicita e controlli del significato,
soprattutto nomi/numeri/negazioni/date/modalità/termini processuali.
Supporto universale è un target, non capacità già provata: inventaria limiti correnti e
crea ticket d'estensione. Esempi tedeschi sono necessari per il pilot storico proposto.

Hitler e Mussolini sono casi iniziali proposti, insieme ad altre persone se utile,
con contenuti permanenti del prodotto, non una demo da buttare.
Morte del soggetto non rende fisso il corpus: nuovi ritrovamenti, digitalizzazioni,
traduzioni, versioni ed errori richiedono refresh e correzioni.
Nessuna promessa di «tutte le fonti» o corpus completo senza inventario della copertura.

Prima completare e provare la catena:
acquisizione fonti → testo/trascrizione → catalogo → immissione/candidati →
attribuzione/context → verifica/comparazioni → frontend → correzioni/test/runtime.
Solo dopo acceptance avviare mega raccolta.
Questo è l'ordine dei FUTURI ticket, non permesso di eseguire ora la catena.

## 8. Persona × Tema e sintesi

L'owner accetta una vista ottenuta incrociando filtro Persona e filtro Tema.
Non è richiesto un chatbot e non aggiungerlo come dipendenza.
Una breve sintesi precomputata delle posizioni documentate deve:
- citare dichiarazioni esatte e datate;
- usare qualificazioni del tipo «nelle dichiarazioni raccolte»;
- separare epoche, contesti, condizioni e cambiamenti;
- indicare la data/corpus/versione su cui si basa e le lacune di copertura;
- aggiornarsi quando cambiano dichiarazioni/fonti/correzioni;
- non dire cosa una persona «pensa davvero» oltre ciò che ha espresso;
- non attribuire una posizione permanente sulla base di una frase isolata;
- non trasformare una citazione storica/ironica in endorsement;
- non diventare quote principale o sostituire i verbatim.

Filtri e sintesi dovranno consumare una proiezione pubblica sicura già preparata.
Il baseline v1 senza LLM per richieste pubbliche resta il riferimento economico.
Non prescrivere nuova infrastruttura semantica per un'intersezione di due filtri.

## 9. Capacità umana, budget e provider

Reviewer editoriale umano ordinario disponibile: zero.
La persona che forse offrirà circa cinque ore settimanali è l'owner stesso,
per controlli rapidi soprattutto VISIVI/non testuali (ad esempio fotografie corrette).
Non assegnargli tutti i testi, tutto il fact-checking o tutte le traduzioni.
La disponibilità è approssimativa e va misurata; una foto approvata non approva un verdetto.
Usare un'immagine corretta/autorizzata o nessuna immagine; non inventare ritratti.

Target futuro di costo operativo: circa EUR10/mese, ipotesi da stimare.
La quota GPT-6 attuale è descritta dall'owner come temporaneamente molto abbondante.
Usare prima GPT-6 su Codex/ChatGPT-web; non assumere entitlement API o token infiniti.
Antigravity, audio, chiavi locali e modelli locali sono prove successive al percorso accettato.

Il progetto oggi configura GROQ per ASR; il riferimento parlato «Grok» non autorizza
a introdurre xAI o un altro provider in silenzio. Verificare le route effettive.
La comparazione futura deve misurare per giorno, fonte, content, persona/tema e job:
richieste, tokens/quotaunit, reset, retries/failures, input/output, audioseconds,
durata/latency, costo marginale e costo effettivamente fatturato dove disponibile.
Separare quota compresa in abbonamento, stima API, spesa misurata e dato ignoto.
Misurare energia incrementale locale se osservabile, dichiarare il metodo/baseline;
«API costa zero» non significa «calcolo locale gratis».

I ticket devono riusare ledger/receipt/cap esistenti, correggere classificazioni errate,
definire contenimento mensile e pause/reset. Non aumentare cap, creare abbonamenti,
fare overage, cambiare account/provider o avviare canary a pagamento in questo mandato.
È pianificazione, non consumo delle quote per stimare a intuito.

## 10. Automazioni economiche e copertura futura

L'owner accetta continuità di fonti/persone/temi seguiti e spazio per eventi rilevanti,
nuove persone e nuove fonti. Virality non deve essere l'unico criterio.
Nessun ranking politico/personale come proxy di rilevanza.

Specifica futuri discovery incrementali, conditional fetch, dedup/versioni, priorità,
budget, retry/backoff, outage, quote reset, cost-per-stage, idempotency, receipts,
misurazione giornaliera e salute della pipeline. Preferisci stadi cheap/deterministici.
Distingui backfill storico e sorveglianza futura. Il materiale invariato non richiede
ricontrollo LLM completo ogni giorno, ma fonti/evidenze materialmente cambiate sì.
Mostrare ultimo aggiornamento, ambito delle fonti seguite e lacune osservate.
Non dichiarare copertura totale del mondo o cattura in tempo reale garantita.

Non attivare timer o daemon mentre scrivi i ticket.
Non introdurre Kafka/Kubernetes/Neo4j/vectorDB o altre piattaforme senza misura.

## 11. Redesign e funzioni già richieste

Il proprietario considera l'UI attuale generica e desidera un redesign completo,
ma sceglierà LUI la direzione alla fine. ChatGPT Image o un altro modello sono
possibili strumenti che deciderà più avanti, non richieste di immagini ora.
Non selezionare o implementare un design al suo posto.

Prepara ticket per brief, alternative comparabili, scelta owner e implementazione
successiva. Le alternative devono usare gli stessi reader jobs/contenuti e
schermate desktop/mobile. Non inventare dati «reali» per rendere credibile il mockup.
I quattro territori storici (archivio editoriale, biblioteca/atlante documentale,
memoria temporale/timeline, ricerca compatta) sono opzioni, nessuno è stato scelto.

Conserva requisiti account già richiesti dall'owner: Google registration/login,
logout, deletion; privato di default, nessun privilegio editoriale o Studio.
Non cancellarli perché non necessari al primo record. Mantieni separati trigger e
prerequisiti di OAuth/privacy/security per il futuro.
Account lettore non attiva public intake. DP-507/508 rimangono condizionali.
Non introdurre bookmark/chat/feed social o nuove funzioni non richieste.

# Matrice obbligatoria dei requisiti

Usa questi identificatori come radici di traceability; integra eventuali requisiti
canonici ulteriori trovati nei documenti, senza perdere o duplicare quelli qui sotto.
Ogni riga deve raggiungere almeno un ticket/AC concreto o una precisa dipendenza
EXTERNAL/PENDING-OWNER; una nota «considerare in futuro» non copre un requisito.

| ID | Outcome da coprire | Lane primaria |
|---|---|---|
| R01 | Missione integrata fonti/verifiche/confronti/Persona/Tema | Coordinatore |
| R02 | Dichiarazione pubblica verbatim, mai parafrasi sostitutiva | C |
| R03 | Riassunto separato e identificato | C |
| R04 | Originali, traduzioni, language, derivation e meaning assurance | A/B |
| R05 | Locatore preciso, hash/versione, capture e source lineage | A |
| R06 | Contesto adattivo e speech-act/endorsement distinti | B |
| R07 | Speaker/author attribution non biometrica e omonimia | A/B |
| R08 | Source-family rights e percorso di citazione esatta | B |
| R09 | Fonti testuali, scansioni/OCR, media/caption/ASR | A |
| R10 | Catalogo, discovery, dedup, immutabilità e retention | A |
| R11 | Candidati→promotion riproducibile, review authority futura | A/B |
| R12 | Evidence role/scope/time e indipendenza delle famiglie | B |
| R13 | Controlli fattuali finali autonomi oltre regole numeriche | B |
| R14 | Autorità machine/versionata e pubblicazione dopo acceptance | B |
| R15 | Sostenuto/falso/prove insufficienti/non verificato distinti | B/C |
| R16 | Opinioni e Statement indipendente da Finding | B/C |
| R17 | «Non ho mai detto X» distinto da verità/endorsement di X | B |
| R18 | Equivalenza same-take e contesti compatibili | B/C |
| R19 | Stessa Persona nel tempo vs Persone diverse | B/C |
| R20 | Sintesi Persona × Tema precomputata con filtri e citazioni | C |
| R21 | Forte automazione processuale e documentaria | B |
| R22 | Stati procedurali, allegazione/accertamento, date/giurisdizione | B |
| R23 | Indagine attiva dei dubbi, tentativi e coda rapida | A/B |
| R24 | Correzioni, replica, revoca e propagazione tutte le superfici | B/D |
| R25 | Isolamento privato/pubblico e concurrent revocation fences | B/D |
| R26 | Multi-persona batch e isolamento/replay/contesto | A |
| R27 | Corpus storico permanente e multilingue, Hitler/Mussolini | A/D |
| R28 | Catena completa verificata PRIMA del bulk storico | Coordinatore |
| R29 | GPT-6 Codex/ChatGPT-web prima, provider comparison dopo | D |
| R30 | EUR10/month target empirico, quota/energy/costi distinti | D |
| R31 | Ledger corretto, cap mensile, outage/reset/backoff | D |
| R32 | Background economico e incremental distinto da backfill | D |
| R33 | Fonte/tema continuity + eventi, copertura/freshness | A/D |
| R34 | Owner ~5h visuali, zero reviewer testuale ordinario | D |
| R35 | Redesign scelto owner, alternative comparabili e QA | C |
| R36 | UX mobile/accessibilità e empty vs unavailable corretti | C |
| R37 | Account già richiesti preservati, intake/admin condizionali | D |
| R38 | Runtime authority MiniPC, drift e readback finale futuro | D |
| R39 | Benchmark credibile, false attribution/verdict e astensione | B/D |
| R40 | Quattro worker nativi, un integratore, niente implementazione ora | Coordinatore |
| R41 | Tutti 35 pendenti riconciliati, DONE storici + nuovi delta | Tutti |
| R42 | Un solo PLAN/DAG, nessun orphan/duplicate, ticket AC dimostrabili | Coordinatore |

# Gap tecnici da trasformare in ticket, non da correggere ora

Sono punti di ingresso osservati al 10 ottobre. Verifica gli attuali percorsi e linee:
non usare un numero di linea come API stabile. Preferisci estendere il seam canonico.

1. public_projection è centrato su Claim+Finding con wording pubblico PARAPHRASE;
   originale/translation body non proiettati. Il requisito verbatim chiede migrazione
   di public schema, dossier/Statement, API, search, HTML/JSON-LD/RDF e template.
2. TraceRecord.astro usa quote/block quote sulla parafrasi; la Statement page dichiarava
   paraphrase correttamente. Specificare coerenza su ogni superficie, non solo detail.
3. DP-221 DONE copre wording metadata/no-body baseline, non public exact quote nuovo.
4. Person deriva dai dossier; Persona senza finding/record non è rappresentabile come
   chiede DP-405.3. Distinguere assenza pubblica legittima da membership privata.
5. DP-407.4 «blocked/unresolved» non deve rivelare membership privata: stato pubblico
   solo se autorizzato da un contratto esplicito, non ogni hold del corpus.
6. relation_runtime.StructuredClaimRelationInput non contiene Person identity:
   posizione opposta può diventare POSITION_CHANGE anche fra due persone.
7. relation_policy richiede entrambi i published Finding; impedisce relazioni tra
   Statement di opinione documentati e non-fattuali.
8. evaluator di benchmark aveva temporal_stance→FACTUALLY_FALSE per stance opposte.
   Non assumere che il verificatore runtime usi quel ramo; specificare distinzione
   semantica e coverage senza trattare «opinione diversa» come falsità.
9. verification_runtime.verify accetta numeric_exact/range/delta/ratio/percent_change,
   historical_minimum/peak, legal_status_exact/text_exact; non general fact-checker.
10. finding_runtime ancora mappa risultati conclusivi a POLICY_HOLD.
11. claim_promotion richiede Statement/Claim review. Publication usa authority/replay,
    rights/privacy e HIGH/LEGAL attested packet. Nuova autonomia va specificata
    con percorso di migrazione e stati auditabili, non «bypass review=true».
12. DP-309/310/311: reviewer umani, separazione e HMAC authority locale off-DB.
    Conserva integrità storica, non fabbricare machine-as-human approvals.
13. challenger high-risk non ha ancora dimostrato authority durevole;
    la proiezione non può fidarsi di un bool dichiarato dal modello.
14. private_candidate_commit_fence dichiara di NON serializzare writer esterni di revoca.
    Servono scenari concorrenti per capture/candidate/promotion/publication/revoca.
15. context_integrity ha regex italiane e window_radius default 240 caratteri, limite
    32–2000: euristica utile, non prova semantica multilingue/anti-decontextualization.
16. wording_contract rischi traduzione coprono it/en/fr/es, non tedesco e tutte le lingue;
    LANGUAGE_RISK_RULE_UNAVAILABLE e machine senza human_reviewed restano held.
17. private_candidate_batch accetta 1–16 Passage e tool li processa serialmente.
    È già multi-persona possibile; non riscriverlo da zero per eliminare una
    restrizione a una persona che non c'è. Misurare batch reali e aumenti motivati.
18. Studio submit può produrre QUEUED_FOR_HUMAN_REVIEW con review/promotion/publication
    false: queue != lavoro concluso. Il nuovo target deve avere un vero machine path.
19. Fonte ufficiale testuale non va trasformata in falso segmento media 0:00;
    written provenance e timed provenance restano percorsi coerenti ma distinti.
20. projection cleanup rimuove stale alla rigenerazione; ritiro immediato su build
    distribuita, API/search/cache/sitemap e concurrency non è ancora provato.
21. candidate_extraction persiste MEASURED_PROVIDER_COST anche se calcola una stima
    token×rate/upper bound; Antigravity zero-rate può apparire measured zero.
22. worker_handlers_transcript conserva LOCAL_COMPUTE_UNMETERED nel receipt locale,
    ma totale API zero può diventare ZERO_COST. Non c'è misura Wh/kWh.
23. Cap USD5/day, USD1/source/day, USD0.25/job non implementano EUR10/month.
24. Account/accedi/Studio esistono in codice ma live 404 alla ricognizione; non farne
    una promessa già servita e non attivare OAuth adesso.

Il repository ha già discovery/capture/corpus/coverage/source-intelligence/matching/
quotation/context/wording/reanalysis/cost/rights/publication modules: riusa questi.
Un nuovo ticket non deve commissionare una seconda pipeline parallela.

# Lane ownership — quattro worker e un coordinatore

## Avvio nativo verificabile

Chat On Steroids era installato sul Mac, versione osservata 2.1.31.
Riferimento upstream verificato:
https://github.com/totec448-spec/chat-on-steroids/blob/main/docs/tool-surface.md

Il Core espone agents con azioni spawn, message, status, finish:
- spawn crea il set di worker con contesto condiviso e task per worker;
- message può svegliare/reimpiegare lo stesso worker;
- status mostra run, worker e slot;
- finish restituisce il risultato al prime e mette il worker a riposo.
I worker conservano la conversazione; non sono quattro prompt esterni da incollare.
Il riferimento documenta un ceiling di 400000 token conteggiati dall'app per worker,
non l'ipotetica finestra infinita. Non promettere autonomia oltre i limiti osservati.

Prima di spawn:
1. Scopri schema live e permissions del vero tool agents nel connettore.
2. Verifica il contesto/progetto approvato e la capacità di quattro worker.
3. Usa una sola creazione del run e quattro task con nomi stabili A, B, C, D.
4. Usa il modello GPT-6 richiesto tramite lo slug realmente disponibile, se il tool
   lo supporta; verifica senza inventare slug o dichiarare uno switch non osservato.
   Omissione di model può prendere un default: non chiamarlo GPT-6 senza prova.
5. Non ampliare permessi, installare app, creare account o cambiare policy da questo prompt.
6. Se una capacità manca, registra il preciso impedimento e continua la preparazione
   locale indipendente; non dichiarare «quattro agenti» simulando quattro sezioni.
   La richiesta di quattro subagenti resta incompleta finché non è eseguita realmente.

Rispetta il limite attivo osservato e il lifecycle nativo. Non lanciare una quinta lane.
Tu non sei uno dei quattro worker: sei il coordinatore/sole serial integrator.
I worker non delegano ulteriormente e non usano Prompt2Prompt.

## Write ownership

Cartella di lavoro del run:
 /Users/domenico/Code/DichiarazioniPubbliche.it/tasks/prompt2prompt/20261010-231757-backlog-post-grilling/

Ciascun worker può scrivere SOLO il proprio pacchetto di planning:
 native-packets/A-sources-corpus.md
 native-packets/B-verification-authority.md
 native-packets/C-public-product.md
 native-packets/D-operations-cost-release.md

Non precreare report COMPLETE o response worker.
Il worker può costruire il pacchetto durante il lavoro e poi consegnarlo tramite
finish nativo con path, hash, evidenze e residuali. Sono planning artifacts, non
risposte Prompt2Prompt né un secondo backlog canonico. Dopo l'integrazione etichettali
come pacchetti assorbiti con riferimento ai ticket reali, così non diventano task zombie.

Solo il coordinatore scrive:
- docs/tickets/DP-*.md;
- PLAN.md e docs/tickets/README.md se necessario;
- canonici PRODUCT/CONTEXT/ARCHITECTURE e ADR limitatamente a target/decisioni/piano;
- l'indice HANDOFF e le note di supersessione dei vecchi mandati;
- matrice coverage/decisione e handoff finale;
- la risposta esterna adiacente a questo prompt;
- commit documentali.

I worker propongono nuovi ticket con chiavi provvisorie A-NEW-01 ecc.; il coordinatore
legge gli ID esistenti e assegna gli ID DP-### senza collisioni. Nessun ID è riservato
da un numero inventato qui. Non cambiare ID/filename storici per riordinare il lavoro.

## Task A — fonti, acquisizione, testo, corpus, catalogo, Studio

Ticket pendenti primari:
DP-201, DP-202, DP-203, DP-204, DP-208, DP-214, DP-215, DP-233, DP-234,
DP-416, DP-417, DP-419, DP-420.
Questi 13 sono di tua competenza primaria, anche se altri commentano le interfacce.

Leggi adapter, source registry, discovery/provenance, safe fetch, capture/corpus,
written/media provenance, transcript/caption/ASR, candidate extraction/batch,
matching, Coverage Needs, Studio corpus/inbox/inspector e receipt reali.
Rileggi DP-205..207/209..228 e M1R DONE pertinenti per riuso e nuovi delta.

Consegna:
- ogni ticket primario con attuali AC/prove/residuali e proposta di aggiornamento;
- lacune per multi-persona, multilingua, tedesco, testi processuali/OCR e fonti storiche;
- distinzione tra originale testuale, citazione riportata, transcription di media;
- discovery e original-source resolution attivi per dubbi, parser/fetch leciti;
- catalog dedup/capture version/locator/hash/retention/source-family derivation;
- source acquisition profile in cui ogni uso ha base concreta, coordinato con B;
- Studio automation path che non finisce in una queue umana inesistente;
- source pilot completo prima della mega raccolta permanente;
- confini benchmark ASR/diarization: non diventano identity biometrica;
- ticket verticali con output/AC positivi e negativi e replay MiniPC futuro.

Mantieni distinta AKN corpus testuale da RDF sedute senza contenuti e da DVNS.
Non chiamare licenza di repository una licenza di qualsiasi sito/WebTV/video.
Non fare capture, download massivo, model call o import DB ora.

## Task B — contesto, prove, fact-check, autorità, diritti, correzioni

Ticket pendenti primari:
DP-229, DP-301, DP-304, DP-307, DP-418.
Questi cinque sono di tua competenza primaria.
Requisiti di follow-up toccano anche molti DONE: DP-104/110/111/117,
DP-216..228, DP-302..306/308..311, citation/high-risk/challenger/review/correction
e altri che devi identificare nel tree corrente. Non escluderli perché DONE.

Consegna:
- separazione speech act/endorsement, cita/critica/ironia e contesto adattivo;
- piano multilingual semantic assurance che non equivale a estendere una regex;
- quote-attribution e negazione di prior utterance, controprove e scope dei «mai»;
- Statement non-fattuale e relazioni con C, senza giudicare opinioni false;
- autonomous final verification per claim type, requirement profile e rule version;
- evidenze primary/role/authorityscope/effectivetime/independence, alternative e conflitti;
- forte automazione documenti processuali e mantenimento preciso degli stati;
- migrazione policy dal requisito di human review ordinario a machine authority
  auditable, distinta dai signoff esterni realmente qualificati;
- rights/exact quotation path: niente falso «nessun copyright» e niente fallback
  parafrase nella dichiarazione;
- coda eccezioni dopo tentativi concreti, budget/residual/priorità e riapertura;
- benchmark false attribution/false verdict e gold credibile;
- revoca transazionale, stale approvals, correction/reply/reanalysis;
- schema dei future AC di ritiro completo, coordinato con D;
- aggiornamento di privacy/legal planning che non self-approva Q-306/DP-307.

Non proporre come default generalista «basta un umano per tutti i casi» contro l'owner.
Non togliere attuali gate nel codice: specifica il target e le prove della migrazione.
Non includere una roadmap di esclusione permanente di high-risk non chiesta.
Atti ufficiali e quote autentiche sono prove con scope, non prova automatica di accuse.

## Task C — pubblico verbatim, schede, confronti, ricerca, redesign, accessibilità

Ticket pendenti primari:
DP-405, DP-406, DP-407, DP-408, DP-409, DP-410, DP-412, DP-421,
DP-422, DP-429.
Questi dieci sono di tua competenza primaria.
Rileggi public schema/API/projection/wording/search, template Astro/React,
component/design contracts e DONE DP-402/403/411/413/423..428/430.. pertinenti.

Consegna:
- piano completo pubblico exact wording, senza normalized paraphrase come dichiarazione;
- originale+translation identificata, summary separato, contesto e locatori precisi;
- schema/API/search/HTML/JSON-LD/RDF coerenti, no leak raw transcript/capture/private;
- public Statement indipendente da Finding, opinioni e incertezze distinte;
- Person senza record, Topic e Content visibility con regole autorizzate;
- same-take cross-person vs chronological same-person con B;
- filtri Persona × Tema, dati incrociati e sintesi precomputata citata/versionata;
- ricerca statica e pagine source/content/trace coerenti, non chatbot nuovo;
- empty genuine corpus vs no match/unavailable/private omitted;
- UX/accessibility ticket realmente verificabili e readback MiniPC futuro;
- redesign brief e alternative: scelta owner separata dall'implementazione successiva;
- DP-421 GO/NO-GO con prerequisite reali, non pubblicare la private collection;
- migrazione delle route preservando link/versioni, distinguendo fixture e production.

Evidenze UX live già raccolte:
sei pagine HTTPS 200; account/accedi/Studio 404; sito e indice legittimamente vuoti.
Home search attiva senza contenuti; stato vuoto sotto fold (~884px su390, ~986px su320).
Esplora «bilancio» invita a cambiare ricerca anche con corpus interamente vuoto.
Metodo ha 11 link indice prima del corpo, corpo ~844/902px.
Progetto overflow a320 (clientWidth320, scroll333) per anchor lungo.
Header mobile target ~22.39px. Skip link e dialog Escape/focus restore pass.
Vero zoom200% (outer1280 inner640) pass per sei route, non annulla overflow320.
Screen reader reale/contrasto/perf completi non sono provati.
Gli screenshot /tmp possono non esistere più; i limiti sono nel verbale canonico.

Non progettare frontend per un pubblico pieno solo di dati inventati.
Non generare immagini, non scegliere il vincitore, non implementare CSS/componenti.

## Task D — costi/quota, automazioni, operazioni, storico, account, release

Ticket pendenti primari:
DP-507, DP-508, DP-701, DP-702, DP-703, DP-704, DP-705.
Questi sette sono di tua competenza primaria.
Rileggi queue/scheduler/providers/operation-ledger/costpolicy/health/restore/
retention/release/hosting/account/privacy/security e ticket DONE M5/M6.

Consegna:
- misurazione giornaliera empirica successiva alla pipeline accettata;
- quota Antigravity/support nativeusage, Groq ASR e local compute energy distinti;
- correzione futura measured/estimated/unknown/zero-cost, minbill/retry/reset e
  contenimento mensile EUR10 target non convertito in falsa tariffa certa;
- background cheap, idempotente, con outage/backoff, no childjob unavailable;
- storico permanent/bulk dopo acceptance, incrementale per nuove fonti/discoveries;
- continuità fonti/persona/tema e coverage/freshness non marketing;
- lavoro visuale owner ~5h/settimana: asset correctness e coda rapida, misure non
  forza editoriale testuale o due reviewer inventati;
- account già richiesti, OAuth/privacy/security e activation trigger DP-507/508;
- sequenza mirror parity/canary/runtime/rollback/correction/readback reale futura;
- profili release informational vs first full slice vs stable-v1 distinti;
- DP-703 100 item/3 famiglie ecc.: requisito corrente vs proposta di acceptance
  graduata, nessuna cancellazione silenziosa dei livelli finali;
- monitor/cost/coverage dopo release, uso governato delle entitlement disponibili.

Fonti ufficiali di riferimento già lette (rileggi solo per raccomandazioni attuali):
https://antigravity.google/docs/cli/commands/usage
https://www.antigravity.google/docs/plans
https://console.groq.com/docs/speech-to-text
/usage (alias quota) riferisce quota/reset, non token universalmente convertibili.
Il default dei prezzi locali non prova billing gratuito. Non fare provider trials ora.

Fonti storiche candidate, non autorizzate/importate per decreto:
https://www.archivioluce.com/tag/benito-mussolini/
https://www.bundesarchiv.de/im-archiv-recherchieren/archivgut-recherchieren/nach-themen/archivalien-zu-adolf-hitler/
https://www.bundesarchiv.de/das-bundesarchiv/aus-unserer-archivarbeit/digitalisierung-von-archivgut-zum-nationalsozialismus-1933-1945/

# Required work — flusso del coordinatore

## Passo 1 — baseline reale e ownership

Rileggi scope finale, Git, ticket report e planning docs. Se trovi modifiche concorrenti
stabilisci ownership, preservale e scegli le sole scritture documentali pertinenti.
Non usare una vecchia fotografia per sovrascrivere uno stato più recente.

Comandi read-only di partenza, da eseguire in chiamate ordinate/batched dove indipendenti:
git status --short --branch
git log -5 --oneline
git branch -avv
git worktree list --porcelain
git stash list
python3 tools/report_ticket_status.py --json
python3 tools/check_repository_contract.py
Non fare fetch/push, accessi provider o scansioni indefinite per abitudine.

Leggi tutti i ticket, non soltanto titoli. Le classificazioni degli audit sono proposte,
non autorizzazioni per cancellare, ridurre AC o dichiarare implementato un target.
Il vecchio codice può essere correct rispetto al vecchio contratto e richiedere un delta.

## Passo 2 — shared context e quattro incarichi

Forma il contesto condiviso dalle decisioni e dai vincoli di questo prompt.
Usa i task A–D, passa ai worker le sezioni rilevanti in forma di messaggi nativi;
non dar loro quattro prompt/response manuali e non chiedere all'owner di gestirli.
Fai leggere a ogni worker contratto/requisiti e solo le parti del tree pertinenti,
senza dividere verticali in un esercizio astratto «backend vs UI vs test».

Ottieni status e identità dei worker reali. Registra run/worker ID non segreti in
coordinator.md nel run, con scope, packet path e stato osservato.
Mai confondere «task preparato» con «worker avviato» o silence con completed.

## Passo 3 — pacchetti concreti, revisione, integrazione seriale

I pacchetti devono contenere descrizioni integrabili e non soltanto elenchi di idee.
Ogni existing-ticket proposal deve indicare ID, vecchio scope/AC, prova storica,
delta richiesto, status motivato, dipendenze e acceptance futura.
Ogni new-ticket proposal deve avere il template completo sotto.

Tu rileggi i quattro pacchetti interi e il codice che sostiene i punti dubbi.
Risolve duplicazioni/interfacce e assegna ID nuovi in un unico passaggio seriale.
Non lasciare «B farà la parte cruciale» senza una dipendenza o un owner nominato.
Un worker che segnala un problema può essere riutilizzato con message, non una quinta lane.
Una nuova run spawn non è il meccanismo ordinario di continuazione del medesimo set.

Integra tutto in docs/tickets e PLAN. Aggiorna canonici solo dove necessario per
documentare owner target, glossary/scope, planned boundaries o supersession.
Un diagramma target non può essere presentato come runtime implementato.

Per i 35 esistenti usa una matrice 35/35:
ID | stato prima | stato dopo e motivo | AC preservati/prova | delta/new follow-up |
fase | hard blockers | soft coordination | evidenza necessaria | owner futuro.
Per i 90 DONE annota in una matrice compatta quelli toccati da nuovi requisiti e
l'esito del resto; nessuna necessità di riaprire ciò che ha una prova pertinente.

Non cancellare ticket/documenti. Se proponi merge/supersession:
preserva ID, AC, proof history e una mappa verso il ticket responsabile.
Un accorpamento organizzativo non consente di perdere AC o doppiare feature.
Uno scope ridotto proposto che altera un outcome non ancora approvato resta proposta
esplicita/PENDING-OWNER, ma non blocca la scrittura del resto del backlog.

## Passo 4 — formato di ciascun ticket

Usa il formato e gli status esistenti nel repository.
Gli status compatibili con report_ticket_status sono DONE, IN PROGRESS, BLOCKED,
FUTURE, READY (header e riga PLAN devono concordare).
Non introdurre status nuovi senza cambiare codice — vietato in questo mandato.
Un ticket futuro può avere Design readiness: READY e Status: FUTURE.
Distingui blocked implementation da pianificazione eseguibile.

Ogni nuovo/modificato ticket deve specificare:

# DP-### — titolo breve e concreto
Status: FUTURE oppure stato esistente motivato
Milestone: milestone reale/canonico
Depends on: lista pura di DP-### per HARD dependencies

## Problem
Trigger concreto, comportamento attuale e limite osservato.
Separare target richiesto da capacità già implementata.

## Outcome
Comportamento end-to-end visibile o prova operativa riproducibile.
Un solo outcome coerente, abbastanza piccolo per una finestra di lavoro fresca.

## Traceability & constraints
Rxx, decisioni Qxx, US/AC/DEC canonici dove esistono.
Vincoli rilevanti ereditati, incluso wording originale e zero implementation ora.
Non inventare riferimenti US/AC assenti.

## Scope
Input→persistenza/provenance→decisione→output/consumer; confini con ticket vicini.

## Non-goals
Funzioni che questo ticket non commissiona, senza negare requisiti affidati altrove.

## Dependencies and sequencing
Hard DP dependencies separate da soft coordination.
Prerequisiti esterni/owner con valore/artefatto necessario e modo di risolverli.
Un blocker falsificabile, non «aspettare AI infallibile».

## Acceptance criteria
Checkbox con identificatori stabili AC-###.N.
Happy path, caso negativo, replay/idempotency e condizioni di incertezza/revoca.
Assert osservabili, non «accurato», «robusto», «funziona benissimo» senza misura.
AC di implementazione nuovi non possono essere pre-spuntati dalla pianificazione.

## Validation / proof
Scenario runnable e valore/artefatto da leggere.
Check focalizzato, proof MiniPC quando runtime-affecting e consumer finale.
Misure non disponibili: precisa la calibrazione e ciò che manca, non inventare target
numerici di qualità/costo sostenuti da zero dati.

## Documentation, data, and migration impact
Boundary/changeplanned, compatibilità dei dati/proiezioni, history retention,
espansione/migrazione/contract solo se serve.
Riutilizzo del modulo esistente e alternative da valutare, senza prescrivere nuovo stack.

## Completion receipt
Per nuovo ticket: «non implementato; pianificazione soltanto».
Per esistente: conserva receipt datati e aggiungi checkpoint del nuovo delta.
In futuro: command/result, commit, schema/replay, real consumer e residuali.

Non commissionare refactor esteso come prerequisite universale.
Un refactor mechanical necessario può usare expand→migrate→contract con proof consumers,
ma solo se il codice evidenzia la necessità. No ticket cosmetici per gonfiare il backlog.
I riferimenti a file correnti sono evidence/seams da verificare, non assunzioni eterne.

## Passo 5 — piano cronologico e frontiera

Una sola sequenza di delivery, senza sprint laterali che sostituiscano il percorso utile:

Fase 0: riconciliazione requirements/domain/policy/schema planned e test matrix.
Fase 1: primo source→text→catalog→candidate→attribution/context privato coerente,
        con multiple persone/lingue nel set rappresentativo quando pertinente.
Fase 2: verification/statement/relations/Persona×Tema/public verbatim/correction
        integrati e provati nel primo percorso completo MiniPC.
Fase 3: acceptance qualità/costo/operatore e primo rilascio controllato se autorizzato.
Fase 4: mega raccolta storico permanente, persone insieme, source coverage/version refresh.
Fase 5: comparazioni provider/quota/energia, cap mensile e background economico sostenibile.
Fase 6: espansione incrementale, nuove fonti/temi/persone con telemetry/coverage/correzioni.

Redesign: brief e alternative possono essere pianificati in parallelo dove indipendenti;
implementazione della direzione finale dipende dalla scelta owner.
Account/intake/admin attivano i loro gate prima dell'exposure, non bloccano per forza
la prova privata o il primo lettore senza account.
Gli outcome devono restare integrati: non rinviare tutte le comparazioni al dopo-bulk.

La suddivisione sopra è una cornice di sequenza, non un comando per creare esattamente
sette ticket giganti o per spuntare milestones. Aggancia alle milestone reali.
Nel PLAN mostra una frontiera pronta, una sequenza successiva e dipendenze esterne precise.
Stime qualitative con metodo/uncertainty, niente ore/sprint promessi senza dati.
Non cancellare l'obiettivo stable-v1 per celebrare un micro-pilot.

## Passo 6 — reuse e official-source-first proporzionati

Prima di definire adozioni non banali, controlla capacità native e implementazioni locali.
Usa gli audit donor esistenti e official docs correnti sui punti che cambiano:
- Senato OpenData RDF (licenza dati/codice da verificare sull'artefatto);
- Senato AkomaNtosoBulkData resoconti XML, adapter locale già esiste;
- vero backend ParliamentRAG in Emeierkeio/parliamentrag-iswc,
  non confonderlo con il repo del sito;
- dataset Camera/graph con licenza separata rispetto al codice;
- Claim Polygraph/Meedan/Hypothesis come pattern, non stack da importare in blocco;
- faster-whisper/WhisperX/yente solo alternative condizionali con hardware/licenze/benchmark.

Mappa adopt/reuse/reference/reject con motivo legato al gap concreto.
Non installare, clonare stack inutili, chiamare paid API o importare dataset qui.
No top-five tools senza evidenza. Riuso locale prima di codice duplicato nella future spec.
Quando una doc parla di capacità futura, non venderla come funzionamento osservato.

# Constraints and non-goals

In questo mandato sono VIETATI:
- implementazione/refactor del codice applicativo o test, anche «piccolo fix ovvio»;
- modifiche a poc/, web/src/, db/, tools/, CI, package/deps, config/runtime .env;
- migrazioni, scritture DB, promotion, publication/retraction operative;
- acquisizione/transcription di corpus e bulk media;
- canary/inference provider e quote/billing trial;
- nuovi timer, scheduler, background services e installazioni;
- deploy/sync MiniPC, DNS/OAuth/credentials e aperture di endpoint;
- scelta o implementazione del redesign e generazione immagini;
- push, issue esterne, e-mail/Slack/Discord o messaggi a terzi;
- auto-approvazione legale o fonte dalla sola raggiungibilità;
- inventare citazioni, persone, URL, dati, review, costi, proof o un model switch;
- scoring/ranking delle persone, suggerimenti politici o inference di dolo;
- biometria facciale/vocale;
- dump pubblico di corpus/capture/transcript/private review.

Sono autorizzati:
- leggere codice, test e receipt per specificare bene i ticket;
- creare/aggiornare ticket, PLAN e documenti di target/decisioni necessari;
- native four-worker planning e packet/handoff;
- comandi/documental checks read-only o documentali;
- commit locale documentale coerente dopo verifica;
- fonti ufficiali web strettamente pertinenti con citazioni e data della verifica.

«Aggiornare codebase» in questo incarico significa repository/documentazione/backlog,
non sorgente applicativo. L'ultima risposta dell'owner prevale sulle richieste precedenti.
Scrivi ticket che consentano IMPLEMENTAZIONE futura autonoma con verifiche e boundary;
non perpetuare come target invarianti espressamente superate dall'owner.
Mantieni però i gate runtime presenti finché l'implementazione successiva li sostituisce
esplicitamente e li prova: non cambiare il codice in questa sessione.

# Verification

## Check documentali da eseguire realmente

Dopo la scrittura e l'integrazione, controlla:
python3 tools/check_repository_contract.py
python3 tools/report_ticket_status.py --json
git diff --check

check_repository_contract valida ticket/dependencies/cycles, links, JSON, hygiene.
Staga prima i nuovi documenti per includerli nel controllo dei link tracked, poi
leggi il diff staged e non committare file estranei.
report_ticket_status richiede esatta concordanza set PLAN/file e status.
La sua green output non prova feature runtime né copertura semantica dei requisiti.

Verifica anche coverage semantica:
- R01..R42 tutti coperti da ticket/AC o dipendenza concreta;
- tutti 35 originari con disposizione e ogni loro AC ancora attribuito;
- DONE toccati valutati, proof storiche conservate, delta nuovi distinti;
- nessun ticket nuovo senza root requirement;
- hard dependency DAG senza cicli e distinzione hard/soft leggibile;
- nessuna feature/AC doppia di due ticket;
- nessun nuovo AC applicativo spuntato «pass» perché è stato scritto;
- nessun requisito di reviewer ordinario umano reintrodotto per inerzia;
- wording public verbatim su tutte le superfici e summary separata;
- niente Statement/opinione bloccata concettualmente dall'assenza di factual Finding;
- niente cross-person chiamato position change;
- Persona×Tema precomputed, non mandatory chatbot;
- forte automazione processuale, allegations != facts e scope/time precisi;
- test-runtime futuri hanno reale input→output e readback, non solo full-suite;
- cap/stats misurati distinguono estimation/unknown e separano entitlement da API;
- primo percorso completo prima bulk e provider trials, owner sceglie redesign;
- un solo canonical PLAN, handoff solo indice, worker packets assorbiti;
- quattro agenti avviati davvero e tutti risultati letti/integrati/classificati.

Poiché il codice non cambia, NON rieseguire full Python/web/provider/browser suites
per costruire un'impressione di acceptance che questo incarico non richiede.
Non modificare gli script di validazione se segnalano errori: correggi i documenti
compatibili; se il requisito richiede un tool change, crea il ticket e registra il limite.
Il checker attuale vede hard dependencies soltanto se sono DP token/ranges puri:
non nascondere cicli inserendo prose nei Depends on. Mantieni una mappa semantica
esplicita per prerequisites milestone e authorizations che non sono DP dependencies.

## Artefatti finali

Consegna nel repository:
1. Tutti i ticket aggiornati/nuovi in docs/tickets con template completo.
2. PLAN unico ordinato e coerente con le intestazioni dei ticket.
3. Matrice requirements→ticket/AC, anche per ogni pending originario.
4. Decision/reconciliation note con supersession e DONE baseline/follow-up.
5. Aggiornamenti minimi canonici/ADR e HANDOFF come porta di ingresso.
6. Pacchetti nativi chiaramente assorbiti e coordinator state finale.
7. Un commit documentale coerente sul branch corrente, senza push.
8. La risposta esterna completa adiacente a questo prompt.

Non imporre un numero di nuovi ticket: servono quelli necessari, tutti di qualità.
Non dire «completo» soltanto perché hai prodotto la matrice senza i file dei ticket.
La matrice è prova di copertura, non sostituto delle specifiche individuali.
L'applicazione rimane non implementata per queste nuove richieste: dichiaralo.

# Response file

Percorso esatto:
/Users/domenico/Code/DichiarazioniPubbliche.it/tasks/prompt2prompt/20261010-231757-backlog-post-grilling/lane-01-backlog-master/001-backlog-master.response.md

Scrivi l'intero handoff, non solo un link a coordinator.md o la parola COMPLETE.
Includi schema e routing:

# Prompt2Prompt Response

Status: COMPLETE | PARTIAL | BLOCKED
Continuation: CONTINUE_NOW | WAIT_FOR_OWNER | WAIT_FOR_EXTERNAL | ACCEPTANCE_ONLY | NONE
Stop-Reason: COMPLETE | TIMEBOX_OR_CONTEXT | OWNER_ACTION | EXTERNAL_DEPENDENCY | PERMISSION | PHYSICAL_ACCEPTANCE | BLOCKER | OTHER
Attempt: 1
Response-Covers-Through: <HEAD corrente coperto realmente dalla consegna>
Updated-At: <ISO8601 con timezone>
Prompt: tasks/prompt2prompt/20261010-231757-backlog-post-grilling/lane-01-backlog-master/001-backlog-master.prompt.md
Lane: master-backlog-post-grilling

## Result
Quale backlog esiste ora; distinguere pianificazione completata da feature implementate.

## Native agents
Tool/schema osservati, run e quattro worker reali, modelli osservati,
task/lifecycle e readback delle consegne. Nessun secret/token.
Nessuna dichiarazione di quattro worker se manca questa prova.

## Changes
File/ticket esistenti modificati, nuovi ID, canonical updates, commit.
Nessuna application/runtime mutation autorizzata.

## Coverage and sequencing
Matrice R01..R42 e 35/35, delta DONE, DAG/frontiera, attività esterne e redesign owner.

## Verification
Comandi eseguiti, output ed evidenza fresca; check omessi con ragione.
Ticket completeness e comportamento runtime distinti.

## Conflicts or blockers
Conflitti di ownership, capacità native mancanti, residuali e owner esatto.

## Residual work
Per COMPLETE: implementazione futura pianificata non è residuo di questo mandato,
ma elencarla come prossimo incarico distinto.
Per PARTIAL/BLOCKED: tutti i documenti/ticket/coverage nativi ancora incompleti.

## Integration notes
Proof history preservata, status changes giustificati, dati e stato runtime invariati.

## Next exact action
Primo ticket/frontiera per la futura implementazione, senza avviarla;
oppure passo preciso per continuare una consegna parziale.

Semantica:
COMPLETE richiede Continuation NONE e Stop-Reason COMPLETE.
Un timebox/contesto reale normalmente produce PARTIAL + CONTINUE_NOW, mai finta closure.
Una dipendenza reale senza lavoro locale utile produce BLOCKED +
WAIT_FOR_OWNER oppure WAIT_FOR_EXTERNAL. Niente polling infinito per riempire il tempo.
Non chiedere all'owner di continuare la vecchia chat dopo il terminal handoff:
un eventuale proseguimento esterno usa un nuovo prompt auto-consistente che incorpora
questa risposta e HEAD attuale. Non sovrascrivere la coppia precedente.

Termina solo dopo avere salvato il file risposta e restituiscine l'assoluto.
