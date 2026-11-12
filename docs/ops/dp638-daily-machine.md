# DP-638 — la macchina giornaliera

Una corsa giornaliera salva le fonti e prepara dichiarazioni con parlante verificato,
verdetto e doppio controllo. La pubblicazione richiede che il bundle superi la
verifica e sia installato: una riga `PUBLISHED` nel DB significa solo *pronta*.

```
config/daily-sources.v1.json
   -> scoperta (feed RSS/Atom di ogni fonte)
   -> cattura (testo dell'articolo, sottotitoli YouTube, o trascrizione)
   -> dichiarazioni (citazione esatta + persona risolta + momento + tema)
   -> verdetto (un passaggio del modello + un controllo indipendente)
   -> proiezione candidata (solo etichette supportate dal web pubblico)
   -> rilascio verificato e controllo del sito (passo separato)
   -> riepilogo serale basato esclusivamente su URL pubblici raggiungibili
```

## Comandi

```bash
# una corsa completa (scrive sul database; il servizio esporta a parte)
PYTHONPATH=poc secret env OMNIROUTE_API_KEY -- \
  python3 -m dichiarazioni_pubbliche.daily_machine --report /tmp/daily-run.json

# prova senza scritture
PYTHONPATH=poc secret env OMNIROUTE_API_KEY -- \
  python3 -m dichiarazioni_pubbliche.daily_machine --dry-run

# esporta nella proiezione candidata solo dichiarazioni ammissibili
PYTHONPATH=poc python3 -m dichiarazioni_pubbliche.daily_publication \
  --projection ~/.local/share/dichiarazioni-pubbliche/public-projection/index.json

# riepilogo serale, in prova (non invia nulla)
PYTHONPATH=poc python3 -m dichiarazioni_pubbliche.daily_machine --evening-summary \
  --summary-file /tmp/summary.txt

# riepilogo serale, invio reale (lo fa il timer delle 20:30)
PYTHONPATH=poc python3 -m dichiarazioni_pubbliche.daily_machine --evening-summary \
  --deliver --summary-file ~/.local/state/dichiarazioni-pubbliche/evening-summary.txt
```

## Aggiungere o togliere una fonte

Solo `config/daily-sources.v1.json`. Ogni voce ha `id`, `name`, `publisher`,
`kind` (`public_rss` o `youtube_channel`), `discovery_url` e, per YouTube,
`channel_id`. Il campo `max_items_per_run` limita gli item per fonte.

## Regole di accuratezza applicate nel codice

- La citazione pubblicata è sempre la sottostringa esatta della fonte catturata:
  l'estrattore può aggiungere punteggiatura, il codice riporta la forma originale
  e scarta ciò che non trova.
- Il nome della persona deve attribuire direttamente *quella* citazione, con
  verbo di dichiarazione e virgolette o etichetta del parlante nei sottotitoli;
  una semplice menzione del nome non basta (`HELD_NO_SPEAKER`).
- Ogni record pubblicato porta l'indirizzo della fonte e la data.
- Un verdetto diverso da «non verificabile» richiede almeno un collegamento
  indipendente, scaricato davvero; se il modello non ne fornisce uno, il verdetto
  diventa «non verificabile».
- Se il passaggio di verifica e il controllo indipendente non concordano, il
  verdetto pubblicato è «non verificabile».
- Le opinioni non ricevono un verdetto fattuale. Il web v2 ancora non offre
  etichette per opinione, parzialmente vero e non verificabile: restano in DB,
  senza essere proiettate sotto un'etichetta inesatta.
- Il riepilogo serale usa l'API pubblica e verifica gli URL prima di contarli;
  il timer è disattivato finché la release non supera la review indipendente.

## Dove finiscono i dati

| Tabella | Contenuto |
|---|---|
| `content_item` | item scoperti; `metadata.ingestion_relevance` parte da `CANDIDATE` e passa automaticamente a `RELEVANT` solo se il parlante è attribuito, oppure `UNCONFIRMED`, sempre con la ragione |
| `daily_capture` | il testo catturato, con impronta SHA-256 |
| `daily_statement` | una riga per dichiarazione, con citazione, persona, momento, tema, stato |
| `daily_verdict` | verdetto, spiegazione, collegamenti di evidenza, i due passaggi e le chiamate usate |
| `daily_run` | il rapporto della corsa del giorno |

## Unità systemd

- `dichiarazioni-pubbliche-source-poll-daily.service` esegue la macchina una volta
  al giorno (`OnCalendar=daily`) e poi esporta la proiezione.
- `dichiarazioni-pubbliche-evening-summary.timer` è preparato per le 20:30,
  ma resta inattivo finché il rilascio e gli URL non sono verificati.

La chiave di OmniRoute non sta in un file: l'unità la legge con
`secret env OMNIROUTE_API_KEY -- …`.
