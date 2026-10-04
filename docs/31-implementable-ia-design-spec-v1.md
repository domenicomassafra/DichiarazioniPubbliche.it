# Dichiarazioni Pubbliche — Implementable IA and Design Spec v1

Date: 2026-09-23
Status: superseded by `docs/32-public-ux-architecture-v2.md`; retained as design history

> This v1 translated the first competitive-research wave into implementation guidance.
> A subsequent simplification pass found that it still exposed too many first-class
> routes/components and retained too much dashboard/card grammar. The current UX
> architecture is `docs/32-public-ux-architecture-v2.md`.

## Purpose

Turn the competitive UX research into an implementable information architecture for
Dichiarazioni Pubbliche Public and the private Verify Studio without changing the product's political,
editorial, provenance, or publication rules.

The design must make evidence and chronology easier to inspect while preserving these
non-negotiable boundaries:

- no person-level truth/reliability score;
- no political ranking or recommendation;
- no automatic publication;
- no implication that contradiction proves intent;
- no public raw transcript or raw evidence body;
- correction/right-of-reply history remains explicit and append-only;
- machine states such as pending, blocked, insufficient evidence, and unresolved are
  represented as states, not disguised as confidence scores.

## One brand, two products

### Dichiarazioni Pubbliche Public

Purpose: answer "what was said, when, what evidence was reviewed, and what changed?"

Density: low to medium.
Primary device: phone first, then desktop.
Interaction style: reading, search, filtering, chronology, evidence inspection.

Primary navigation:

```text
Fact-check   Esplora   Persone   Temi   Metodo   Cerca
```

The home surface must not become a news portal. It should open with a clear product
explanation, recent verified records, a simple search path, and direct access to method
and corrections.

### Verify Studio

Purpose: analyze a new source and move it through acquisition, transcript, claim,
evidence, verification, review, and publication gating.

Density: medium to high.
Primary device: desktop/wide screen.
Interaction style: triage, comparison, provenance inspection, explicit operator actions.

Primary navigation:

```text
Nuova verifica   In corso   Coda   Record   Revisioni
```

Analysis completion and publication must remain visually separate. A successful model
response must never render as "published" or as an implicit approval.

## Public route map

```text
/
/fact-check
/fact-check/:finding_id
/esplora
/persone
/persone/:person_id
/temi
/temi/:topic_id
/contenuti/:content_id
/confronti/:relation_or_group_id
/cerca
/metodo
/correzioni
```

Do not add party leaderboard, politician scorecard, reliability dashboard, "best/worst",
or election-choice routes.

## Mobile-first page contracts

### Home

Above the fold, in order:

1. one-sentence product explanation;
2. search entry;
3. 2–4 recent fact-check cards;
4. link to method/corrections.

No generic AI hero, animated orb, chatbot-first composition, oversized gradient headline,
or decorative dashboard KPI wall.

### Fact-check detail

Mobile order is fixed:

1. exact/original wording or bounded source quotation context;
2. speaker + role + source + statement date;
3. finding state label;
4. short rationale;
5. evidence list;
6. provenance/verification method;
7. chronology;
8. correction/right-of-reply history;
9. related records.

The normalized claim must be visually distinguishable from the source wording.

Desktop may place evidence/provenance in a right rail, but the DOM/content order should
remain compatible with the mobile sequence and accessible reading order.

### Person record

Show:

- identity and role context;
- chronological statement/finding stream;
- filters by topic/date/claim type;
- position-change or discrepancy links only when the underlying relation is reviewed.

Do not show aggregate truth percentages, grades, reliability averages, streaks, ranks,
party comparisons, or "most false" summaries.

### Topic record

Show a time-ordered evidence/claim record for the topic. Grouping may be by date,
sub-topic, or source type, but never by a person score.

### Content audit

Mobile:

- media/source header;
- chapter/timestamp navigation;
- claim moments;
- finding/evidence cards below each moment.

Desktop:

- media and transcript/timeline can be side by side;
- selecting a claim highlights its exact source segment and linked evidence;
- transcript text remains bounded to the public-safe policy, never a raw operational dump.

### Search

Search results should be compact:

```text
claim / original wording
speaker + role
source + date
finding state
one-line rationale
evidence affordance
```

Do not expose hidden operational states or raw provider/model output.

## Public component grammar

### Claim card

Required fields:

- claim/finding identifier;
- normalized claim;
- speaker name;
- source date;
- source title/domain;
- current finding state;
- explicit evidence affordance.

Optional fields:

- source timestamp;
- correction badge;
- right-of-reply badge;
- topic labels.

The card must remain usable in grayscale. Status may use color, but text/iconography must
carry the same meaning.

### Finding state labels

Use human-readable labels mapped from domain states. They are record states, not ratings.

Examples:

- Supported by reviewed evidence
- Factually contradicted by reviewed evidence
- Uses outdated data
- More evidence needed
- Unresolved
- Under review

Avoid theatrical meters, grades, emoji verdicts, flames, traffic-light-only meaning, or
language that implies a person's overall trustworthiness.

### Evidence item

Display:

- publisher/source;
- title or concise descriptor;
- publication date;
- reference period when material;
- relation to the finding;
- link;
- provenance/method affordance.

Do not show raw cached evidence bodies or private extraction payloads.

### Provenance drawer

Progressively disclose:

- source content ID;
- exact source segment/timestamp identifiers;
- transcript provenance identifiers;
- evidence IDs/content hashes;
- observation IDs;
- verification rule/version;
- review-event IDs.

These identifiers are trust/audit affordances and should not dominate the primary reading
surface.

### Correction and right-of-reply history

Corrections and replies belong in a visible chronology, not a hidden footer.

Each item needs:

- type;
- created/published date;
- relation to the finding version;
- review/publication state where public-safe;
- bounded public text;
- evidence links when approved.

Never silently replace the old record.

## Verify Studio workspace

Wide-screen structure:

```text
left: source/media/transcript
center: detected atomic claims + pipeline state
right: evidence + observations + review actions
```

The central pipeline state is explicit:

```text
Acquire
-> Transcript / extract
-> Detect claims
-> Select check-worthy claims
-> Search/fetch evidence
-> Extract observations
-> Verify
-> Review
-> Ready for publication / Hold
```

Blocked/provider-unavailable states must occupy the same status grammar as successful
states. They must not be hidden behind retries or replaced by a lower-quality verdict.

## Density rules: avoid "AI slop"

The public product should prefer real records over decorative explanation.

- one primary action per card;
- no repeated "AI-powered", "intelligent", "smart", or model branding in user-facing
  record pages;
- no synthetic metrics without a direct operational meaning;
- no fake live activity animation;
- no wall of pills/badges when plain metadata is clearer;
- no generic sparkle/bot/brain iconography as evidence of quality;
- no verbose autogenerated summaries where the original claim + concise rationale +
  evidence list communicates the same information;
- use whitespace to separate evidence layers rather than adding more chrome.

Studio may be dense, but every visible panel must correspond to a persisted workflow
object or operator decision.

## Responsive behavior

Target breakpoints are implementation details; behavior is not.

Phone:

- single content column;
- sticky page title/status only if it does not obscure content;
- evidence opens inline or in a full-height sheet;
- filters collapse behind one control with active-filter count;
- tables become labeled key/value stacks;
- chronology remains vertically ordered.

Tablet:

- one main column plus optional contextual drawer;
- cards can become two-column only when reading order remains clear.

Desktop:

- fact-check detail may use main content + evidence rail;
- person/topic archives may use persistent filters;
- Studio may use 3 panes with independently scrollable transcript/claims/evidence.

## Accessibility and trust requirements

- minimum WCAG AA contrast for text and interactive states;
- no state communicated by color alone;
- visible keyboard focus;
- headings reflect the record hierarchy;
- source/evidence links have descriptive labels;
- timestamps and dates are machine-readable where possible;
- motion respects reduced-motion settings;
- any animation reflects persisted/observed state only.

## Data-contract boundaries

Public UI consumes only the fail-closed public projection/API. It must not read operational
tables directly.

The UI may render a finding only when the backend projection already established:

- approved speaker provenance;
- source/transcript provenance;
- approved evidence and observations;
- verification run provenance;
- explicit finding publication review;
- correction/reply gates where applicable.

Frontend code must not recreate or weaken publication policy.

## Implementation sequence

1. Build shared typography/spacing/status primitives with no party/person semantic color.
2. Implement mobile fact-check detail using approved projection fixtures.
3. Implement compact search/result cards.
4. Implement person/topic chronology without aggregate scoring.
5. Implement ContentAudit timeline.
6. Implement desktop evidence rail/provenance drawer.
7. Implement private Studio shell and persisted pipeline states.
8. Run accessibility, mobile, and neutrality acceptance before visual polish.

DP-411 visual concept generation may explore visual language, but it must not override
this information hierarchy or any PRODUCT.md invariant. DP-412 may later consolidate
tokens/components after the concept comparison.

## Acceptance checklist

- a first-time mobile user can identify the claim, speaker, date, finding state, and
  evidence path without opening a menu;
- evidence is one deliberate interaction away from the claim;
- original wording and normalized claim are distinct;
- correction/reply history is visible and version-aware;
- no person/party ranking or aggregate truth score appears anywhere;
- pending/unresolved/blocked states render intentionally;
- public pages remain useful with all model providers offline;
- public UI requires no raw transcript/evidence body;
- Studio clearly separates analysis, review, and publication;
- UI contains no fake live/research activity;
- page hierarchy still works at narrow phone width before desktop enhancements are added.
