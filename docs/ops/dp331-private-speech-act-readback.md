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
