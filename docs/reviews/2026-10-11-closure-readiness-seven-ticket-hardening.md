# Ticket closeout audit and seven-ticket hardening — 11 October 2026

## Scope and closure policy

Baseline Mac Studio `main`: `59ee0ee`; canonical ticket inventory:
**162 total, 90 DONE, 52 IN PROGRESS, 6 BLOCKED, 14 FUTURE**.
The owner asked to close as many tickets as possible. The sprint audited
the nearest-to-complete work, distinguished technically executable checks
from real external acceptance and implemented missing fail-closed behavior.

**New ticket statuses promoted to DONE: zero.** Seven real ticket behaviors
advanced, but their remaining original acceptance criteria are not satisfied
by fixture data, browser automation or a caller-provided signed-looking
identifier alone. No checklist was checked by pretending an independent
qualified review, real VoiceOver session, real source rights, live published
resource or MiniPC cutover occurred. The original totals remain unchanged.

| Ticket | Change and regression | Outstanding closure gate |
| --- | --- | --- |
| DP-229 | Challenger material fingerprint v3 includes evidence retrieval method, claim statement cutoff, publication date, validity interval and reference period; isolated PostgreSQL temporal mutation invalidates material/review identity. | AC-229.8: durable independently attested challenger packet/incorporation/review and qualified policy-waiver authority; forged in-memory READY/waivers stay rejected. |
| DP-405 | Opt-in separately validated zero-record PublicPerson UI with semantic empty state, no fabricated filtered count, source-dated public roles and strict HTTPS link guard. Isolated Astro positive + eight unsafe negative fixtures. | AC-405.3 needs a real approved first-class DP-438 Person API/route and MiniPC fingerprint/readback; AC-405.6 needs actual human screen-reader and manual keyboard/contrast acceptance. |
| DP-407 | Published Content moment labels now distinguish DISPUTED/CORRECTED/RETRACTED. Withdrawn verdict/rationale/evidence are not shown as a current conclusion; private/unfinished statuses are withheld. Browser/AX/keyboard synthetic-public-schema regression. | AC-407.4: reviewed source/owner rule for private unresolved/under-review/blocked state (not in public schema); AC-407.7: manual screen-reader/zoom/keyboard acceptance. |
| DP-409 | Explore static-index UI announces result count atomically and distinguishes an overlong query from no results; dialog filter trigger retains accessible target and open state, with real local browser fixture. | AC-409.8: human screen-reader/manual AT judgement, plus public-v3 Statement/Person/topic consumer gates. |
| DP-412 | Shared Button busy activation remains focusable but cannot submit, TextField retains both hint/error descriptions, EmptyState retains base style semantics. Added eight Node SSR/contrast/reduced-motion contract groups. | AC-412.5: actual VoiceOver/mobile AT and manual 200%-zoom/focus/contrast/touch test. DP-410 remains independently open. |
| DP-422 | Route checker detects unowned self-canonical public page families, supports isolated build roots and truthfully reports live family coverage. | AC-422.1: approved, live primary Statement/Person/Topic/Content/Trace resources and MiniPC readback. The safe empty projection has **3/8 primary families**, not demo 8/8 acceptance. |
| DP-429 | Both explicitly empty and locally populated Explore views now have tested focus/status/dialog semantics, including browser 200%-zoom/reduced-motion checks; no provider requests. | Combined accessible search criterion requires real manual screen-reader acceptance, not a headless accessibility-tree proxy. |

## Independent validation and observed limits

- Python complete `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=poc python3 -B
  -m unittest discover -s tests -q`: **2833/2833 PASS** in **165.990 s**,
  backup/restore **PASS**. The calling `zsh` wrapper accidentally attempted
  assignment to its read-only `status` variable *after* the successful suite;
  the recorded `Ran 2833 tests … OK` and restore receipt belong to the test
  log, not a fabricated wrapper exit zero.
- DP-229 focused 45 public/Python/disposable PostgreSQL tests PASS with
  genuine temporal-fingerprint RED→GREEN reproduction; real qualified
  challenger review is not simulated.
- `npm run check`: **91 Astro/TypeScript files, zero errors/warnings/hints**;
  `npm run check:design` PASS;
  `npm run check:design:a11y` **8/8 PASS**, explicitly
  `manual_screen_reader: PENDING`.
- `node web/scripts/check-dp405-approved-empty.mjs`: PASS, isolated
  non-deployable build and eight unsafe-case rejects.
- `DP429_BROWSER=1 node tests/dp429_explore_accessibility_regression.mjs`:
  PASS for approved-empty and local populated fixture/browser contracts.
- `node prototypes/v4-implementation/dp407/test-contentrecord-real-wave11.mjs`:
  PASS for schema-valid synthetic Content, Chrome accessibility name,
  keyboard and editorial-state negative/positive checks. No real claim is
  published by these fixtures.
- Default `npm run build` without an explicit projection correctly
  **fails closed** (`PUBLIC_PROJECTION_PATH is required`). Re-running with
  the previously verified, empty v2 allowlisted fixture
  `/private/tmp/dpub-approved-empty-projection-20261010.json` succeeds
  with **8 generated HTML routes** (six public informational plus two
  noindex Account utilities); `npm run check:routes` PASS, exactly
  **3/8** primary families, zero aliases, 149 internal links.
- Repository contract PASS, deterministic benchmark **5/5 PASS**,
  `git diff --check` PASS; editorial launch preflight still
  **NO-GO, 49 blockers**.

## Strict release and follow-up boundaries

The current public information site remains independent of the repo `main`
source commit. No updated MiniPC immutable runtime, public-v3 content,
external reviewer decision, rights/use permit, personal account, paid
provider, source material or production database was written or inferred.
The original blocker list and the ticket dependencies remain in force.

Next possible genuine closeouts require (a) an actual documented assistive
technology session for public pages/components, (b) a qualifying approved
zero-record Person and at least one owner-approved public resource of each
primary family with MiniPC projection-to-reader readback, or (c) the
independently attested high-risk challenger review/waiver authority.
Those are *acceptance inputs*, not implementation shortcuts and not
synthetic data to manufacture simply to change the counter.
