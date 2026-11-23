# DP-638 — fondazione della macchina giornaliera

Questa fase prepara il registro delle fonti, la persistenza PostgreSQL e i
contratti privati di lettura. La macchina non è ancora attiva: discovery,
cattura, estrazione, verifica, revisione e pubblicazione richiedono le rispettive
fasi e i relativi gate.

## Configurazione delle fonti

Il solo registro delle fonti è config/daily-sources.v1.json. Ogni voce ha:

- id: identificatore stabile e univoco;
- name e publisher: nome della fonte e soggetto editore;
- kind: public_rss oppure youtube_channel;
- discovery_url: URL HTTPS effettivo del feed;
- channel_id: obbligatorio per i canali YouTube;
- max_items_per_run: limite per singola fonte.

I limiti globali sono versionati nello stesso file. La configurazione abilita
la discovery e non concede diritti di acquisizione, trattamento o pubblicazione.
La rilevanza del singolo contenuto continua a passare dal contratto
ingestion_relevance; i controlli privacy e diritti restano separati. I modelli
e le consegne esterne non sono configurati in questo registro.

## Persistenza privata

La migrazione db/migrations/20261112-add-dp638-daily-machine.sql crea quattro
tabelle additive:

| Tabella | Dati |
|---|---|
| daily_capture | riferimento a content_capture, URL, tipo, data, hash del contenuto e del testo normalizzato |
| daily_statement | citazione esatta, offset, fonte, persona candidata, momento, tema e stato |
| daily_verdict | verdetto fattuale, spiegazione, evidenze, primo passaggio e controllo |
| daily_run | stato e contatori della corsa giornaliera |

La migrazione è ripetibile e non modifica righe preesistenti. Non contiene
aggiornamenti temporali ai job storici. Il censimento DP-304 registra queste
tabelle come set di migrazione versionato; lo schema canonico v1 resta intatto.
La cattura punta a un record già presente in content_capture; il corpo resta
nel CaptureBodyStore esistente. Lo store richiede un SourceFamilyUseGuard
che autorizzi EXTRACT_CANDIDATES, diritti CLEARED, hold NONE, retention
DURABLE_PRIVATE o DURABLE_PROVENANCE e un corpo ancora disponibile. Le fonti
public_rss e rss restano bloccate dal gate RIGHTS_HOLD. La cattura lega
contenuto, fonte e URL; la dichiarazione lega inoltre cattura, hash e URL con
una chiave esterna composta e verifica la citazione all'offset esatto.

Tutte le tabelle restano private. daily_statement.status ammette solo
CANDIDATE e stati HELD_*; non esiste uno stato PUBLISHED. Un candidato
persistito non è una review e non è una pubblicazione.

## Contratto dei verdetti

Le dichiarazioni fattuali possono avere uno dei seguenti valori:

| Valore persistito | Etichetta |
|---|---|
| TRUE | Vera |
| MOSTLY_TRUE | In gran parte vera |
| MISLEADING | Fuorviante |
| FALSE | Falsa |
| NOT_VERIFIABLE | Non verificabile |
| CONTRADICTORY_WITH_ITSELF | In contraddizione con sé stesso |

`claim_nature` è obbligatorio e non ha un valore predefinito. Le opinioni sono
registrate con claim_nature = OPINION e non possono avere
una riga in daily_verdict. La chiave esterna composta e il controllo nel
metodo save_verdict applicano questa distinzione anche a livello di database
e di store.

## Contratti di lettura

DailyStore espone letture esplicite:

- read_capture_metadata restituisce i metadati della cattura e la sua impronta;
- captured_content_ids_today restituisce i contenuti già catturati nella data;
- il corpo si legge tramite il CaptureBodyStore esistente, dopo il controllo
  dei diritti; DailyStore non espone una seconda lettura del corpo;
- read_statement e read_statements restituiscono campi dichiarati e, se
  presente, il verdetto associato;
- save_statement accetta una citazione solo se coincide con il testo catturato
  all'offset dichiarato e se cattura, contenuto e fonte coincidono;
- set_statement_status può portare un candidato in uno stato HELD senza
  riscrivere la citazione o riaprire uno stato terminale;
- read_verdict restituisce evidenze e i due passaggi;
- read_run restituisce stato, contatori e rapporto della corsa;
- statement_count restituisce un conteggio per data.

Le letture di dichiarazioni e metadati non includono il corpo della cattura.
DailyStore scrive solo le quattro tabelle DP-638; source, content_item,
content_capture e provider_receipt restano posseduti dai rispettivi store.
Nessun metodo dello store genera o scrive la proiezione pubblica.

## Prova locale della migrazione

Applicare la migrazione soltanto a un database PostgreSQL usa-e-getta che
contenga le tabelle esistenti source, content_item e content_capture definite
nello schema di base. Preparare una cattura già autorizzata con diritti
CLEARED, hold NONE e retention durevole, usando una fonte diversa da public_rss.

Poi applicarla due volte con psql -v ON_ERROR_STOP=1 -f
db/migrations/20261112-add-dp638-daily-machine.sql. Inserire un record di prova
in daily_capture collegato a content_capture e nelle altre tabelle, ripetere la
migrazione e confrontare gli identificatori, i conteggi e gli hash. Non applicare questa
migrazione al database del MiniPC in questa fase.

Il resoconto di lettura del MiniPC del 12 novembre riportava già 28 righe in
`daily_capture`, 57 in `daily_statement` e 51 in `daily_verdict`, e indicava che
la migrazione precedente era stata applicata in produzione. Questa prova non
è stata ripetuta in questa attività e nessuna migrazione è stata applicata al
MiniPC. `IF NOT EXISTS` non corregge tabelle già presenti con colonne o vincoli
diversi: prima di un futuro rilascio occorre confrontare lo schema e i dati
esistenti e preparare una migrazione di convergenza separata se necessario.

Il backup e il restore drill includono tutte e quattro le nuove tabelle. Il
timer giornaliero, l'invio di riepiloghi e la pubblicazione restano fuori da
questa fondazione.
