# DP-407 — Content page and source-locator UI

Status: READY

Milestone: M4 — public product/API
Depends on: DP-207, DP-105, DP-425

## Problem

Content is the public source-first way to inspect published statement moments inside a
video, podcast, interview, article, post or document. The current implementation still
contains legacy ContentAudit vocabulary and media-first assumptions. A production
implementation must support timed and written locators without exposing the operational
transcript/corpus or turning the public page into Verify Studio.

## Outcome

Implement the v3 Content template. A reader can inspect the original source, jump to a
published timed moment or written locator, read the concise finding for each published
statement, and open its canonical Statement page. The page remains useful with providers
offline and fails closed when a locator lacks public-safe provenance.

## Contract gate

- **DP-105** must define the public Content resource, media/statement-moment fields,
  bounded excerpt policy, identifiers, and correction/relation behavior;
- **DP-207** must close timestamped claim acceptance so `start_ms`/`end_ms` and source
  segment coverage are real accepted data rather than fixture assumptions;
- public architecture v3 is the IA gate; **DP-425** is the final v4 visual-token/component gate;
- the current `web/src/data/content-audit.ts` fixture is demo-only and must not become a
  public schema by reuse.

Until DP-105 and DP-207 close, fixture prototyping may exercise the interaction, but no
route may be called stable, no timestamp may be inferred, and no runtime proof may be
claimed.

## Scope

### Public route and data

The existing `/contenuti/<content_id>/` route is a demo/baseline alias. It must remain
clearly bounded and must not be removed or silently redirected until DP-105 and DP-401
ratify the canonical content identifier and redirect policy.

The canonical route is `/contenuti/{slug-or-id}/` with deterministic identifier mapping.
The page consumes only the public Content projection/API and may render:

- content title, source, publication date, duration, and canonical source link;
- a public-safe media player or source link for the bounded item;
- published claim moments with stable moment/claim/finding IDs;
- start/end timestamps for timed media or approved paragraph/section/quote locators for written content;
- the normalized claim, written finding state, one-sentence answer, and bounded rationale;
- reviewed source metadata and approved evidence links;
- a bounded source segment/identifier affordance;
- corrections, replies, and reviewed relations when present in the public contract.

The full transcript, canonical transcript text, raw/private media artifacts, evidence body/excerpt,
provider transcript, provider receipt, and internal extraction output are not public
fields. A transcript excerpt may appear only if DP-105 explicitly marks it public-safe
and policy-authorized; otherwise the UI shows the source/timestamp and not the words.

### Media and selection interaction

- use native or already-approved accessible media behavior; do not autoplay;
- media controls, claim markers, and jump actions are keyboard operable;
- selecting a moment updates the concise finding panel and the active marker without
  discarding the page context;
- the player, timeline, and claim list expose text labels and machine-readable times;
- mobile uses a single column, a small number of large touch targets, and an inline or
  full-height detail surface; it does not squeeze three desktop panes together;
- a selected moment is reflected in the URL or an equivalent shareable state when the
  approved route contract supports it;
- reduced-motion mode keeps the same state and selection semantics without animation.

The public Content page must remain distinct from Studio: it may show a bounded moment,
not an operator transcript, evidence-review queue, worker state, or publication action.

### Required states

| State | Required behavior |
|---|---|
| Normal | Show media/context, ordered claim moments, selected finding, and approved sources. |
| No public claim moments | Show the source context and a clear “no published checks for this item” state; do not expose held or private claims. |
| No public media | Keep the title, source link, timestamps/claim list, and a text-first fallback; do not show a broken player as a success. |
| Moment without public evidence | Show the finding state and “evidence not publicly available/approved” language; never invent a source. |
| Unresolved/needs-more-evidence | Render the explicit state and limitations as intentional, not as a broken empty page. |
| Stale/missing/invalid projection | Fail closed, omit unsafe moments, and show a bounded unavailable state with navigation. |
| Loading/selection | Preserve media and chronology context, announce the selected moment, and avoid fake “AI researching” activity. |
| Correction/reply | Link the version-aware history without overwriting the original moment or media context. |

## Non-goals

- Verify Studio pipeline, worker/provider monitoring, evidence approval, or publication
  actions;
- raw/full transcript browsing or an unbounded transcript search;
- automatic claim detection, ASR, evidence retrieval, or LLM calls in the public route;
- invented timestamps, guessed speakers, or media URLs;
- an always-on timeline, node graph, or transcript visualization that does not explain the
  user's question;
- a generic video CMS, media downloader, or third-party tracker;
- a second public ContentAudit product or domain contract outside DP-105/DP-207;
- public intake, auto-publication, or provider failover fabrication.

## Dependencies and gates

- **DP-207:** timestamped claim acceptance and source-segment coverage;
- **DP-105:** public Content/media/statement-moment contract and safety boundary;
- **Public architecture v3:** universal timed/written Content IA and distinct Studio boundary;
- **DP-425:** final v4 visual tokens and accessible component contracts;
- **DP-402/DP-403:** if resources are served over HTTP, stable API and OpenAPI examples;
- **DP-408:** reviewed longitudinal links when a Content item has them;
- **ADR 0001/0002:** projection-only public reads and no LLM request path.

## Traceability & constraints

- **Traces to:** US-36-03, US-36-07, DEC-36-03, AC-36.3, AC-36.8, AC-36.10.
- **Constraints:** source-first; timed media and written locators are both first-class;
  never invent timestamps; never expose private/raw transcript/provider output; public
  projection only.

## Acceptance criteria

- [ ] `AC-407.1`: Given an approved Content item with several public statement moments, when
  a reader opens the route on desktop or mobile, then media/context, ordered moments,
  selected finding, and approved sources are available without a raw transcript dump.
- [ ] `AC-407.2`: Given a moment with a valid source segment and timestamp, when the
  reader selects it, then the player/marker, finding panel, and URL state identify the
  same public moment and the source position is not inferred from display order.
- [ ] `AC-407.3`: Given no public media, no public claim moments, or no approved public
  evidence, when the page renders, then it has a deliberate text-first fallback and does
  not fabricate a player, claim, source, or stronger assessment.
- [ ] `AC-407.4`: Given an unresolved, needs-more-evidence, under-review, or blocked
  state, when rendered, then the wording is explicit and the page remains navigable;
  analysis completion is never presented as publication.
- [ ] `AC-407.5`: Given a transcript segment without approved public-safe content, when
  the page renders, then it exposes only the permitted source/timestamp metadata and
  never raw/canonical transcript text or provider output.
- [ ] `AC-407.6`: Given a correction or approved right of reply, when selected, then the
  page preserves the original Content moment and links the version-aware history.
- [ ] `AC-407.7`: Given keyboard-only input, 200% zoom, reduced motion, and a screen
  reader, when the reader traverses media controls, moment markers, details, and source
  links, then all actions and state are perceivable and operable with visible focus.
- [ ] `AC-407.8`: Given providers are offline, when an approved projection is served,
  the page remains readable and no LLM, provider, or operational DB request occurs.
- [ ] `AC-407.9`: Given the collision/dependency audit runs, then DP-407 owns the public
  Content route, DP-408 owns Trace, and Studio remains a separate boundary.

## Validation / proof

The implementation receipt must include:

```bash
python3 -m compileall -q poc tests
PYTHONPATH=poc python3 -m unittest discover -s tests -v
cd web && npm run check && npm run build
cd .. && git diff --check
```

The Content fixture matrix must include at least twelve moments/locators, one item per
finding state, no-media, no-moment, no-public-evidence, stale projection, correction,
reply, keyboard selection, and mobile fallback cases. Verify timestamps against the
DP-207 accepted source-segment fixture rather than the UI's formatted labels.

Exercise the real static route on phone and desktop widths, keyboard-only navigation,
200% zoom, reduced motion, media fallback, and a screen-reader pass. Inspect rendered
HTML and client assets for raw transcript/evidence leakage and for any request to a
provider, PostgreSQL, or LLM.

Runtime-affecting completion requires the route and media/claim projection to be served
from the MiniPC deployment mirror through DP-401, with the accepted DP-207 timestamp
fixture and an approved DP-105 projection. Record the route, projection fingerprint,
representative media-less and populated states, and the no-private-content inspection.

## Documentation, data, and migration impact

- document the public Content resource and bounded excerpt policy only after DP-105
  ratifies it;
- update the shared locator/evidence component contract through DP-425;
- DP-207 owns timestamp acceptance and any backend fixture/schema changes;
- no migration is introduced by the UI ticket;
- do not edit `PLAN.md`.

## Completion receipt

Pending DP-105, DP-207, DP-425, and implementation. A demo Content interaction is not a
production acceptance receipt.
