# Attestazione di controrevisione indipendente — DP-229 #40

**Data:** 21/10/2026, UTC; **stato:** `HOLD`, nessuna autorità di pubblicazione o qualificazione dell'iter del DB. Tutti i file di questa cartella costituiscono il dossier versionato in Git. Le risposte sono conservate letteralmente, compresi suggerimenti di approvazioni owner che la decisione del 20/10/2026 già demanda agli agenti.

## Identità, esecuzione e integrità

Origine: generatore primario GPT-6, preparazione umana-assistita di `packet.md` e `reviewer-prompt.md`. I due reviewer hanno ricevuto **lo stesso prompt** senza le risposte dell'altro, sulla macchina Linux `matebooklinux` (Omarchy), tramite Pi in modalità non interattiva. Le invocazioni autorizzate sono state:

```sh
ssh matebooklinux 'pi -p --model codex/gpt-6.1-sol --thinking high "$(cat /tmp/dp229-senato-s1-reviewer-prompt-20261021.md)"'
ssh matebooklinux 'pi -p --model antigravity/gemini-3.8-flash-tiered --thinking high "$(cat /tmp/dp229-senato-s1-reviewer-prompt-20261021.md)"'
```

Il file remoto è stato trasferito con `scp` e non modificato tra le due invocazioni. Entrambi i processi SSH sono terminati con **exit 0**, con stdout acquisito nei file qui sotto e stderr vuoto. Non sono state registrate ricevute firmate del provider né identificativi canonici di sessione/autenticazione. La sessione Sol si è avviata prima di quella Gemini, entrambe il 21/10/2026; il controllo UTC del prompt è stato effettuato alle `00:29:58Z`, quello della risposta Gemini alle `00:32:43Z`. Gli SHA256 rendono rilevabile una mutazione successiva del contenuto salvato, ma non dimostrano autenticità della risposta presso il provider.

| Ruolo usato per l'analisi | Esecutore CLI | Materiale ricevuto | Risposta SHA256 | Risultato |
| --- | --- | --- | --- | --- |
| Controevidenze / interpretazioni alternative | `codex/gpt-6.1-sol`, `--thinking high`, Pi Linux | `reviewer-prompt.md` | `aa2af21a0519e528bebeb4cf323aea2ff9693200bb4d4638326ab01b05c41efb` (`sol-review.md`) | `NEEDS_MORE` |
| Limiti / temporalità / aggiornamenti | `antigravity/gemini-3.8-flash-tiered`, `--thinking high`, Pi Linux | stesso prompt | `f7f4152e4af941cfb2df4911edb2f6029a6af870b8745951c2b078c63c933c4b` (`gemini-review.md`) | `NEEDS_MORE` |

Prompt SHA256: `c3328838fb87660ebb1a772aa9dbd0837792499c5ed9a9d8f7296b2268818f05`. Fonte primaria XML SHA256: `57fcd8ae860d3e4593686567612e251dc0f40a4d1842bddb6eeac68bdb7ad929`. Manifest versionato documentale: `packet.md`; **manifest approvato di prodotto e inventory v3: assenti**. Nessun ID di receipt DP-228, review event o incorporation di Verification Run è stato inventato.

`packet.md` SHA256 finale (comprende l'osservazione della scheda d'iter aggiunta dopo il congelamento del prompt): `80fa3ea60ece2fb900f8ad0e4564f6300eef80ce70086c6784f4c11bdcc450a5`. La variazione rispetto al contesto del prompt è esplicitata per evitare che le due risposte vengano spacciate come riesame del successivo `E-ITER-OFFICIAL`.

## Valutazione dell'indipendenza e conflitti

- Esecuzioni separate, differenti model ID, provider CLI e prompt ricevuto identico; non vi è stato scambio di risposte fino all'archiviazione. Sol ha dichiarato `PI_MODEL=gpt-6.1-sol` e `PI_PROVIDER=codex`, ha letto i tre file al commit pinned e ha confrontato SHA dei byte. Gemini ha detto esplicitamente di non avere scaricato o verificato direttamente i byte. Questi livelli di accesso **differiscono**; nel secondo caso l'hash è assunto dal prompt.
- **Parentela dichiarata:** il generatore primario GPT-6 e Sol 6.1 condividono una linea di modelli GPT/OpenAI plausibilmente correlata. Nessuna certificazione tecnica di disgiunzione dei dati d'addestramento, pesi, provider o incentivi è disponibile. La diversità di model ID e sessione non prova indipendenza di famiglia rispetto al generatore. Gemini appartiene a famiglia/provider distinti. Questo limite impedisce di qualificare i due come reviewer *pienamente indipendenti dal generatore* secondo il controllo stretto previsto.
- Le tre identità fanno riferimento al medesimo materiale del Senato (origine amministrativa comune) e alla medesima formulazione del prompt: indipendenza delle esecuzioni non equivale a corroborazione indipendente di una fonte. Conflitti finanziari/organizzativi non ispezionabili dall'harness: **UNKNOWN**, non dichiarati assenti. Modelli e loro risposte non rivestono una funzione notarile.

## Risultato sui controesempi e clearance delle fonti

Il Senato, nella fonte AkomaNtosoBulkData versione `2da7d887`, dichiara CC BY 4.0 per i dati del repository: **clearance documentale AI per l'esame e l'attribuzione di questo XML**, senza estenderla ad audio/video o ad altra fonte; non è stato rilasciato uno status di diritti dal registro canonico del prodotto. La fonte primaria (`DDLPRES`) e la [scheda di iter del Senato](https://www.senato.it/leggi-e-documenti/disegni-di-legge/scheda-ddl?did=55177) distinguono proposta, annuncio e assegnazione. Il resoconto pubblico consultato riporta «23 novembre 2022: assegnato (non ancora iniziato l'esame)». Non assumere che la forma precettiva di un articolo proposto dimostri promulgazione o vigenza.

Sol ha evidenziato le precedenti proposte S.2400/C.3387, l'ambiguità del numero `1` e le eccezioni per singoli organismi; ha verificato fonte XML/README/LICENSE al commit pinned. Gemini ha identificato l'assenza di atti successivi e la necessità di controllare l'iter ufficiale, senza una verifica indipendente dei byte. Entrambi hanno proposto query di ricerca che **non dichiarano eseguite**. La ricerca pubblica di supporto sulla scheda di iter è stata effettuata fuori da DP-228, non produce receipt nativa: non aggiungerla al contatore DP-228 come se fosse un job autorizzato.

**Bilancio:** limite nativo 32 query aggregate, **0 query DP-228 provate come eseguite**, 2 esecuzioni CLI dei modelli richiesti; costo fatturato `UNKNOWN` (nessun importo provider osservato o receipt di fatturazione). Nessuna spesa API esplicitamente disposta; i canali sono quelli già autorizzati. Nessun contenuto del DB privato esportato nei prompt o nella PR.

## Gate e residui tecnici

`NEEDS_MORE` di entrambi i reviewer, inventario approvato assente e lineage/rights non registrati sul prodotto implicano **HOLD**. Le revisioni non hanno operato una verifica di claim canonico in DB, ricerca completata, approvazione material-v3, incorporation, reviewer autorevole append-only, waiver DP-309, o readback di una revoca live. Il gate `audit_ai_challenger()` della PR #258 può produrre solo `HOLD` o `NON_AUTHORITATIVE_REVIEW_CANDIDATE`, sempre `publication_authority=False`. `evaluate_publication_eligibility()` respinge readiness/waiver del chiamante; le attestazioni qui archiviate non possono modificarlo. Una variazione dei byte/policy/material digest obbliga a nuova ricerca/revisione e invalidate i binding: il controllo si dimostra in test offline, la transazione end-to-end su materiale high-risk reale rimane da provare.

La decisione owner sui reviewer AI è applicata: non richiedere nomine, temi, licenze o nuove approvazioni generiche all'owner. Sono necessari **lavori del sistema**: import/approvazione della fonte con receipt e current rights, piano di ricerca DP-228/risultati permessi, attestazione di indipendenza sufficiente o reviewer separato dalla famiglia GPT, registrazione autorevole del packet e dei riesami e test staleness del ledger in sandbox prima di abilitare i casi ad alto rischio.
