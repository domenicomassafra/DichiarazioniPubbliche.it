# DP-314 — verificatore fattuale generalista

Stato: implementato e provato su un caso reale; **nessun verdetto pubblico**.
Modulo: `poc/dichiarazioni_pubbliche/dp314_general_verifier_v1.py`.
Canary riproducibile: `tools/dp314_claim_verification_canary.py`.
Issue: [#58](https://github.com/domenicomassafra/DichiarazioniPubbliche.it/issues/58).

## Perché serve

Il preflight `preflight_verification_requirements` risponde a «questa proposizione
è controllabile con fonti revisionate, indipendenti, tempestive e con diritti?»
e non restituisce mai un verdetto. Il ticket chiede la classificazione
**verificabile / non verificabile / falso** «solo dopo requisiti per claim,
controprove e fonte; scarti in HOLD». Questo modulo è quel passo, e nient'altro.

## Regole di classificazione

| Esito | Condizione |
| --- | --- |
| `VERIFIABLE` | profilo applicabile, ruoli richiesti coperti da evidenze eleggibili su radici e famiglie indipendenti, contro-caso testato e **refutato** dalle stesse fonti |
| `NOT_VERIFIABLE` | nessun profilo per il `claim_kind`, oppure claim non fattuale |
| `FALSE` | stessa eleggibilità, **tutte** le osservazioni eleggibili refutano la proposizione, e il contro-caso è **supportato** da quelle fonti |
| `HELD` | tutto il resto: evidenza insufficiente, conflitto, stance ignota, contro-caso assente, non eleggibile o non osservato, input rifiutato |

Vincoli duri:

- `FALSE` non può derivare da una sola riga o da una riga non revisionata;
- gli id del contro-caso devono essere un sottoinsieme degli id eleggibili,
  quindi una riga esclusa (diritti revocati, fuori cutoff, non approvata) non
  può essere reintrodotta dal contro-caso;
- `verdict` resta `None`, `private_only=True`, `finding_authority=False`,
  `publication_authority=False`: è una classificazione di lavoro privata, non un
  Finding e non una pubblicazione;
- la stance resta un'etichetta dell'operatore: il modulo non scarica nulla e non
  trasforma un'etichetta in verità.

## Diritti delle fonti

L'approvazione dei diritti non è dichiarata a mano: `attest_licence_use` del
modulo DP-317 (`licence_excerpt_decision_v1`) concede `APPROVED` solo se il
documento dei termini è legato per SHA-256 e contiene almeno uno dei nomi che
identificano la licenza (`CC BY 4.0`, `Attribution 4.0 International`). Nel canary le stesse fonti
istituzionali UE sono usate come evidenza sotto quella licenza, con obbligo di
attribuzione.

## Cosa resta aperto

Nessuna proiezione pubblica, nessun verdetto pubblico, nessuna scrittura su
database: il consumer e i gate DP-305/DP-316 restano invariati. Il canary usa
una sola fonte primaria più il contro-caso: la doppia fonte indipendente resta
obbligatoria quando il profilo la richiede (p.es. `EVENT_SEQUENCE`,
`FACTUAL_DENIAL`), ed è il preflight a imporla.

## Riproduzione

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=poc python3 -m unittest tests.test_dp314_general_verifier -v
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=poc python3 tools/dp314_claim_verification_canary.py
```

Canary del 23/10/2026: dichiarazione del 04/03/2025 della presidente della
Commissione, `https://cyprus.representation.ec.europa.eu/news/press-statement-president-von-der-leyen-defence-package-2025-03-04_en`,
91729 byte, SHA-256 `6f985cbc9ebf19ab7cb1911d5bd561c839e6d6a4308c1207abc5882f10efdd19`,
passaggio «It will provide EUR 150 billion of loans to Member States for defence
investment» (80 caratteri, SHA-256 `00b847d2…`). Esiti: `VERIFIABLE`, `FALSE`,
`NOT_VERIFIABLE`, due `HELD`.
