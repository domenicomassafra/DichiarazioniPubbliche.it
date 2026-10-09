# GOAL INFINITO — Wave 8: Discovery resume budgets, Capture URLs, private draft

Date: 2026-10-09 Europe/Rome. This is a source implementation checkpoint,
**not an authorization** to ingest Garlasco sources or publish v1.

## Starting authority and measurements

- Source `main` before this tranche was `302537088745e1e35d1c0a04aaeef60f5ac5363e`.
  Its exact GitHub CI run `37951300010` is **11/11 SUCCESS**.
- Canonical 125-ticket backlog: 86 DONE, 24 IN PROGRESS, 6 BLOCKED,
  9 FUTURE — **39 open**. M7 launch preflight **NO-GO 41 blockers**,
  receipt `890103b989d86e2ad2a112c943aa57d1f0e52e24a50ddd14d64ff42cc3bf7399`.
- Production MiniPC remains unchanged: Garlasco PAUSED, 18 included
  historical Contents, 30 historical Atomic Claims, no accepted real Discovery
  Hit, Capture, Passage or Candidate proof. The DP-417 migration is still
  uninstalled. No provider credential, rights review, license, source
  approval or release authority has been inferred from tests.
- Preexisting owner's untracked
  `docs/reviews/2026-10-09-goal-infinito-tutti-ticket.md` remains untouched.

## Source changes

1. **DP-209 / DP-214 Discovery persisted billing:** When restarting a
   previously started Research Discovery Run, read its canonical scoped
   provider_receipt `billing_basis` along with prior attempts. A prior paid
   attempt with `UNKNOWN` billing resumes as uncertain instead of zero-cost;
   the next provider is `BUDGET_BLOCKED` and receives no invocation. Worker-1
   demonstrated an actual RED (later adapter called) on old code and GREEN
   (zero calls) with the fix. Prime additionally ran the new SQL directly
   against authoritative MiniPC PostgreSQL with `BEGIN READ ONLY`;
   `cost_uncertain=false` for a nonexistent controlled run and syntax/joins
   passed without any database mutation.
2. **DP-210 / DP-214 Capture destination and final-response integrity:**
   Validate initial and final HTTPS URLs, block local/internal destinations,
   non-global IP literals, ambiguous numeric-IP spellings, forbidden ports,
   credentials and malformed authorities. Accept only fully completed HTTP
   2xx responses with typed status/length. Validate bounded response byte
   limits before invoking a fetcher. The pipeline does **not** certify
   arbitrary network transports against DNS rebinding; that remains an
   explicit non-closed transport/operational gate.
3. **DP-214 private Garlasco seed export:** Create the 0600 private draft
   relative to a verified, owned, 0700 directory descriptor, with no-follow
   and exclusive-create flags. Symlink parent refusal and a simulated
   concurrent parent swap prove an attacker-controlled replacement directory
   receives no private content. The draft remains deliberately marked
   INCOMPLETE_UNREVIEWED_SEED_NOT_FOR_INGESTION.

Two sleeping workers were reused simultaneously for disjoint Discovery and
Capture source/test files; prime independently edited inventory source/tests,
canonical ticket docs, PLAN and this checkpoint. Neither worker committed,
pushed, fetched real content, performed provider calls, changed production
or installed a migration.

## Gate evidence and next executable work

Combined Discovery, Capture and Garlasco-inventory focused tests **62/62
PASS**. Full Python suite **2,049/2,049 PASS** in 110.03 seconds,
including isolated restore drill `RESULT: PASS` and technical-only inventory
of 100 tables and 1,248 fields. Discovery resume SQL was independently
executed in an explicit MiniPC PostgreSQL READ ONLY transaction, with no
production row written. Source SHA and GitHub CI are recorded after their
actual execution. Remaining authentic-source prerequisites:
an owner-qualified Camera/Senato or other Garlasco-relevant source family,
reviewed private capture/model-use rights, source/lineage/Collection evidence,
Q-306 legal dispositions, 82 more authentic Garlasco Contents and accepted
provider/budget canary where required. DP-214/215 are still IN PROGRESS;
M7 stays NO-GO. Candidate/review or source material must not be fabricated
to satisfy the tests.
