# Garlasco real-data intake — 2026-09-28 expansion

Status: runtime-proven private corpus expansion; no automatic publication.

## Scope

This pass continues the 2026-09-27 Garlasco intake for public statements by:

- Selvaggia Lucarelli;
- Roberta Bruzzone.

The purpose is claim-level archival and verification, not person-level scoring. The pass
adds attributable statements from direct interviews, publisher podcast pages, and
Lucarelli's authored articles. Criminal-case opinions, prosecution theories, and
evidentiary judgments remain explicitly distinguished from established facts.

The pass is not represented as an exhaustive record of everything either person has ever
said. It is a reproducible expansion of the currently discovered Garlasco source set.

## Runtime readback

The authoritative MiniPC PostgreSQL database `dichiarazioni_pubbliche` was updated additively on
2026-09-28. After the intake:

- Garlasco `atomic_claim`: **30**, up from 12;
- Roberta Bruzzone: **14** claims, **12** check-worthy;
- Selvaggia Lucarelli: **16** claims, **10** check-worthy;
- `claim_text_provenance`: **28** Garlasco rows, all **APPROVED**;
- new batch: **18** claims across 10 Content records;
- new batch: **13** check-worthy claims and **5** non-factual/value-judgment claims;
- existing findings remain **9** total: **2 PUBLISH**, **7 NEEDS_MORE_EVIDENCE**;
- the 2026-09-28 batch created **no new finding and no new public dossier**.

Approval of `claim_text_provenance` means only that the quoted proposition was checked as
attributable to the named speaker in the recorded source. It does not approve the truth of
the proposition.

## Intake implementation

This pass also adds a reusable curated written-source intake path:

- `poc/dichiarazioni_pubbliche/curated_written_intake.py` validates a bounded manifest,
  normalizes content/claim records, hashes exact quote text, and inserts sources, Content,
  claims, and text-provenance records idempotently;
- `tools/ingest_curated_written_claims.py` is the operator CLI;
- quote bodies are used transiently to derive SHA-256 provenance and are not retained in
  the prepared model or receipt;
- attribution approval is an explicit append-only review event;
- ingestion never creates evidence approval, a Verification Run, a Finding, or a public
  dossier.

The runtime manifest containing exact source quotes was intentionally kept outside Git at
`/tmp/garlasco-curated-2026-09-28.json` on the MiniPC. The committed repository contains
only normalized claim descriptions and this sanitized operational receipt.

## Sources added in this pass

### Roberta Bruzzone

1. Radio Number One / Apple Podcasts, 27 March 2025 interview:
   `https://podcasts.apple.com/it/podcast/il-delitto-di-garlasco-la-criminologa-bruzzone-non/id1499630188?i=1000701227066`
2. Quotidiano Nazionale, 18 May 2025 direct interview:
   `https://www.quotidiano.net/cronaca/garlasco-poggi-stasi-sempio-wszqlbwo`
3. Open, 7 October 2025 direct interview:
   `https://www.open.online/2025/10/07/garlasco-parla-roberta-bruzzone-sempio-rinvio-giudizio-accuse-venditti/`
4. Corriere della Sera, 10 July 2026 direct interview:
   `https://www.corriere.it/cronache/26_luglio_10/roberta-bruzzone-intervista-78617977-dd29-442e-b678-0844cc0f2xlk.shtml`

### Selvaggia Lucarelli

1. Il Fatto Quotidiano, 21 May 2025, authored article:
   `https://www.ilfattoquotidiano.it/in-edicola/articoli/2025/05/21/bestiario-di-un-delitto-insulti-ai-poggi-il-complotto-di-rizzoli-e-le-emoticon/7996080/`
2. Il Fatto Quotidiano, 12 July 2025, authored article:
   `https://www.ilfattoquotidiano.it/in-edicola/articoli/2025/07/12/linchiesta-pro-stasi-inguaia-stasi-e-lavvocato-de-rensis-fa-le-piroette/8059153/`
3. Il Fatto Quotidiano, 21 October 2025, authored article:
   `https://www.ilfattoquotidiano.it/in-edicola/articoli/2025/10/21/omicidio-garlasco-in-tv-il-gran-circo-tra-magistrati-avvocati-e-giornalisti/8167451/`
4. Il Fatto Quotidiano, 1 February 2026, authored article:
   `https://www.ilfattoquotidiano.it/in-edicola/articoli/2026/02/01/garlasco-la-procura-ora-si-affida-al-perito-delle-iene-la-giustizia-insegue-linchiesta-tv/8275837/`
5. Il Fatto Quotidiano, 3 May 2026, authored article:
   `https://www.ilfattoquotidiano.it/in-edicola/articoli/2026/05/03/il-circo-garlasco-presenta-la-donna-che-mori-2-volte/8373214/`
6. Il Fatto Quotidiano, 10 May 2026, authored article:
   `https://www.ilfattoquotidiano.it/in-edicola/articoli/2026/05/10/sempio-si-auto-confessa-il-giornalismo-parla-da-solo/8380880/`

## New claim set

### Roberta Bruzzone — eight new claims

| Claim | Type | Check-worthy | Current hold |
| --- | --- | ---: | --- |
| Evidence at the center of the reopening was already available in 2016 | `HISTORICAL_CLAIM` | yes | primary-record evidence required |
| The Y-chromosome material attributed to the Sempio line was described as incomplete | `HISTORICAL_CLAIM` | yes | forensic-record evidence required |
| Francesco De Stefano was attributed the view that the Y comparison was not particularly reliable | `HISTORICAL_ATTRIBUTION` | yes | primary forensic source required |
| DNA traces now being re-examined had long been described as unreliable for judicial use | `HISTORICAL_CLAIM` | yes | primary forensic record required |
| No objective element, in Bruzzone's view, placed Sempio at the scene as an alternative to Stasi | `VALUE_JUDGMENT` | no | non-factual evidentiary judgment |
| Prediction that prosecutors would request that Sempio be sent to trial | `SYSTEMIC_INFERENCE` | yes | later official outcome required |
| Marco Poggi and the Cappa sisters were described as excluded from the investigation | `HISTORICAL_CLAIM` | yes | official procedural record required |
| Prediction that the reopened investigation would end in a `nulla di fatto` | `SYSTEMIC_INFERENCE` | yes | outcome not final at statement date |

### Selvaggia Lucarelli — ten new claims

| Claim | Type | Check-worthy | Current hold |
| --- | --- | ---: | --- |
| Chiara Poggi's parents were described as victims who had become targets of the public narrative | `VALUE_JUDGMENT` | no | non-factual media commentary |
| The incidente probatorio was described as indicating that Stasi was the person who had eaten with Chiara in the hours before the homicide | `HISTORICAL_CLAIM` | yes | incidente-probatorio record required |
| The Cappa sisters were described as never formally involved in the murder investigation | `HISTORICAL_CLAIM` | yes | official procedural record required |
| Lucarelli judged the evidence insufficient for conviction beyond reasonable doubt | `VALUE_JUDGMENT` | no | non-factual legal/evidentiary judgment |
| Lucarelli judged Stasi the most probable culprit | `VALUE_JUDGMENT` | no | criminal-case opinion, not a Finding |
| Lucarelli judged that there was nothing concrete against Sempio as of 1 February 2026 | `VALUE_JUDGMENT` | no | non-factual evidentiary judgment |
| Lucarelli reported a prosecution theory identifying Sempio as the sole perpetrator | `LEGAL_QUOTE` | yes | criminal allegation; official record required |
| Lucarelli reported a prosecution theory describing an attempted sexual approach as motive | `HISTORICAL_ATTRIBUTION` | yes | criminal allegation; official record required |
| Lucarelli reported that the prosecution theory included the aggravating circumstance of cruelty | `LEGAL_QUOTE` | yes | criminal allegation; official record required |
| Lucarelli stated that media excerpts of intercepted audio had joined separated fragments despite unintelligible material in between | `HISTORICAL_CLAIM` | yes | source-audio comparison required |

## Verification state

The new factual/check-worthy claims are intentionally not promoted to findings merely
because their source attribution is now approved. Their next gate is authoritative or
otherwise policy-appropriate evidence with explicit observations. In particular:

- forensic statements require the underlying expert report, order, hearing record, or a
  source that is authoritative for the proposition being tested;
- procedural-status statements require official judicial/prosecution records where
  available;
- the intercepted-audio claim requires the source audio or an equivalently strong record,
  not another headline paraphrase;
- predictions are stored as dated predictions. A later outcome may be used only to assess
  that later outcome, not retroactively as evidence that an earlier state-of-the-world
  proposition was knowable.

No empty-evidence Verification Run was manufactured simply to create a green receipt.
The new batch therefore remains private/fail-closed pending evidence work.

## Deferred/discovered source backlog

The discovery pass also found material that was deliberately not ingested as an atomic
claim in this batch:

- television/video appearances where a stable timestamped transcript was not available;
- a January 2026 Lucarelli/Bruzzone podcast page whose crawl exposed episode metadata but
  not enough attributable transcript text;
- secondary articles that merely repeat statements already represented by a stronger
  primary/direct source;
- sensitive allegations involving third parties where the available material was only a
  media retelling and an appropriate primary or official record had not yet been attached;
- broad rhetorical or evidentiary commentary that added no independently useful atomic
  proposition beyond the non-factual judgments already represented.

These are discovery candidates, not evidence that the coverage is complete.

## Validation receipt

Local focused validation before runtime ingest:

```text
python3 -m unittest tests.test_curated_written_intake tests.test_text_provenance -v
8 tests: PASS

python3 -m py_compile poc/dichiarazioni_pubbliche/curated_written_intake.py \
  tools/ingest_curated_written_claims.py
PASS

git diff --check
PASS
```

MiniPC production readback after ingestion:

```text
Roberta Bruzzone      14 claims   12 check-worthy
Selvaggia Lucarelli   16 claims   10 check-worthy

Garlasco claims                 30
Garlasco text provenance        28
Approved text provenance        28
Existing PUBLISH findings        2
Existing NEEDS_MORE_EVIDENCE     7
New-batch findings               0
```

The same manifest was then replayed through the MiniPC CLI. Readback reported all
**18/18** claim rows as `existing`, all **18/18** new provenance rows as `APPROVED`,
the Garlasco claim count remained **30**, and the public `PUBLISH` finding count remained
**2**. The replay therefore produced no duplicate claim and no publication side effect.

The two legacy Garlasco claims without `claim_text_provenance` are from the prior intake
path and are not silently converted by this batch.
