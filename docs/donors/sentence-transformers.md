# DP-157 — Sentence Transformers, only for private candidate hints

**Donor evaluated 2026-10-20:** [huggingface/sentence-transformers](https://github.com/huggingface/sentence-transformers), Apache-2.0, [tag `v6.1.0`](https://github.com/huggingface/sentence-transformers/releases/tag/v6.1.0), Git commit `b0bf39968ba461c34b29372144794eff1be06f6d`, released 2026-09-18. PyPI distribution `sentence-transformers==6.1.0` also declares `Apache-2.0`; wheel SHA-256 `eb8122f4d180f552eda26dc3d77e84e8c11dc2b1d456a406b9f24abb70ceeadd`, sdist SHA-256 `299025df51550dc1a38f05be27a9b0bf881c4e5e70542b3b7757d05e00aa3868`. Sources: [upstream license](https://github.com/huggingface/sentence-transformers/blob/v6.1.0/LICENSE), [release](https://github.com/huggingface/sentence-transformers/releases/tag/v6.1.0), [PyPI](https://pypi.org/project/sentence-transformers/6.1.0/). This is an **optional upstream dependency**, not copied source. Upstream Apache-2.0 notices and attribution apply to the installed package. Its library license **does not license any model weights**.

**Independent model gate: BLOCKED (as of 2026-10-20).** No pretrained model has been selected, fetched, installed or activated. Model weights/data license, revision, exact SHA-256 per local file, memory consumption and practical Italian recall/latency remain unverified. Do not infer permissive weights from the Apache-2.0 Python library. No model download is permitted without a separately reviewed permissive model license and a recorded inventory. This is a truthful weight gate, not a passing live accuracy or runtime benchmark.

## Adapter and invariants

The project adopts upstream `SentenceTransformer` via `private_semantic_matching.run_private_semantic_matching`, which takes the native `candidate_matching.MatchingInput` and delegates pair classification to the existing `candidate_matching.rank_candidate_matches` / `proposition_clustering.classify_proposition_pair`. Exact normalization, lexical matching, `matching_input_fingerprint`, replay, existing run IDs, cluster memberships, evidence, Person semantics, persisted dispositions, verified findings and the public projection remain authoritative. A hint is only `match_class=UNCERTAIN`, `disposition=HOLD`, `method=MODEL_SUGGESTION`, with no cluster ID, publication right or vector persistence. The adapter never modifies or inserts a database row. It only scores the bounded set of targets already retrieved through the native matching pool; no search or vector infrastructure is introduced.

Opt-in prerequisites on MiniPC hostname `udodo` (Linux), in an **isolated private backend process**:

1. An operator separately reviews the exact model repository revision (40-hex commit), full model license and provenance, and makes a local snapshot with safetensors weights. Reject a model whose license or redistributability is unresolved.
2. Create an operator-private JSON receipt outside the Git repository with the following structure (replace all placeholders with separately verified values and SHA-256 digests):

```json
{
  "model_id": "owner/model-name",
  "revision": "0123456789012345678901234567890123456789",
  "model_dir": "/home/udodo/.local/share/dichiarazioni-pubbliche/private-model",
  "license_spdx": "Apache-2.0",
  "license_source_url": "https://example.org/actual-model-license-at-pinned-revision",
  "license_reviewed": true,
  "files": {
    "LICENSE": "<actual 64-character SHA-256>",
    "model.safetensors": "<actual 64-character SHA-256>",
    "config.json": "<actual 64-character SHA-256>"
  }
}
```

The sample is a **schema illustration**, not authorization for any particular weights or claim about their license. Include **every** file in the on-disk model snapshot (e.g. `modules.json`, `0_Transformer/config.json`, tokenizer and pooling files). Symlinks, undocumented extra files, pickle weights and a mismatch of any file hash are rejected. The `LICENSE` file must be included and hashed. An operator sets `license_reviewed=true` only after separately verifying that the declared SPDX license applies to **that** exact model revision. Allowlisted SPDX identifiers are Apache-2.0, MIT and BSD 2/3-clause.

3. Install the opt-in `semantic-candidates` extra in a MiniPC-only environment, after checking its transitive package inventory, and set `DP_PRIVATE_SEMANTIC_ENABLED=1` and `DP_SEMANTIC_MODEL_RECEIPT=/absolute/path/private-receipt.json`. Invoke `run_private_semantic_matching(candidate, targets)` only from private operations. The library must be installed at exactly `6.1.0`. The default install/worker/browser/CI never activates it. No cloud API or Hugging Face Hub call is made by the adapter; `local_files_only=True`, `trust_remote_code=False`, `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1` apply.

Budget: at most 32 existing targets, 400 characters per text, 128 local model files, 384 MiB of fully hashed model files, safetensors only, 1024 output dimensions, 128 input tokens, CPU only, 1 compute thread and batch size 8. The child process is limited to 4 GiB address space and 40 CPU seconds; the caller waits at most 45 wall seconds. Missing flag, host, package, receipt, weights, license review, matching SHA, compatible model or child output returns an explicit blocked or disabled result with **zero** hints. The deterministic path is usable independently.

## Test and benchmark receipt

`tests.test_private_semantic_matching` contains synthetic vectors (no licensed language data or model weights) for Italian paraphrases and adversarial negation, quotations, homonyms, numeric values, claim type, period and republication. The vectors deliberately grant maximum similarity on negative examples; the deterministic gates still refuse them. Replay and existing lexical equivalence remain untouched. `tests.test_candidate_matching` and `tests.test_proposition_clustering` remain the regression authority. The offline fixture verifies contract/safety, **not** real semantic recall, weights memory consumption or latency. Compare the real model only after separately documented rights and weight acceptance; until then the required weight benchmark is **BLOCKED** and opt-in remains off. Existing DP-116 PostgreSQL candidate-search baseline reports 13/13 Recall@5 and approximately 51–57 ms p95 (ADR-0008); no incremental model lift is claimed.
