# #182 — prova reale podcast RSS → episodio YouTube (Pulp Podcast #68)

Questa cartella contiene l'evidenza del caso reale richiesto dal criterio
«Prova reale» di #182 e il canary privato che lo riproduce. Non contiene audio,
video, transcript né copie di contenuti di terzi: solo metadati pubblici, hash
dei due feed e l'identità verificata dell'episodio.

## Caso reale

| Lato | Valore verificato |
| --- | --- |
| Podcast RSS | `podcast-pulp-podcast` — <https://feeds.megaphone.fm/SONY4300078217> (self-link dichiarato nel feed) |
| Canale YouTube | `youtube-pulp-podcast` — `UCY99TnBJ8xyat2lpeN_hcEA` — <https://www.youtube.com/channel/UCY99TnBJ8xyat2lpeN_hcEA> |
| Catalogo Atom | <https://www.youtube.com/feeds/videos.xml?channel_id=UCY99TnBJ8xyat2lpeN_hcEA> |
| Episodio | `Ignazio Benito La Russa a Pulp Podcast. | Pulp Podcast #68` |
| GUID RSS | `992be98a-cb99-11f1-90b0-533d180ba42d` |
| Pubblicazione RSS | `2026-10-19T11:00:00` |
| Video risolto | `TpbFntO68Iw` — <https://www.youtube.com/watch?v=TpbFntO68Iw> |
| Pubblicazione Atom | `2026-10-19T11:00:23+00:00` |

Verifica del 23/10/2026, con letture HTTP dirette e senza intermediari.

## Perché l'associazione è editoriale e non somiglianza (approval-record)

1. Il feed RSS dichiara come titolo di canale `PULP PODCAST` e descrive il
   programma come il podcast di **Fedez e Mr.Marra**; il canale YouTube
   dichiara `<title>Pulp Podcast</title>` e, nella descrizione ufficiale della
   pagina `…/about`, «Pulp Podcast, il podcast di Fedez e Mr. Marra. Ogni lunedì
   alle ore 13:00 su YouTube e Spotify un nuovo episodio». Stesso titolo, stesso
   publisher, stesso calendario editoriale.
2. L'episodio esiste su entrambi i lati con **titolo identico carattere per
   carattere**, marcatura `Pulp Podcast #68` su entrambi e pubblicazione a 23
   secondi di distanza (RSS `11:00:00`, Atom `11:00:23`).
3. Il video ha `atom:id = yt:video:TpbFntO68Iw` coerente con `yt:videoId` e link
   `alternate` di tipo `watch`; nessun altro ID video rivendica `#68`
   nell'elenco Atom.
4. Il caso è anche il caso negativo più difficile: lo stesso ospite compare in 8
   clip/short con titoli diversi (`La Russa Core.`, `La Russa e i suoi BUSTI.`,
   `Il caro benzina secondo Ignazio La Russa.`…). Nessuna clip ha il marcatore
   serie/episodio e nessuna viene scelta per somiglianza: il canary rifiuta con
   `CANARY_YOUTUBE_COPY_UNPROVEN` il catalogo che contiene solo la clip.

**Registro di approvazione.** `config/source-registry.v1.json` contiene
l'associazione `pulp-podcast-youtube-v1` (`status=APPROVED`,
`policy_version=source-association-v1`, `approval_ref` verso questa sezione,
`reviewer_ref=ai-review:deepseek-v4.1-flash:2026-10-23:dp182`). L'approvazione
copre **solo** l'identità editoriale e il locator: non è una licenza, non è un
permesso del detentore dei diritti e non autorizza acquisizione o pubblicazione.

## Diritti della prova (decisione canary-scoped)

`rights-canary.v1.json` è la decisione esplicita usata dal canary:
`status=APPROVED`, host ammessi `feeds.megaphone.fm` e `www.youtube.com`,
scope `FETCH` + `STORE_METADATA`, con `MEDIA_DOWNLOAD`, `ASR_MEDIA`,
`REDISTRIBUTE` e `PUBLISH` **non** concessi, scadenza 23/11/2026.

Base: si leggono solo i metadati che i publisher pubblicano per la
distribuzione (feed RSS del podcast e feed Atom del canale), si conservano i
soli campi di identità e lo SHA-256 dei due feed, non si scarica audio/video,
non si produce transcript e non si pubblica nulla. Il canary rifiuta
(`CANARY_RIGHTS_SCOPE_UNSUPPORTED`) qualunque decisione che includa `ASR_MEDIA`
o `PUBLISH`, e rifiuta host non elencati.

## Difetto reale trovato e corretto

Il feed YouTube dichiara il canale due volte con due grafie: `yt:channelId` di
feed in forma a 22 caratteri **senza** prefisso `UC`, e `yt:channelId` di ogni
`entry` nella forma canonica `UC`+22. Il codice precedente confrontava le due
stringhe alla lettera, quindi **ogni feed reale** produceva
`YOUTUBE_ASSOCIATED_CHANNEL_UNVERIFIED` (e `YOUTUBE_ENTRY_CHANNEL_CONFLICT` nel
parser). Verificato il 23/10/2026 su tre canali pubblici indipendenti
(`UCY99TnBJ8xyat2lpeN_hcEA`, `UC_x5XG1OV2P6uZZ5FSM9Ttw`, `UCBR8-60-B28hp2BmDPdntcQ`):
stessa regola per tutti. La correzione confronta la sola identità canonica
(`poc/dichiarazioni_pubbliche/podcast_youtube_channel_identity.py`) e resta
fail-closed su prefissi, lunghezze o caratteri inattesi.

Prova RED/GREEN sul caso reale: sul codice precedente il canary risponde
`{"decision": "HOLD", "code": "YOUTUBE_ASSOCIATED_CHANNEL_UNVERIFIED"}` con exit 3;
dopo la correzione risolve `TpbFntO68Iw` con exit 0. Il nuovo
`tests/test_dp182_real_feed_identity.py` fallisce sul codice precedente (3 test)
e passa sul nuovo.

## Riprodurre

```bash
cd <checkout>   # o il worktree della issue
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=poc nice python3 -m dichiarazioni_pubbliche.podcast_youtube_canary \
  --registry config/source-registry.v1.json \
  --podcast-source-id podcast-pulp-podcast \
  --rights docs/evidence/dp182/rights-canary.v1.json \
  --episode-guid 992be98a-cb99-11f1-90b0-533d180ba42d \
  --out docs/evidence/dp182/canary-<host>-<data>.json
```

Ricevute di questa consegna (hash e identità, nessun contenuto):

- `canary-omarchy-2026-10-23.json` (host Omarchy)
- `canary-minipc-2026-10-23.json` (host MiniPC)

Gli hash dei feed cambiano a ogni nuovo episodio pubblicato: le ricevute
valgono per la finestra indicata da `generated_at`, infatti il canary rilegge
sempre lo stato corrente e non riusa catture precedenti.

## Cosa resta HOLD

- Il worker di produzione non usa il canary: prima di un locator reale servono
  `require_current_ingestion_relevance` e i record diritti `FETCH`/`STORE_BODY`
  nel registro privato, altrimenti il job resta `BLOCKED` senza fetch.
- ASR, download del media e pubblicazione restano non concessi: richiedono una
  decisione separata per contenuto/episodio.
- Il canary non scrive nel database, non accoda job e non pubblica
  (`publication: "HOLD"`, `side_effects` tutti a 0 nella ricevuta).
