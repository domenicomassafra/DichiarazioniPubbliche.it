# DP-160 — Fonte ufficiale EUR-Lex per confronto Loki, 23 ottobre 2026

## Provenienza e riuso

- **Opera:** Regolamento (UE) 2024/1689, GU UE L del 12 luglio 2024,
  articolo 113, **versione originaria** ELI
  `http://data.europa.eu/eli/reg/2024/1689/oj`.
- **Italiano:** https://eur-lex.europa.eu/eli/reg/2024/1689/oj/ita
- **Inglese:** https://eur-lex.europa.eu/eli/reg/2024/1689/oj/eng
- **Diritti:** la nota legale di EUR-Lex
  https://eur-lex.europa.eu/content/legal-notice/legal-notice.html?locale=en
  autorizza il riuso commerciale e non commerciale dei testi giuridici,
  salvo restrizioni specifiche. Fonte attribuita sopra; estratti testuali
  brevi non modificati, esclusi loghi, immagini e materiali di terzi.
  La nota distingue la licenza CC BY 4.0 per contenuti editoriali e testi
  consolidati di proprietà UE: non attribuiamo automaticamente una licenza
  CC BY al testo normativo originario, al quale si applica il permesso
  di riuso dichiarato per i documenti giuridici.
- **Contesto:** l'articolo 113 distingue *entrata in vigore* da
  *applicazione*: la prima decorre dal ventesimo giorno dopo la
  pubblicazione; la seconda, nella versione originaria, dal 2 agosto 2026.
  Una versione consolidata del 27 luglio 2026 modifica alcune eccezioni:
  https://eur-lex.europa.eu/eli/reg/2024/1689.
  Qui i confronti riguardano soltanto le frasi originali sull'applicazione
  generale, non l'elenco completo delle eccezioni o un parere sul diritto
  attuale.

## Metodo falsificabile

La fixture `tests/fixtures/dp160_eurlex_article113_v1.json` conserva
due citazioni brevi **reali** (IT, EN), gli URL canonici, le date e i due
contrasti intenzionalmente errati, riconoscibili direttamente dal testo
ufficiale. Le coppie di claim sono un *oracle testuale indipendente
dall'algoritmo*: per ciascuna lingua la data è corretta, ma nella variante
negativa cambia il fatto giuridico dall'applicazione all'entrata in vigore.

`tests.test_loki_eurlex_case` usa il POC fixture-only per le tre fasi
donor: `Decompose` ripristina lo span, `CheckWorthy` riceve un voto
predefinito, `QueryGenerator` riceve una query predefinita. Passa al
validator incumbent `candidate_extraction.validate_provider_payload`
lo stesso claim contraffatto per stabilire esattamente quale controllo
strutturale esegue. Nessun generatore/model inference è interrogato.

L'esperimento misura **2 lingue × 1 esempio valido + 1 alterazione per
lingua**, senza holdout indipendente o campionamento rappresentativo.
Gli output Loki restano `HOLD`, senza rete, provider, persistenza,
verdetto, rights clearance editoriale o pubblicazione. Il costo osservato
è zero chiamate *nel test fixture-only*, non una stima di costo o latenza
di inferenza Gemini/Antigravity. La precisione/recall di produzione non
è deducibile da esempi costruiti manualmente. Una revisione AI con modello
diverso non è attestata: la decisione corrente del repository autorizza
soltanto Gemini 3.8 Flash tramite Antigravity.

## Esito

Eseguire `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=poc python3 -m unittest
tests.test_loki_eurlex_case tests.test_loki_private_poc -v` tramite
resource guard. La prova dell'esecuzione effettiva, il commit remoto e
il readback del MiniPC sono registrati nella
[issue originale #160](https://github.com/domenicomassafra/DichiarazioniPubbliche.it/issues/160).
La differenza con il validator incumbent è soltanto la nuova guardia
lessicale del POC: entrambi richiedono ancora verifica semantica e fonti.
