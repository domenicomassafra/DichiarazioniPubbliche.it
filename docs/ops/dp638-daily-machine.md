# DP-638 — la macchina giornaliera

Una corsa al giorno porta una fonte pubblica fino a una dichiarazione pubblicata
con il suo verdetto, senza passaggi manuali.

```
config/daily-sources.v1.json
   -> scoperta (feed RSS/Atom di ogni fonte)
   -> cattura (testo dell'articolo, sottotitoli YouTube, o trascrizione)
   -> dichiarazioni (citazione esatta + persona risolta + momento + tema)
   -> verdetto (un passaggio del modello + un controllo indipendente)
   -> pubblicazione (record della proiezione pubblica)
   -> riepilogo serale al proprietario
```

## Comandi

```bash
# una corsa completa (scrive su database e proiezione)
PYTHONPATH=poc secret env OMNIROUTE_API_KEY -- \
  python3 -m dichiarazioni_pubbliche.daily_machine --report /tmp/daily-run.json

# prova senza scritture
PYTHONPATH=poc secret env OMNIROUTE_API_KEY -- \
  python3 -m dichiarazioni_pubbliche.daily_machine --dry-run

# esporta le dichiarazioni pubblicate nella proiezione pubblica
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
- Una dichiarazione senza una persona nominata nella fonte non si pubblica
  (`HELD_NO_SPEAKER`).
- Ogni record pubblicato porta l'indirizzo della fonte e la data.
- Un verdetto diverso da «non verificabile» richiede almeno un collegamento
  indipendente, scaricato davvero; se il modello non ne fornisce uno, il verdetto
  diventa «non verificabile».
- Se il passaggio di verifica e il controllo indipendente non concordano, il
  verdetto pubblicato è «non verificabile».
- Un'opinione non ha verdetto: viene pubblicata etichettata come opinione.

## Dove finiscono i dati

| Tabella | Contenuto |
|---|---|
| `content_item` | item scoperti; `metadata.ingestion_relevance` registra la decisione automatica di rilevanza con la sua ragione |
| `daily_capture` | il testo catturato, con impronta SHA-256 |
| `daily_statement` | una riga per dichiarazione, con citazione, persona, momento, tema, stato |
| `daily_verdict` | verdetto, spiegazione, collegamenti di evidenza, i due passaggi e le chiamate usate |
| `daily_run` | il rapporto della corsa del giorno |

## Unità systemd

- `dichiarazioni-pubbliche-source-poll-daily.service` esegue la macchina una volta
  al giorno (`OnCalendar=daily`) e poi esporta la proiezione.
- `dichiarazioni-pubbliche-evening-summary.timer` alle 20:30 invia il riepilogo
  con `hermes send` verso la destinazione già configurata.

La chiave di OmniRoute non sta in un file: l'unità la legge con
`secret env OMNIROUTE_API_KEY -- …`.
