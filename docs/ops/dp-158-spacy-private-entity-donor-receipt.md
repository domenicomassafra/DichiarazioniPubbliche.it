# DP-158 — spaCy Italian private entity proposals

Status: **adapter available, opt-in; no pretrained Italian model approved or activated**.
This receipt covers the library and the synthetic in-memory gold, not deployment
against real Content, a production rights grant or automatic person attribution.

## Donor and license evidence (verified 2026-10-20)

- Adopted upstream: [explosion/spaCy](https://github.com/explosion/spaCy),
  MIT, release **3.8.16** (2026-08-24), tag
  [release-v3.8.16](https://github.com/explosion/spaCy/tree/26b4d1dc04a812f426e4bef3e8a1b6f159d6f048);
  exact release commit `26b4d1dc04a812f426e4bef3e8a1b6f159d6f048`.
  Distribution: [PyPI spaCy 3.8.16](https://pypi.org/project/spacy/3.8.16/).
  Attribution/notice: Explosion, MIT license, available in upstream repository and
  installed package. No source file copied into this project. The repository's
  Apache-2.0 license continues to cover only original code.
- API reused: spaCy `Language`/`Doc.ents`, `Span.start_char`, `Span.end_char`
  and `Span.label_`. The separate wrapper implements only local safety,
  provenance and existing Candidate persistence contracts.
- **Do not use the official Italian pretrained pipelines by default.**
  [it_core_news_sm 3.7.0](https://huggingface.co/spacy/it_core_news_sm/blob/main/meta.json)
  declares **CC BY-NC-SA 3.0**; [it_core_news_lg](https://huggingface.co/spacy/it_core_news_lg)
  is also **CC BY-NC-SA 3.0**. Neither is approved for this product;
  swapping from `lg` to `sm` does not resolve the license restriction.
  No pretrained weights, model package, fixture from these models or model
  download script is distributed here.

## Exact adapter / activation contract

`pyproject.toml` exposes the isolated `private-spacy` optional extra pinned to
`spacy==3.8.16`; stdlib-only installs are unchanged. The new
`dichiarazioni_pubbliche.candidate_spacy_private` module accepts an explicit,
locally installed Italian `Language` with `ner` or `entity_ruler`, with
`ApprovedSpaCyModel(source_url, revision, license_id, pipeline_sha256)`.
The model must have a compatible allowlisted license in its actual metadata,
and the complete serialized spaCy pipeline digest must match the approved
receipt. This does **not** automatically authorize any third-party model:
the source/revision/license and permitted reuse must first be reviewed.
`SpaCyItalianPrivateAdapter.load(Path(...), approval=...)` fails closed on
unavailable files, missing spaCy, metadata mismatch or digest mismatch and
never downloads or selects a default model.

The entrypoint `extract_passage_candidates_with_spacy(...)` requires the current
private `authorization_guard` and `PrivateCandidateCommitFence`. Both are
passed into the existing `extract_passage_candidates` pipeline for repeat
rights checks and transactional authority at commit. spaCy processes only the
already approved private Passage in memory; candidates are committed by the
existing path. Changing the approved model fingerprint changes the extraction
operation key (via the versioned provider), preserving replay identity.
The wrapper is **not** wired into a public route, daemon or production operator
CLI. Explicit integration can occur only after model and corpus rights approval.

The adapter validates exact input `text_sha256`, language `it`, unchanged
document text, character offsets, span equality, and per-span text SHA-256.
It accepts spaCy labels `PER`, `ORG`, `LOC` and ignores `MISC`.
Existing private schema stores `PERSON` and `ORGANIZATION`; for `LOC`
the proposed canonical type is **NULL**, keeping `ner_label=LOC` in private
metadata until an independently reviewed location ontology exists. spaCy
mentions use the existing `MODEL` extraction method with
`ner_backend=spacy` and an auditable metadata-only model receipt. No
speaker identity, target ID, entity resolution, statement approval, Finding,
publication, score or public read is derived from NER. The existing known
alias candidate resolver runs unchanged and its choices remain unapproved.

## Deterministic gold and boundary checks

`tests/test_candidate_spacy_private.py` provides a wholly synthetic Italian
passage with repeated identical person names, nested quoted speech, an
attributed/reported statement, ORG, LOC and the negative ordinary word
`organizzare`. Gold: 3 PER + 1 ORG + 1 LOC with exact offsets/hashes.
The test checks independent alias targets, no implicit identity/speaker
assignment, retention of the old extraction output without opt-in, replay,
revoked/missing rights, corrupt input, incorrect language, malformed spans,
disallowed model license, missing model/NER and digest mismatch.
An additional optional test exercises the *real spaCy* `EntityRuler` API using
this synthetic in-memory pattern set, which is user-authored fixture data
under this repository's Apache-2.0 license. The same deterministic gold is
verified without spaCy so the default contributor suite requires no download.

## Pending gate

An Italian model with independently verified compatible weights/data license,
source/revision and approved pipeline digest is still required for real use.
Until this is resolved, the default path remains the existing extractor and
there is **no** spaCy production activation or source processing permission.
