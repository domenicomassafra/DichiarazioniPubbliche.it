# Optional local CPU claim extraction: private candidate lane

This is an explicitly **disabled-by-default** alternative inference transport
for permitted private research windows. It is **not** the official DP-201
OmniRoute canary, not a DP-202/203 dependency waiver, not proof of source
rights, and never approval to publish or attribute a claim.

The provider accepts only the already-installed qwen3:4b model through
http://127.0.0.1:11434. The operator must independently inspect the exact
full SHA-256 model digest from the local Ollama model catalog and pin it.
Before transmitting any window, the client checks the digest, uses no proxies
and rejects redirects and external network destinations. There are no model
downloads or external routes added to the production worker by this change.

Only in an authorized, isolated private acceptance environment, supply:

    DICHIARAZIONI_PUBBLICHE_LOCAL_CLAIM_ENABLED=1
    DICHIARAZIONI_PUBBLICHE_LOCAL_CLAIM_MODEL_SHA256=<operator-verified-64-hex-digest>
    DICHIARAZIONI_PUBBLICHE_CLAIM_MAX_USD_PER_1K_TOTAL_TOKENS=0

An OmniRoute credential and local claim opt-in cannot be used together.
Zero means explicitly accepted **zero external API-token billing**: CPU,
electricity, retention and storage costs still exist; current queue caps and
relevance/rights source permits remain mandatory.

Generated claims must cite exact in-window segment IDs, a nonempty verbatim
source quote, valid claim taxonomy and strict boolean values. A model returning
an unsupported, truncated or source-unbound response fails closed. Quote
substring matching does NOT establish correctness, full transcript fidelity,
public quotation rights or verified speaker attribution. Existing human and
contextual review remains mandatory. Receipts identify ollama-local, never
misidentify the model as OmniRoute.

On 2026-10-10 the MiniPC was already running Ollama and an installed qwen3:4b
model. Its local tag has an independently observed full SHA-256 digest starting
with 359d7dd4. A synthetic Italian sentence passed a schema-constrained
loopback extraction with an exact input quote in 7.42 seconds, while an
unconstrained earlier probe returned unwanted reasoning instead of JSON.
This is **transport/model feasibility only**: no private real content was sent,
no claim was approved, no production worker feature enabled and no production
DB or source registry mutated. Real corpus acceptance, independent model
benchmark, owner/provider route decision and review are still pending.
