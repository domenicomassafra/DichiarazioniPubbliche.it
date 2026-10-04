# Data Model & Taxonomy

## Core entities

### Person

id, canonical name, aliases, public roles, role intervals, organizations, official/public accounts, source references.

### Topic

id, name, aliases, hierarchy, related topics.

### Source

id, canonical URL, source type, publisher, author, publication date, acquisition date, hash, archive URL, source class, metadata.

### ContentItem

article, video, podcast, social post, official act, interview, parliamentary session.

### Appearance

Presenza di una persona in un ContentItem.

### Statement

verbatim, normalized, timestamp/range, attribution confidence, language.

### AtomicClaim

normalized claim, subject, predicate, object/value, temporal scope, geographic scope, qualifiers, check-worthiness.

### Evidence

source id, relevant passage/data, support/contradict/context, evidence date, extraction method, confidence, source independence group.

### Finding

id, claim id, type, status, verdict, rationale, evidence set, counter-evidence set, limitations, confidence, model runs, policy version, timestamps, version, correction/reply status.

### Reply / CorrectionRequest

requester, target finding, claim, evidence submitted, status, timestamps, re-analysis result.

## Claim relationships

supports, contradicts, updates, clarifies, retracts, same_claim, paraphrase_of, prediction_of, promise_of, fulfills, violates, refers_to.

## Finding taxonomy

### Support/veracity

SUPPORTED, FACTUALLY_FALSE, PARTIALLY_SUPPORTED, IMPRECISE, UNVERIFIABLE, INSUFFICIENT_EVIDENCE.

### Context

MISSING_MATERIAL_CONTEXT, MISLEADING_CONTEXT, CHERRY_PICKED_DATA, OUTDATED_DATA.

### Numbers/data

NUMERICAL_ERROR, UNIT_ERROR, DENOMINATOR_ERROR, BASELINE_ERROR, DATE_RANGE_ERROR.

### Attribution

MISQUOTE, MISATTRIBUTION, WRONG_SPEAKER, SOURCE_MISMATCH.

### Temporal/person consistency

POSITION_CHANGE, CONTRADICTION_OVER_TIME, RETROSPECTIVE_CONTRADICTION, RETRACTION, CORRECTION, CLARIFICATION.

### Promise/prediction

PROMISE_PENDING, PROMISE_FULFILLED, PROMISE_NOT_FULFILLED, PREDICTION_PENDING, PREDICTION_CONFIRMED, PREDICTION_FAILED.

### Official records

CONTRADICTS_OFFICIAL_RECORD, SUPPORTED_BY_OFFICIAL_RECORD.

### Intentionality

DELIBERATE_FALSEHOOD — threshold separato e molto più alto.

## Status separato da verdict

DRAFT_INTERNAL, EVIDENCE_COLLECTION, CHALLENGE_REVIEW, READY_FOR_POLICY, PUBLISHED, UNRESOLVED, DISPUTED, UNDER_REANALYSIS, CORRECTED, RETRACTED.

## Versioning

Ogni modifica di un finding pubblicato crea una nuova versione. Non sovrascrivere rationale, evidence set, verdict, date e policy version.

## Provenance

Per ogni run: model/provider, model version, prompt/template version, tool calls, query strings, fetched URLs, timestamps, code/policy version.

