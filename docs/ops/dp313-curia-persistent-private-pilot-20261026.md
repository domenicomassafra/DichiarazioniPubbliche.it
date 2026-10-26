# DP-313B — Originale CURIA nella pipeline persistente privata (26 ottobre 2026)

## Fonte, diritti e decisioni

- Originale ufficiale: Corte di giustizia UE, Ottava Sezione, sentenza del **25 giugno 2026**, causa **C-622/24 P** (VT/Commissione europea), **ECLI:EU:C:2026:519**: <https://juris.curia.europa.eu/juris/document/document.jsf?docid=312911&doclang=IT>.
- Testo canonico verificato sull'originale: `sha256:1bcb37cfb1d9f6c949dbe0b57fdb391ad9f5ba89102ba48271c53a25f40a72ae`. I byte HTML possono cambiare per controlli di sessione; hash e offset sono riferiti al testo della sentenza normalizzato.
- Avviso ufficiale CURIA sul diritto di riproduzione della giurisprudenza con citazione della fonte: <https://curia.europa.eu/site/jcms/qua1_6625/>. Opere di terzi richiedono permessi separati. Il registro `private_source_rights_record` limita le attività a `FETCH`, `RESEARCH_CAPTURE_PRIVATE`, `STORE_BODY`, `PARSE_TEXT`, `EXTRACT_CANDIDATES`, con scadenza a 7 giorni e attribuzione; non concede `EXCERPT_PUBLIC`.
- Il soggetto **VT** resta anonimizzato; nessuna verifica della sua identità, della legittimità di ulteriori usi di dati personali o della versione giudiziaria finale è dedotta dal copyright. Privacy, negazioni, merito e pubblicazione: **HOLD**. La decisione EPSO del 2022 è solo *riferita* dalla Corte, senza originale EPSO autenticato.

## Percorso realizzato

`Fonte ufficiale HTTPS → Source/Content/Collection → diritto corrente per uso → Content Capture privato → quattro Passage con offset/hash sull'originale → quattro Statement Candidate HELD → readback da PostgreSQL → replay della famiglia CURIA`. Nessuna chiamata a modelli, nessun Atomic Claim, Finding o contenuto pubblico.

Il parser riusa `evaluate_curia_private` e conserva ruoli separati: `PARTY_ALLEGATION`, `PRIOR_DECISION_REPORTED_BY_COURT`, `COURT_DISPOSITION`, `COURT_ANNULMENT_OF_REPORTED_DECISION`. Ogni valutazione dei fatti sottostanti rimane `NOT_EVALUATED`. Le date 15/07/2022 e 25/06/2026 sono ancoraggi testuali distinti, **non** attestazioni automatiche di stato processuale efficace.

`tools/dp313_curia_persistent_pilot.py` senza flag legge e valida il documento, senza scritture. Con `--apply-private-intake`, richiede un nuovo fetch ufficiale, diritto privato corrente, guard di acquisizione e readback completo. Rifiuta l'applicazione di un HTML fornito da file; un URL di redirect diverso e un mutamento dell'hash canonico interrompono il flusso. Un secondo fetch con la *stessa* sentenza canonica riusa la catena già verificata anche se sono cambiati i byte HTML di sessione.

## Prova su MiniPC e ripetizione

Sul MiniPC Ubuntu, PostgreSQL `dichiarazioni_pubbliche` e `dichiarazioni-pubbliche-web.service` erano raggiungibili. Lo script è stato provato da un checkout di staging temporaneo con `poc` e il precedente readback collegati al mirror, senza sostituire il servizio web:

```sh
cd /tmp/dp313-496-stage-20261026
PGDATABASE=dichiarazioni_pubbliche PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=poc \
  python3 tools/dp313_curia_persistent_pilot.py \
  --database-url dichiarazioni_pubbliche --apply-private-intake
```

Primo passaggio riuscito: `persistent=true`, `state=PRIVATE_HOLD`, Capture `capture:f96555a8077a707d9e04fc7cf0bba425b743240284c6eb5ac041df94991853fb`, 4/4 Passage verificati sui byte salvati, 4/4 Candidate `HELD` con foreign key confermate, tutti `NOT_EVALUATED`; `publication_authorized=false`, `model_called=false`.

**Rilevazione replay:** due esecuzioni esplorative precedenti alla deduplicazione del testo canonico hanno registrato due Capture diversi perché le risposte HTML differivano; entrambi hanno lo stesso hash di sentenza, stessa famiglia, stato `HELD`, zero corroborazioni indipendenti. Il successivo replay, dopo la correzione, ha restituito `reused_canonical_case=true` e il **primo** Capture con i medesimi quattro Candidate, senza ulteriori scritture di Capture/Candidate. I record storici restano immutati.

Sul Mac Studio: 42 test DP-313 mirati verdi, inclusi preflight dei diritti, controprova di redirect, negazione mutata, testo persistito manomesso e original-span/roundtrip; Ruff sui file nuovi verde. Il readback in modalità sola lettura da fonte HTTPS ha dato `writes=0` e lo stesso digest canonico.

## Limiti di accettazione

Questa è una **prova persistente privata reale**, non il completamento di tutti gli AC-313.1–6: mancano una testimonianza giudiziaria originale separata, la comparazione OCR contro scansione primaria, un vero stato d'impugnazione/supersessione con invalidazione `STALE` persistente, la verifica dei diritti/privacy per usi più ampi e una revalidazione pubblica autorizzata. Tali casi non sono simulati e la pipeline rimane `PRIVATE_HOLD`; in particolare il documento CURIA non certifica la verità di testimonianze o accuse di altri procedimenti.
