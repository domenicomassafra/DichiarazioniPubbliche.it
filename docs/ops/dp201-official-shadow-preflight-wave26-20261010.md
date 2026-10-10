# DP-201 — Official OmniRoute 3.8.51 shadow preflight (Wave 26)

**Source authority:** `main` at `bea4b8e` when this isolated work began, 2026-10-10.
**Mode:** local read-only validator; zero provider requests, zero credentials, zero
install/upgrade, zero database/service mutations. This document does not close DP-201.

## Observed external blocker, sanitized

The historically recorded meaningful DP-201 canary against official OmniRoute
`3.8.50`, `antigravity/gemini-3.8-flash-tiered`, returned HTTP **400** with
category `bad_request` in approximately **5.15 seconds** on 2026-09-22. The
last matching HTTP 400 in the MiniPC's local OmniRoute call-log metadata was
2026-10-04T18:36:16.387Z on the top-level policy and
18:36:16.332Z on the Antigravity step. It is classified only as
`PROVIDER_UPSTREAM`: `error_type` is empty, and no persisted response body or
pipeline detail gives an upstream subcode. That October request cannot be
identified conclusively as a DP-201 canary. **The exact root cause is unknown.**

Official source `v3.8.50` does not exclude Gemini tool JSON-schema keys
`prefixItems`/`additionalItems`; official `v3.8.51` does. This fixes a known
tool-schema compatibility class, but the **actual DP-201 claim client uses a
plain chat payload without `tools`, `response_format` or a JSON-schema tool**.
There is no evidence that those schema keys caused its HTTP 400. No model
replacement or alternative route was accepted as proof.

The canonical ControlCenter report-only official-release gate previously
returned **3.8.51 ELIGIBLE, all seven checks passed**, including three required
fix-ancestry checks. This is a release *provenance* result, not a working
Gemini tier or claim-extraction result. The MiniPC still ran official 3.8.50
when the worker checked it on 2026-10-10. The old local 3.8.51 runtime is a
**LOCAL-FORK** and cannot be substituted for an official release.

## New offline readiness contract

`tools/dp201_official_shadow_preflight_wave26.py` accepts six explicit
non-secret inputs:

1. A **locally available** uninstalled, unexecuted `omniroute` npm `.tgz`.
2. A local JSON report emitted by ControlCenter's existing
   `omniroute/tools/check_official_release_gate.py` in report-only mode.
3. An **independently reviewed SHA-256 pin** for the exact bytes of that report.
   A checksum computed from the same untrusted report during validation does
   not authenticate it. Pin via the approved release ledger/separate trust path.
4. A synthetic response fixture. The bundled fixture is
   `tests/fixtures/dp201-shadow-response-wave26.json` and contains no provider
   receipt or private transcript.
5. A **positive** maximum USD rate per 1,000 combined input/output tokens.
6. A **positive**, explicitly approved USD spending cap for the two-call
   probe + extraction sequence, at most the existing **$0.25/job** limit.

The tool compares the independent SHA-256 pin with the report; requires
`ELIGIBLE`, official version **exactly 3.8.51**, all seven provenance checks,
stable npm/GitHub/Docker metadata and three affirmative fix-ancestry proofs;
compares the tarball's SHA-512 with the npm integrity in that pinned receipt;
and checks its unextracted package name/version. New versions, locally rebuilt
tarballs, missing proof and hash drift fail closed. The Docker tag is checked
only as release evidence; Docker images are **not** run or promoted here.

Next the tool reconstructs both existing canonical requests entirely in
memory: the meaningful `OmniRouteClaimClient.probe()` (256 output tokens)
and `extract()` (2,048 output tokens), always on
`antigravity/gemini-3.8-flash-tiered` with `claim-extract-v1`. It validates
the unchanged simple chat shape and applies the production claim parser to the
synthetic response fixture. The fixture must resolve to one check-worthy,
numeric-sensitive price claim tied exclusively to segment 0. It cannot confer
provider success, attribution approval, or publication permission.

For a conservative **local estimate**, the gate counts the UTF-8 bytes of each
request prompt as input-token proxies, adds the two maximum output-token
budgets, multiplies by the separately verified upper rate and rounds up to a
micro-dollar. It rejects zero/unset/negative rates, insufficient caps and caps
above $0.25. This estimate is **not a remote billing guarantee**; live daily,
source, job and provider-side cost/usage checks must still be verified before
any authorized request. The default worker limits are $5/day globally,
$1/day per source and $0.25/job; none are reset or bypassed here.

## Offline invocation

From the repository root, **after** obtaining independently trusted release
evidence and locally staging a release tarball (performed separately by the
authorized runtime owner):

```sh
PYTHONPATH=poc python3 tools/dp201_official_shadow_preflight_wave26.py \
  --artifact-tgz /path/to/pinned-official-omniroute-3.8.51.tgz \
  --official-gate-receipt /path/to/independently-reviewed-release-gate.json \
  --trusted-gate-sha256 '<independently-reviewed-64-hex-sha256>' \
  --offline-fixture tests/fixtures/dp201-shadow-response-wave26.json \
  --max-usd-per-1k-total-tokens '0.01' \
  --approved-max-cost-usd '0.10'
```

The quoted numbers are **illustrative operator inputs**, not a verified
OmniRoute price or spend authorization. Only a verified official upper rate
and an operator-approved cap can be used in an acceptance run. A successful
offline report returns `OFFLINE_READY_FOR_OPERATOR_REVIEW`, with request
hashes, configured rate/cap and the conservative two-call cost estimate. It
always returns `live_canary_executed=false`, `paid_call_authorized=false`,
`provider_receipt_recorded=false` and
`live_budget_snapshot_verified=false`. Failure exits `2` with a sanitized
reason code. No input bodies, prompts, keys, credential paths or exception
details are printed.

## Exact next owner actions to close DP-201 and unblock DP-202

1. The runtime owner must obtain the **official npm 3.8.51 tarball** and
   independently pinned fresh official-release report. Execute the offline
   preflight; keep the 3.8.50 production symlink, service and DB unchanged.
   The past official release-gate 7/7 result alone does not supply those bytes.
2. The owner must approve a **DP-specific, least-privilege OmniRoute client
   credential** in the worker's private environment, not reuse/copy the
   OpenCode client auth. Supply a verified **positive USD/1k total-token
   ceiling** and approve an explicit cap for the intended two calls. The
   MiniPC's `runtime.env` had neither `OMNIROUTE_API_KEY` nor that rate, and
   `claim-runtime.env` was absent on the 2026-10-10 sanitized readback.
3. After release provenance, correct private-scoped credentials, budget
   snapshot/provider billing controls, and an isolated **shadow 3.8.51**
   runtime are approved, the **next separately authorized paid/model request**
   is exactly one meaningful `probe()` on
   `antigravity/gemini-3.8-flash-tiered` (`claim-extract-v1`, Italian numeric
   segment, max 256 output tokens). Record model, version, sanitized HTTP
   code/upstream category, duration, request identity and provider usage/cost
   if supplied. Do not retry on a 400 or substitute another model.
4. **Only if** the first canary produces a nonempty canonical valid claim
   schema, separately approve/execute one bounded `extract()` on the same
   source window with 2,048 maximum output tokens, under the already reviewed
   **total sequence cap**. Persist the real provider/model/usage/cost receipt;
   verify expected claim/segment binding and a real cost circuit breaker.
   Do not fabricate usage if the provider omits it. Fail closed if receipt,
   cost enforcement, content or upstream path is inadequate.
5. Complete DP-201's actual MiniPC acceptance on the approved official
   runtime and record the receipt. **Then** and only then may DP-202's
   one-parent/Giuliani evaluation begin; DP-203 fan-out follows DP-202.

**DP-204 Groq remains separate and BLOCKED.** The sanitized 2026-10-10
readback also found no `GROQ_API_KEY` in the worker's environment. Groq needs
its own private credential grant, bounded audio duration/spending cap, real
receipt and sensitive-token fallback/hold proof; neither this tool nor the
OmniRoute client's unrelated auth supplies that grant.

## Validation / change ownership

RED: `tests/test_dp201_official_shadow_preflight_wave26.py` failed with
`ModuleNotFoundError` before its isolated implementation existed. GREEN:
the focused test suite verifies official artifact tampering, untrusted release
receipt changes, unauthorized versions, incomplete ancestry, missing/zero
cost cap, excessive budget, model substitution, forbidden tools and invalid
schema, plus exact parity with mocked canonical `probe()`/`extract()` calls.
The mock exercises no network. No existing app module, ticket, production
configuration, corpus, release preflight or other worker's file was edited.
