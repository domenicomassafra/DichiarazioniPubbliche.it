# DP-312 / #331 — readback privato di speech-act su fonte Senato

Il campione autentico e' il singolo documento Akoma Ntoso gia' verificato nelle
issue [#326](https://github.com/domenicomassafra/DichiarazioniPubbliche.it/issues/326)
e [#330](https://github.com/domenicomassafra/DichiarazioniPubbliche.it/issues/330):
`SenatoDellaRepubblica/AkomaNtosoBulkData`, commit
`bfac144eb5c54820971bc1020fece11aae56ec90`,
`Leg19/Atto00055187/resaula/01457617-ra.akn.xml`;
Git blob `bec30c067a1a79e8b377af483cfc4bfb44d13896`,
SHA256 dei byte `1cb2b5fc3cbc96701e52f06c34c3ae3cd494eb622aa3f124fb1a93a223e27476`.
Il documento e' attribuito al **Senato della Repubblica** (CC BY 4.0,
README/LICENSE ufficiali verificati con hash nella #330, 24/10/2026).

La #330 ha registrato su MiniPC una **sola Capture privata durevole** e un
rights record CURRENT con le sole operazioni
`DISCOVER_METADATA`, `FETCH`, `RESEARCH_CAPTURE_PRIVATE`, `STORE_BODY`.
La #357 ha poi registrato un successore CURRENT con `PARSE_TEXT` aggiunto
agli stessi quattro usi, senza revoche. Il readback accetta entrambi gli
scope privati esatti, richiedendo ancora `STORE_BODY` sul record CURRENT e
conservando la verifica di policy, review, scadenza, hash e revoca.
Non vi sono permessi dedotti per `EXTRACT_CANDIDATES`, identificazione
approvata, traduzione pubblica o pubblicazione.

`tools/dp331_senato_private_speech_readback.py` rilegge il record CURRENT,
la Collection, la Capture e i byte immutabili, controlla SHA256 + Git blob,
poi passa **al massimo tre ordinali espliciti** all'importatore AKN gia'
presente e all'interfaccia `assess_speech_act_context`. Il risultato contiene
solo gli identificatori source-bound, l'etichetta ufficiale di ruolo come
*ipotesi*, l'atto lessicale e i segnali di astensione. L'importatore non prova
l'utterer al livello del singolo segmento e un documento stenografico puo'
includere piu' turni nel medesimo elemento `speech`: `turn_complete=False`
e `HOLD` restano obbligatori. Nessun testo fonte, XML o testo derivato viene
stampato; nessun oggetto Claim/Statement viene scritto.

Il tedesco e' **solo una traduzione di prova derivata privata**: il documento
originale osservato e' italiano, non esiste una variante ufficiale DE
attestata per questo campione. Con `--german-draft-file` si usa un testo
italiano/tedesco fornito per il confronto lessicale, sempre
`NEEDS_REVIEW` con identita' del parlante DE sconosciuta. Le ambiguita'
di negazione, modali, sostantivi/citazioni e confine di turno non sono
risolte da equivalenza parola-per-parola.

Sul MiniPC (read-only, senza avviare alcun modello):

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=poc python3 tools/dp331_senato_private_speech_readback.py \
  --database-url dichiarazioni_pubbliche --ordinal 15 --ordinal 19
```

Il test Mac Studio `tests.test_dp331_private_speech_probe` copre ruoli
distinti, REPORT/QUOTE, astensione sull'italiano, negazione DE derivata,
replay dei fingerprint e nessuna authority di estrazione/pubblicazione.
Il contratto richiesto nella #331 resta quello di
`tests.test_dp312_candidate_context_extraction tests.test_dp312_negative_indefinites`.
Questi controlli tecnici non sostituiscono gold multilingue autentico e review
indipendente, ne' autorizzano il GO-PUBLIC.


## 2026-10-25 — esempio IT→DE legato a quote span, ancora in attesa di review indipendente

La singola Capture e i diritti privati sopra restano invariati. Per la seduta
2025-05-29, `speech:19` (210 caratteri di `review_text`), l'intervallo Python
**[64, 94)** contiene una domanda italiana di 30 caratteri, SHA256 UTF-8
`ebc7d16add183a126a613606b8465bbd9c985a27ac6f3ab8ce2a8d86acf0bc5a`.
La provenienza primaria si verifica con la Capture, il Git blob e lo SHA256
del documento indicati sopra; gli offset sono relativi a `speech.review_text`,
non agli offset dei byte XML. Il suo contesto comprende una risposta breve e
etichette di parlanti in successione: la voce e l'autore della risposta non
sono accertati dal solo elemento XML. Nessuna quote/person identity approvata.

Proposta DE generata da GPT-6, **traduzione privata derivata**, NON testo
originale tedesco del Senato e NON traduzione esaminata:

`Ist die Stellungnahme also positiv?`

Confronto da sottoporre a gpt-6.1-sol: mantenimento della forma interrogativa
e della particella inferenziale “quindi/also”; “parere favorevole” reso con
“Stellungnahme positiv”, non assunto come equivalente tecnico senza revisione.
L'italiano è l'originale immutabile, il tedesco un derivato separato con hash
proprio. Controllo negativo privato: `Ist die Stellungnahme also nicht positiv?`
introduce negazione e deve restituire `NEGATION_CHANGED`. Il contesto
contenente risposta e più etichette non consente di inferire un endorsement:
sia la fonte che il derivato restano HOLD, con quote author UNKNOWN.
Le euristiche possono segnalare falsi positivi sui sostantivi tedeschi con
maiuscola; `translation_review=NEEDS_REVIEW` non è un giudizio di parità.

Comando readback dal mirror runtime MiniPC, usando un file DE temporaneo
preparato dall'operatore in uno spazio privato:
```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=poc python3 tools/dp331_senato_private_speech_readback.py \
  --database-url dichiarazioni_pubbliche --ordinal 19 \
  --quote-start 64 --quote-end 94 --german-draft-file /tmp/dp331-it-de-20261025.txt
```
Il file DE contiene solo la frase proposta sopra. Il comando rilegge
la Capture gia' autorizzata in sola lettura, produce solo metadata/hash,
non materializza nuovi Candidate e non muta i permessi della registry.
Operazioni consentite attuali: DISCOVER_METADATA/FETCH/RESEARCH_CAPTURE_PRIVATE/
STORE_BODY; EXTRACT_CANDIDATES e PUBLISH non sono autorizzate.
La review indipendente resta necessaria prima della chiusura di #331.
