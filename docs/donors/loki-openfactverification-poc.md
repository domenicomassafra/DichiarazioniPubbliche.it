# #160 — isolated Loki/OpenFactVerification fork POC

**Retired from the executable codebase on 2026-10-29 (#545).** The four
`loki_*_poc.py` modules were fixture-only, never imported by production code,
and never granted publication authority. Their two isolated test modules were
removed with them. This file preserves the historical donor and license audit;
the shared EUR-Lex source fixture remains for other provenance checks.

- Upstream: https://github.com/Libr-AI/OpenFactVerification, **MIT**, Copyright
  (c) 2024 LibrAI. Complete verbatim notice:
  [loki-openfactverification-mit.txt](./loki-openfactverification-mit.txt).
- Maintainer fork: https://github.com/domenicomassafra/OpenFactVerification.
- Pinned upstream HEAD: `6e1ee9e5159abe544c342689093afe12b908a419`,
  2024-10-03. Last release `v0.0.2` (2024-04-21); no post-2024
  code push observed as of 2026-10-20. Adapter version
  `dp160-loki-private-poc-v2`, donor version `v0.0.2+6e1ee9e`.
- Only derived components: upstream
  `factcheck/core/Decompose.py` (decomposition, source span restoration),
  `factcheck/core/CheckWorthy.py` (per-claim selection), and
  `factcheck/core/QueryGenerator.py` (bounded proposed research questions).
  Mapped to `loki_decompose_poc.py`, `loki_checkworthy_poc.py`,
  `loki_query_generator_poc.py`. This was an **adapted selective port**,
  not a verbatim vendored package. No other Loki files or dependencies
  were imported, packaged, or executed.

## Safety adaptations and comparison (historical)

The 2024 source uses `eval(response)` and model-provider calls in all
three stages; `CheckWorthy.py` falls back to assuming all inputs are
check-worthy, `Decompose.py` falls back to sentence splitting, and
`QueryGenerator.py` falls back to using the raw claim as a question.
Those behaviors are **not accepted** for this product.

The retired phases accepted explicitly passed offline JSON fixtures,
rejected duplicate object keys (even in nested responses),
validated source-span uniqueness and literal time/quantity references,
checked negation cues in the claim, source span and enclosing sentence across
Italian, English, German, French and Spanish,
conservatively held legal *application* versus *entry-into-force* substitutions
even when dates and source spans otherwise match (real EUR-Lex original OJ
IT/EN regression in
[`dp160-eurlex-article113.md`](../reviews/dp160-eurlex-article113.md)),
blocked obvious reported-speech context even if fixture metadata incorrectly omitted
its flag,
rejected malformed/partial or policy-incompatible outputs, capped queries, and
failed closed without retries, providers, NLTK, Playwright, models or network.
Historically, `DP_LOKI_OFFLINE_POC=1` enabled **local comparison only**;
`LokiPrivatePOC(enabled=True)` was a fixture test hook. Neither exists after
#545, so these are not runtime instructions.
Each invocation produced a content-hash-only private receipt recording
donor pin, adapter version, `provider_calls=0`, `provider_cost_usd=0`,
and `publication_authority=false`. All results stayed `HOLD` even
for positive proposed clauses. There was no storage, verdict, score,
approval, retrieval, query dispatch, promotion or public projection hook.

The retired comparison tests covered an existing offline `poc/fixtures/italian_cases.json`
claim (its benchmark's `SUPPORTED/PUBLISH` expected label remained inaccessible
as a POC verdict), synthetic Italian compound numbers, English,
German and French dates/quantities, reported speech, non-factual statements,
malformed JSON/code-looking input, missing output, mismatched numbers,
duplicate/overlapping source spans, fabricated query quantities, disabled
configuration and the incumbent `validate_provider_payload`,
`validate_atomic_claim`, `compile_claim_research_plan` boundaries.
These fixtures did **not** assert independent factual correctness, licensed
live source availability or a measurable quality advantage over the
current extraction. The negation and reported-speech guards were lexical and could HOLD
ambiguous clause scopes; they did not establish semantic entailment or speaker identity.
No upstream component was promoted to production
without a separate rights-cleared gold benchmark and cost/quality evidence.

The upstream repository's `requirements.txt` includes `openai>=1.0.0`,
`anthropic`, `nltk`, `playwright`, `opencv-python` and others;
**none** were installed for this POC. No model or dataset weights were
included; additional model/data licenses would require independent review
before any future use. The project AtomicClaim, receipt, review,
provenance, privacy and publication rules remain authoritative.
