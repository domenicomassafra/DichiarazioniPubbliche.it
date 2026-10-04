# Licensing & Commercialization

> **Historical research note.** The repository-code license question in this document
> was resolved on 2026-09-22 by `docs/adr/0005-apache-2-core-license.md`: repository code
> is Apache-2.0 unless a file/directory states otherwise. Data/content rights remain a
> separate pre-launch workstream.

## Requisito

Il core deve restare utilizzabile in scenari commerciali futuri: SaaS, abbonamento, API premium, BYOK, quota inclusa sulle nostre API key, enterprise e agent integration.

## Regola critica

Il fatto che il codice sia visibile non significa che possiamo riscriverlo a mano uguale.

Il copyright protegge l'espressione del codice. Una riscrittura molto aderente può comunque essere derivativa.

## Classificazione donor

### Permissive

MIT, Apache-2.0, BSD: in genere consentono fork, incorporazione, modifica e uso commerciale rispettando notice e condizioni.

### Copyleft

GPL e AGPL: da decidere caso per caso; non incorporare nel core commercialmente flessibile senza valutarne le conseguenze.

### Restrictive/custom

Esempio: InTruth vieta commercial use senza permesso scritto.

Policy: niente copia, niente port line-by-line, niente traduzione del codice in altro linguaggio, niente reimplementazione guidata riga-per-riga.

## Clean-room pattern

Se una feature di repo restrittiva è interessante:

1. Researcher A osserva comportamento pubblico e documentazione e scrive una specifica funzionale.
2. La specifica descrive input/output, UX, invarianti e casi limite, non il codice.
3. Implementer B non usa il sorgente restrittivo come riferimento operativo e implementa da zero.
4. Test black-box validano il comportamento desiderato.
5. Provenance documenta implementazione indipendente.

Policy prudenziale da sottoporre a consulenza legale prima di feature sensibili.

## Donor matrix

| Progetto | Licenza | Uso ipotizzato |
|---|---|---|
| Loki/OpenFactVerification | MIT | possibile riuso codice |
| Claim Polygraph NG | MIT | possibile riuso codice/pattern |
| Meedan Pender | MIT | possibile riuso codice |
| Meedan Alegre | MIT | possibile riuso codice |
| Community Notes | Apache-2.0 | riuso selettivo/idee |
| OpenParliamentTV Architecture | CC0 | documentazione/spec |
| OpenParliamentTV Tools/Platform | GPL-3.0 | reference o integrazione separata |
| OpenParliamentTV Additional Data Service | AGPL-3.0 | reference/servizio separato |
| Openparlamento | GPLv3 | reference/dati, non core |
| Ledsav/fact-checker | MIT | donor tattico |
| InTruth | custom non-commercial | reference comportamentale/clean-room senza permesso |
| CIMPLE | da verificare per repo | reference finché non verificato |

## Licenza del nostro progetto

Non ancora decisa.

Opzioni:

- MIT/Apache per massima adozione;
- open-core;
- dual-license;
- source-available con commercial terms.

Nota: una licenza che vieta uso commerciale normalmente non è open source in senso OSI.

## Business model futuri

- free read;
- request queue gratuita limitata;
- BYOK;
- managed quota con crediti e rate limits;
- API read gratuita e bulk/realtime/premium a pagamento;
- MCP, skill, OpenAPI tool, SDK o plugin.
