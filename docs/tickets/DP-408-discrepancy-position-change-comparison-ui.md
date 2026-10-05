# DP-408 — Trace / longitudinal relation UI

Status: BLOCKED

Milestone: M4 — public product/API
Depends on: DP-104, DP-105, DP-425

## Problem

Readers need to compare reviewed longitudinal relations without mistaking a candidate
relationship for an accusation. The comparison surface must show the statements, dates,
context, relation type, and evidence trail while preserving the product rule that
contradiction does not prove deception or malicious intent.

DP-104 and DP-105 are complete. The implementation must consume only their approved
relation/public-projection semantics and must fail closed when a relation is absent,
stale, private or unreviewed.

## Outcome

Implement the v3 chronology-first Trace view for two or more published statements
connected by an approved longitudinal relation. The page supports same-proposition,
clarification, update, position-change and contradiction contexts without generating a
person score, ranking or intent claim. Side-by-side comparison is secondary and user-invoked.

## Contract gate

- **DP-104** is the hard relation-policy gate: candidate and published relation states,
  review provenance, temporal compatibility, and reanalysis behavior must be settled;
- **DP-105** is the hard public resource/identifier/schema gate;
- public architecture v3 is the IA gate; **DP-425** is the final v4 visual-token/component gate;
- if the relation is not approved, current, and present in the public projection, the
  comparison must be unavailable rather than inferred from text similarity.

## Scope

### Public route and rendering

The canonical route is `/tracce/{relation_id}/` (or a deterministic slug form).
The page renders:

1. the relation title/type and a neutral explanation of what the relation means;
2. each participating published finding version, with statement time, source, speaker,
   and claim-first wording;
3. the relation's public context, limitations, and temporal scope;
4. a chronological evidence rail as the primary composition;
5. optional two-item comparison only after explicit user selection;
6. links to each Statement, Content, evidence source, correction, and approved
   right of reply;
6. reviewed relation/reanalysis metadata in a secondary disclosure when policy allows.

The comparison must not infer a relation from shared keywords, embeddings, topic
similarity, or a model answer. The only relation data rendered is the approved public
relation from DP-104/DP-105.

### Relation semantics

Allowed public relation types are those ratified by DP-104, such as same proposition,
clarification, update, position-change candidate after approval, and contradiction. The
UI must preserve the exact domain label and explanation supplied by the public contract.

- “Contradiction” means the reviewed statements do not align under the stated scope; it
  does not mean “lie”, “deception”, or malicious intent;
- a position change is a temporal change, not automatically an error;
- a relation candidate remains hidden until explicit review and publication;
- reanalysis, correction, or reply that changes the relation must update the link target
  without rewriting the old finding;
- a participant that is no longer public/projectable is omitted and the comparison fails
  closed rather than showing stale text.

### Responsive and comparison behavior

- desktop uses chronology first; optional selected-pair comparison remains secondary;
- mobile keeps participants in chronological order with no horizontal page scroll;
- each participant has a stable heading and link back to its Statement;
- source/evidence context remains close to the statement it supports;
- a visual diff is optional and must have a text/table equivalent;
- no node graph, political party color, leaderboard, or aggregate verdict display.

### Required states

| State | Required behavior |
|---|---|
| Two or more approved participants | Show relation type, context, statements, and evidence paths. |
| One participant is no longer public | Omit it and explain that the comparison cannot be completed; do not use stale data. |
| Relation is candidate or unreviewed | Return a deliberate unavailable/private state; do not show a guessed comparison. |
| No participants match filters | Show an empty state and a reset action; do not imply a relation was disproved. |
| Projection/schema is stale or invalid | Fail closed with bounded navigation and no cached unsafe record. |
| Correction/reply changes a participant | Link the version-aware history and preserve the original participant. |
| Comparison loading | Keep participant headings and state labels stable; never animate fake analysis. |

## Non-goals

- automatic relation inference, semantic similarity, or contradiction detection in the
  frontend;
- intent, deceit, lie, reliability, ideology, or political ranking inference;
- a graph database, node-graph visualization, or social network analysis;
- a comparison of private, held, or unreviewed records;
- an LLM explanation or live model call in the public request path;
- public submission, relation approval, or publication controls;
- a separate visual system for Trace (use the shared v4 design-system/Segno grammar);
- a new domain relation vocabulary outside DP-104/DP-105.

## Dependencies and gates

- **DP-104:** hard relation approval, temporal, reanalysis, and no-intent policy;
- **DP-105:** hard public relation resource and identifier contract;
- **Public architecture v3:** Trace is the canonical longitudinal page job;
- **DP-425:** final shared v4 token/component contract;
- **DP-402/DP-403:** stable read route/examples if relation resources are served over
  HTTP;
- **DP-407:** Content links for media participants;
- **ADR 0001/0002:** projection-only public reads and no LLM request path.

## Traceability & constraints

- **Traces to:** US-36-04, US-36-07, DEC-36-05, AC-36.4, AC-36.8, AC-36.10.
- **Constraints:** chronology first; reviewed relation data only; no intent/deception
  inference; no person score; side-by-side comparison is secondary and explicitly invoked.

## Acceptance criteria

- [ ] `AC-408.1`: Given an approved relation with two or more public finding versions,
  when a reader opens the Trace, then each statement, date, source, relation type,
  and evidence path is visible in a stable reading order.
- [ ] `AC-408.2`: Given the relation is a contradiction or position-change context, when
  the page explains it, then it does not infer intent, deceit, lie, reliability, or a
  political conclusion and preserves the exact DP-104 label.
- [ ] `AC-408.3`: Given a relation candidate, stale review, incompatible scope, or
  non-projectable participant, when the page is requested, then it fails closed and
  does not render a guessed or stale comparison.
- [ ] `AC-408.4`: Given a correction, reply, or reanalysis, when a participant changes,
  then the page links the new version and preserves the original finding/history without
  overwriting it.
- [ ] `AC-408.5`: Given desktop and mobile layouts, when the comparison is navigated by
  keyboard, at 200% zoom, and with a screen reader, then each participant, relation
  explanation, source link, and state is perceivable and operable with visible focus.
- [ ] `AC-408.6`: Given the visual implementation, when compared with architecture v3
  and DP-425, then chronology and the Segno evidence rail are primary; side-by-side
  comparison is secondary; no dashboard, graph, or color-coded person history appears.
- [ ] `AC-408.7`: Given providers are offline, when an approved comparison projection
  is served, then it remains readable and no LLM, provider, or operational DB request
  occurs.
- [ ] `AC-408.8`: Given the collision/dependency audit runs, then DP-408 owns the
  Trace route and DP-104/DP-105 remain the only relation/schema owners.

## Validation / proof

The implementation receipt must include:

```bash
python3 -m compileall -q poc tests
PYTHONPATH=poc python3 -m unittest discover -s tests -v
cd web && npm run check && npm run build
cd .. && git diff --check
```

The comparison fixture matrix must cover every approved relation type plus candidate,
stale-review, incompatible-scope, one-participant-omitted, correction, reply, empty
filter, missing projection, and invalid schema states. Exercise desktop and mobile
layouts, keyboard-only traversal, 200% zoom, reduced motion, grayscale, and a screen
reader. Inspect output for intent words, person scores, raw content, and private relation
candidates.

Runtime-affecting completion requires the comparison route and relation projection to be
served from the MiniPC deployment mirror through DP-401 with an DP-104-reviewed canary.
Record the relation ID, review-event provenance, projection fingerprint, representative
comparison output, and fail-closed stale/tampered result.

## Documentation, data, and migration impact

- consume the ratified DP-104/DP-105 relation/public-schema contract; any new relation
  vocabulary belongs to those domain owners rather than this UI ticket;
- update shared Statement/Trace components through DP-425;
- no migration is introduced by the UI ticket;
- do not edit `PLAN.md`.

## Completion receipt

- Implemented the canonical `/tracce/{relation-id}/` static route and moved the legacy
  `/compare/{id}/` surface onto the same `TraceRecord.astro` implementation with canonical
  metadata pointing to `/tracce/`; DP-422 still owns eventual redirect/removal of the
  legacy alias.
- `collectPublicTraces()` consumes only relations already present in the approved public
  projection, requires `status=APPROVED`, a review event, a projectable related claim and
  at least two public participants, and orders participants by public statement time with
  a deterministic finding-ID tie-breaker.
- The v4 chronology is neutral: event buttons never borrow finding-state colors. Only the
  selected event receives `paper-selected` + the cobalt Segno and `aria-current`; the
  event's own finding remains local inside its detail region.
- On narrow screens the selected detail is in the DOM immediately after its event button;
  the implementation does not use CSS reordering or a duplicated mobile detail tree.
- Relation copy avoids deception/intent conclusions, exposes exact domain type/version and
  review provenance only in secondary disclosure, and never reconstructs a relation from
  keyword similarity, embeddings or model output.
- Local deterministic canary: a temporary projection derived from the existing demo
  fixture with one structurally APPROVED `UPDATE` relation emitted both
  `/tracce/relation-demo-maintenance-mobility/` and its legacy Compare alias. Desktop and
  phone receipts are stored under `prototypes/v4-implementation/dp408/` and were manually
  inspected. This fixture proves rendering only and is **not** claimed as DP-104 runtime
  approval evidence.
- Local validation shared with DP-405: full Python suite **986/986 PASS**, restore
  verification PASS, `npm run check:design` PASS, Astro check 0 diagnostics, explicit
  projection build PASS, and `git diff --check` PASS.
- MiniPC fail-closed proof on 2026-10-05: production projection fingerprint
  `8c430c1bb36ad8135c313247d6cf276ffc6fea6c2f998e31f9d55aa02da85383` contains **0**
  public relations; PostgreSQL contains **0** `claim_relation` rows and no approved
  `claim_relation_candidate` row. The production build therefore emits no Trace route and
  the same-origin service returns HTTP 404 for an unprojected Trace ID, as required.
- **Remaining blocker:** the ticket's runtime DONE gate requires a real DP-104-reviewed
  relation canary with projectable participants. None exists in the runtime authority, so
  no synthetic database row or fabricated approval was created merely to make the ticket
  green. Once one reviewed relation is available, rebuild on MiniPC and attach its route,
  review-event provenance, projection fingerprint and representative HTML receipt.
