# DP-317 — decisione di citazione esatta basata su licenza

Stato: implementata e provata su caso reale; **proiezione pubblica non attivata**.
Modulo: `poc/dichiarazioni_pubbliche/licence_excerpt_decision_v1.py`.
Pilota riproducibile: `tools/dp317_licence_quote_pilot.py`.
Issue: [#61](https://github.com/domenicomassafra/DichiarazioniPubbliche.it/issues/61).

## Perché serve

`evaluate_exact_quote_preflight` verifica solo la coerenza interna (locator,
capture, wording, binding) e per costruzione non concede mai una citazione
pubblica: un `revocation_epoch` fornito dal chiamante non è un'autorità live.
Il pezzo mancante era la metà «diritti»: nessun codice valutava la licenza della
fonte. Questo modulo fa solo quello, per un caso delimitato.

## Cosa è verificabile a macchina

Un `PERMITTED` richiede tutte queste condizioni, altrimenti la decisione resta
`HELD` o passa a `PROHIBITED` senza alcun rendering:

1. il contratto DP-317 source-only è coerente (`EXTERNAL_QUALIFIED_AND_LIVE_PROOF_REQUIRED`
   con `source_only_consistent=True`), quindi locator, capture, hash, intervallo,
   lingua, uso, giurisdizione e binding coincidono;
2. la base giuridica dichiarata è `SOURCE_SPECIFIC_LICENCE`; una permission
   caso-specifica non viene promossa a licenza (`LICENCE_GRANT_NOT_ESTABLISHED`);
3. il documento dei termini è identificato da SHA-256 e la sua versione coincide
   con quella citata dal claim (`LICENCE_TERMS_BINDING_MISMATCH`);
4. l'identificatore di licenza è in `LICENCE_GRANTS` e i marker obbligatori sono
   stati **osservati dentro il documento hashato**, non dichiarati dal chiamante;
5. l'attribuzione nomina titolare, locator, licenza e «testo non modificato»;
6. l'estratto resta dentro il limite di non-sostituzione (400 caratteri,
   valore di prodotto, non quantità legale);
7. la revoca è letta **a read-time** da un `LiveRevocationAuthority` e coincide
   con l'epoch del claim; un'epoch diversa revoca immediatamente.

I fatti di licenza (attribuzione obbligatoria, adattamenti, uso commerciale)
sono trascritti nella tabella `LICENCE_GRANTS` dal testo ufficiale, non
forniti dall'operatore: nessuno può affermare un permesso che la licenza non dà.

## Cosa resta chiuso

- `publication_authorized` è sempre `False`: la decisione produce un rendering
  **privato** attribuito e una ricevuta riproducibile, non un output pubblico.
- `EXCERPT_PROFILE_APPROVED` di DP-305 resta `False`: la proiezione web non è
  attivata da questo modulo.
- Diritti non basati su licenza (permissione puntuale, eccezione qualificata)
  restano `PROHIBITED`: richiedono la loro decisione separata.

## Fonti ufficiali delle licenze

| Licenza | Testo ufficiale | Fatti trascritti |
| --- | --- | --- |
| CC BY 4.0 | <https://creativecommons.org/licenses/by/4.0/> | attribuzione, adattamenti e uso commerciale ammessi |
| CC BY 3.0 | <https://creativecommons.org/licenses/by/3.0/> | come sopra, versione 3.0 Unported |
| CC0 1.0 | <https://creativecommons.org/publicdomain/zero/1.0/> | nessuna attribuzione obbligatoria |

Termini della famiglia UE usata nel pilota:
<https://commission.europa.eu/legal-notice_en> — contiene «Creative Commons
Attribution 4.0 International (CC BY 4.0)» e dichiara che il riuso è ammesso con
credito adeguato e indicazione delle modifiche, salvo diversa indicazione e
diritti di terzi. Base dichiarata: Commission Decision 2011/833/EU
(<https://eur-lex.europa.eu/legal-content/en/TXT/?uri=CELEX:32011D0833>).

## Rischio residuo dichiarato

La licenza copre i contenuti di cui l'UE possiede i diritti, salvo avvisi
specifici e opere di terzi. Per il caso pilota (una frase istituzionale della
presidente della Commissione, testo invariato, attribuzione, nessuna immagine,
nessun logo, nessun endorsement) il titolare è la Commissione e il rischio
residuo è un eventuale diritto di terzi sul testo citato: nessuna decisione di
pubblicazione viene presa da questo modulo.

## Riproduzione

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=poc python3 -m unittest tests.test_dp317_licence_excerpt_decision -v
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=poc python3 tools/dp317_licence_quote_pilot.py
```

Il pilota scarica profilo e legal notice ufficiali, stampa solo hash, lunghezze
e codici, e scrive il rendering privato e la ricevuta in una directory temporanea
con permessi `0600`. Nessun database, nessun provider, nessuna pubblicazione.
