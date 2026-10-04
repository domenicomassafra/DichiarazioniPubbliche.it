# DP-411 — Generate and compare five visual design systems

Status: DONE
Milestone: M4 research track  
Depends on: DP-413

## Outcome

Generate comparable high-fidelity mockups against the **same UX v2 page contracts** and
evaluate them before any frontend implementation. Earlier A/B/C images are exploratory
receipts only and do not satisfy this ticket because their information architectures
differ.

## Inputs

- `docs/33-ui-ux-deep-design-research-v3.md`
- `docs/ux/prototypes-v3/01-civic-editorial.prompt.md`
- `docs/ux/prototypes-v3/02-italian-modernist-ledger.prompt.md`
- `docs/ux/prototypes-v3/03-quiet-research-index.prompt.md`
- `docs/ux/prototypes-v3/04-visual-journalism.prompt.md`
- `docs/ux/prototypes-v3/05-temporal-evidence-tape.prompt.md`

## Acceptance criteria

- all five concepts use the same current page hierarchy from
  `docs/32-public-ux-architecture-v2.md`;
- round 1 generates Home desktop P1–P5 and Fact-check desktop P1–P5;
- reject weak directions before generating the rest of the product;
- round 2 compares ContentAudit, Explore, Record and Studio Workspace for the best 2–3;
- include mobile Home and Fact-check for finalists;
- each concept is scored with `docs/ux/evaluation-rubric.md`;
- apply the stricter anti-slop/designer-quality gates from research v3;
- automatic rejection conditions are applied before aesthetic preference;
- select two finalists rather than averaging all concepts;
- second round compares the same screens in both finalists: public home/search, public
  fact-check detail, Verify Studio live run, mobile fact-check detail.

## Non-goals

Choosing final logo/typeface, implementing frontend code, or turning generated placeholder
facts into real content.

## Prior exploration state

Directions A, B and C were generated before UX v2 was frozen. They exposed useful visual
preferences and anti-patterns, especially card/KPI/dashboard overload, but are explicitly
not accepted implementation targets. No partial generated-image work is considered active
WIP: this ticket restarts cleanly from UX v2 when visual exploration resumes.

## Preparation receipt — 2026-09-23

Deep design research and generation inputs are complete. Research covered materially
relevant local design/UX skills plus public fact-checking, public-service design,
editorial systems, visual/data journalism, research/evidence tools, media/transcript
workspaces and Italian modernist graphic-design references.

Five full-product prompt packs now cover Home, Explore, Fact-check, Record, ContentAudit,
Verify Studio Sessions, Verify Studio Workspace, mobile Home and mobile Fact-check.

## Visual comparison receipt — 2026-09-23

The five v3 directions were generated and compared in ChatGPT against the same product
surface family. The current user preference is **not** one literal winner: it is a
controlled hybrid of P2, P4 and P5.

The chosen contributions are:

- P2: modernist ledger structure, asymmetric grid, sharp geometry and typographic identity;
- P4: one evidence visual when it materially explains the finding;
- P5: Evidence Tape / temporal provenance for media, chronology and correction history.

The generated screenshots are visual receipts only and are not yet committed as canonical
assets. `DESIGN.md` now converts the preference into explicit reusable rules so the next
validation round can compare a coherent system rather than literally blending screenshots.

### Reassessment after P6 — 2026-09-23

The first P2/P4/P5 hybrid proved that the selected ingredients can coexist, but it also
reproduced the earlier failure mode: too many simultaneous visual systems in one viewport.
After rereading the full product/UX/research corpus, the candidate has been revised:

- **P3 Quiet Research Index is now the default Public interaction grammar**;
- **P2 remains the main identity/structural influence**;
- **P4 evidence visuals are conditional modules, not a page default**;
- **P5 temporal grammar is concentrated in ContentAudit, corrections and Studio**.

This change is not a return to P3's exact visual prototype. It is a hierarchy correction:
utility and reading clarity first; brand structure second; specialist evidence/time
interactions only where they earn their space.

### Final outcome — 2026-09-26

**Status: DONE.** The hybrid was validated, and validating it falsified part of
its own premise. The result is frozen as `DESIGN.md` v1 and implemented as
`web/src/styles/tokens.css` + `web/src/components/design/**`.

**The selected direction: "A civic ledger, not a dashboard."**

The reassessment above was right about the hierarchy and wrong about the
result. Keeping four visual systems alive at once (P2 identity + P3
interaction + P4 evidence + P5 temporal) produced the exact failure it was
trying to avoid: a page assembled from parts. The decision this ticket makes is
therefore not a blend but a **demotion**. Typography and whitespace become the
structure; three of the four systems become *registers inside one world*:

| Source | Final standing | What actually ships |
|---|---|---|
| P3 — Quiet Research Index | **retained as interaction grammar** | Search, rows, evidence adjacency, progressive disclosure, calm retrieval |
| P2 — Italian Modernist Ledger | **retained as structure** | Asymmetric grid, typographic identity, the 2px cobalt Segno, deliberate date rails |
| P4 — Visual Journalism | **demoted to a conditional module** | One evidence visual per record, and only where it answers a factual question |
| P5 — Temporal Evidence Tape | **demoted to a named mounting point** | The tape as a navigation rail, concentrated in ContentAudit, corrections, Studio |

#### What made it distinctive

The default for a fact-check product is a card grid with colored verdict pills
and a KPI strip; the default for a "modern" record product is a dark analytics
console. Both are excluded twice — by `PRODUCT.md`'s invariants and by the
craft floor. What survives that double exclusion, built honestly, is a system
where **the finding state is a word and the brand gesture is a rule, not a
color**. That pairing is not reachable by reaching for a component library, and
it is the reason this direction will not decay into one.

Three commitments carry it: typography is the layout engine; the Segno (one 2px
cobalt rail doing five jobs) is the only brand gesture; hairline is the entire
depth system — zero shadows, radii capped at 3px.

#### Evaluation against `docs/ux/evaluation-rubric.md`

The rubric's automatic rejection conditions are the binding test, because they
apply before aesthetic preference.

| Rejection condition | Status | Evidence |
|---|---|---|
| Courtroom / seal / parchment aesthetic | **pass** | No institutional scenery, seal, flag, or monument. `--paper-*` is a cool bone, not parchment. |
| Truth meters, grades, person-level scores | **pass** | No `score`/`rank`/`rating` prop exists in the type surface. `StatusText` has a runtime guard that **refuses to render** a count above 50. |
| Red/green as the only verdict signal | **pass** | The word carries the state; `unresolved` alone is hollow. Verified in-browser under `filter: grayscale(1)`. |
| Party colors as navigation | **pass** | One accent (cobalt) for selection/focus/links. The four states are claim↔evidence, never identity. |
| Chatbot as primary UI | **pass** | `TextField` is a plain `role="search"` form. No composer, no model selector, no streaming affordance. |
| Fake terminal/code aesthetic | **pass** | Mono is budgeted to time/identifiers/tabular only; not used as texture anywhere. |
| Animated fake progress | **pass** | The only two infinite animations are a skeleton sweep and a button spinner, both genuine states, both static under reduced motion. |
| Public raw transcript/evidence dumps | **pass** | Public consumes only the fail-closed `dichiarazioni-pubbliche-public-v2` projection. `src/lib/projection.ts` and `src/lib/types.ts` untouched. |
| Publishing conflated with analysis | **pass** | Four distinct registers; publication has **no color at all** — a rule and a date. |

Scored criteria (5 = best). The two-density criterion is the one this ticket
exists to prove:

| Criterion | Score | Note |
|---|---:|---|
| Instant comprehension | 5 | Search + dated claims, no dashboard |
| Not legalistic | 5 | No institutional scenery of any kind |
| Trust without stiffness | 4 | Editorial, but the mono/date rails stay restrained |
| Claim-first hierarchy | 5 | Serif at display scale; the claim is the largest ink on the page |
| Evidence legibility | 5 | Source stack sits inside the reading flow, not behind an action |
| Neutrality | 5 | Enforced in types and runtime guards, not just styling |
| Uncertainty | 5 | `unresolved` is a designed state with its own scale and mark |
| Memory | 4 | The tape is strong in ContentAudit, deliberately absent elsewhere |
| Scanability | 4 | Rows are calm; the 3-state color vocabulary is the limit |
| Mobile potential | 5 | Recomposed, verified at 320px with no overflow |
| **Two-density system** | **5** | Verified live: `--density-row-min` resolves to 3.75rem Public / 2.5rem Studio from one stylesheet |
| Distinctiveness | 4 | Recognizable without a logo, but it is deliberately quiet |
| Contemporary | 4 | Current without trend-chasing |
| Longevity | 5 | No framework visual to date-stamp it |

**Honest reading:** this is a strong 4s-and-5s sheet, not a sweep. The two
4s on *trust without stiffness* and *scanability* are the real cost of
editorial gravity, accepted deliberately: the alternative was a dashboard.

#### Validation receipt — 2026-09-26

Verified in Chromium against the built output, not asserted:

- 320px: no horizontal overflow (`scrollWidth === clientWidth === 320`).
- Density: `--density-row-min` = 3.75rem (Public) / 2.5rem (Studio).
- Selection: active Studio row computes to `rgb(211, 224, 247)` = `--paper-selected`.
- Focus: skip link off-screen; focused control on ink gets the inverted ring
  `2px rgb(168, 198, 255)`.
- Reduced motion: `--duration-*` collapse 0.12s/0.18s → 1ms, and content links
  keep their underline (the end state is preserved, not removed).
- Grayscale: state remains readable with `filter: grayscale(1)`.

**Two defects were found by looking and fixed**, which is the point of doing
the visual round at all: an unstyled `.skip-link` rendering as body copy on
every page (a Lane D2 class that `global.css` used to style), and a brand mark
whose two glyphs overflowed their 32px box at the inherited 24px.

#### Boundary

This ticket owns visual comparison and selection. It does not own the token or
component contract (DP-412), the information architecture
(`docs/32-public-ux-architecture-v2.md`), or product truth (`PRODUCT.md`).
