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
span or model-generated text enters that receipt, which is also attached to
the private provider receipt when the model returns zero new mentions. No
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

## Owner option A: upstream model due diligence (2026-10-23)

The owner chose to investigate `nickprock/it_spacy_ner_trf` on 2026-10-20.
Read-only upstream verification (no model weights acquired, installed or run):

- [Model card](https://huggingface.co/nickprock/it_spacy_ner_trf) identifies
  version `0.1`, model license `MIT`, required spaCy `>=3.5.1,<3.6.0`,
  and sole component `token_classification_transformer`. Revision
  [`1ded0d637d19ad528a76232efb75643273f976ac`](https://huggingface.co/nickprock/it_spacy_ner_trf/tree/1ded0d637d19ad528a76232efb75643273f976ac)
  offers a 406 MB wheel with SHA-256
  `6b77193b6f61d80f6bc25dc78aea06936c21322f6d541fd1d8261e14baf30363`.
  The current optional extra instead pins spaCy `3.8.16`, and this adapter
  requires `ner` or `entity_ruler`; loading the wheel unmodified would not
  satisfy either interface contract. No third-party source patch is authorized.
- [Underlying fine-tune](https://huggingface.co/nickprock/bert-italian-finetuned-ner)
  identifies base `dbmdz/bert-base-italian-cased` and training data
  `tner/wikiann`. The [WikiANN dataset card](https://huggingface.co/datasets/unimelb-nlp/wikiann)
  explicitly reports `license: unknown`: the model's `MIT` badge alone does
  not establish rights to reuse the training data and derived weights.
- [WikiNEuRal](https://huggingface.co/datasets/Babelscape/wikineural) is
  explicitly `CC-BY-NC-SA-4.0`; the [KIND authors' repository](https://github.com/dhfbk/KIND)
  marks its NER annotations `CC-BY-NC-4.0` / `CC-BY-NC-SA-4.0`.
  These are not unrestricted drop-in training-data replacements.

**Decision:** option A remains `HOLD` at the upstream rights and binary/API
compatibility gates. A blank Italian spaCy pipeline with an `EntityRuler`
can exercise the existing adapter and synthetic fixture without third-party
weights, but its hand-authored patterns are not a general-purpose pretrained
Italian NER model or an independent accuracy evaluation. Runtime use with a
real authorized Passage needs a separately documented model/data clearance,
model digest, rights fence, and independent review. No production/default
activation or public attribution follows from this investigation.

## 25 October 2026 — license review packet: independent Italian model candidate

**Review status: PREPARED, AWAITING A DISTINCT CHECKER AND APPROVER.** The
owner's 25 October decision in [#300](https://github.com/domenicomassafra/DichiarazioniPubbliche.it/issues/300)
assigns model/source licensing investigation and ultimate approval to agents,
in three distinct roles: preparer, checker, approver. This section is a proposal,
not an approval or permission to publish. The earlier `nickprock` option was
investigated and remains rejected for the `tner/wikiann` unknown data license
and incompatible spaCy binary/component interface.

### Origin and actual rights chain

1. **Training data, direct publisher**: Joel Nothman, Nicky Ringland, Will
   Radford, Tara Murphy and James R. Curran, [Learning multilingual named entity
   recognition from Wikipedia](https://figshare.com/articles/dataset/Learning_multilingual_named_entity_recognition_from_Wikipedia/5462500),
   Figshare DOI [`10.6084/m9.figshare.5462500.v1`](https://doi.org/10.6084/m9.figshare.5462500.v1),
   dataset v1, file ID `9446344`, `aij-wikiner-it-wp3.bz2` (6,316,939 bytes).
   The Figshare API `https://api.figshare.com/v2/articles/5462500` explicitly
   returns **CC BY 4.0** for the data; download endpoint
   `https://ndownloader.figshare.com/files/9446344`.
   Publisher MD5 `2554a867110a72189ac7f1a4de629de9` matches the downloaded
   archive. Locally computed SHA-256 is
   `d702670de515508b7b3341e3e088c9efd882c3647be6930b39f26a920dc4df69`.
   Attribution to all five dataset authors and link to original CC BY 4.0 license
   must accompany any model release/use. Dataset labels are silver standard.
2. **Upstream raw text**: the authors explicitly explain Wikipedia extraction.
   The independent checker must review whether Wikipedia CC BY-SA terms add
   attribution/share-alike duties for the exact derived weights before they
   approve commercial reuse; the Figshare CC BY 4.0 tag is evidence, not a
   substitute for that copyright analysis. No third-party pretrained weights
   were used by the local builder.
3. **Engine, trained weights, interface**: `spaCy==3.8.16` from Explosion,
   [MIT upstream release](https://github.com/explosion/spaCy/tree/26b4d1dc04a812f426e4bef3e8a1b6f159d6f048).
   `tools/dp158_train_wikiner_ner.py` seeds a fresh `spacy.blank("it")`,
   trains its native `ner` component exclusively on the SHA-pinned wp3 archive,
   and exports a standalone local model plus `dp158-manifest.json`.
   Its **untrained** Italian tokenizer is reconstructed on load via the
   explicitly approved `tokenizer_policy=blank-it`; the serialized model
   contains trained `ner` weights but no third-party tokenizer weights. This
   works around a spaCy 3.8.16 tokenizer deserialization `OverflowError`
   observed on both Python 3.13 and 3.14 for the original serialized tokenizer.
   Other pretrained models continue to load their packaged tokenizers.
   Locally authored script and new weights are intended Apache-2.0 with the
   underlying corpus CC BY 4.0 attribution; the second and third licensing
   agents must settle any additional Wikipedia obligations before acceptance.
   No `nickprock`, `dbmdz` or official `it_core_news_*` weights are incorporated.
4. **Consumer trial text**: one transcript in
   [SenatoDellaRepubblica/AkomaNtosoBulkData](https://github.com/SenatoDellaRepubblica/AkomaNtosoBulkData),
   commit `bfac144eb5c54820971bc1020fece11aae56ec90`, Git blob
   `bec30c067a1a79e8b377af483cfc4bfb44d13896`, file
   `Leg19/Atto00055187/resaula/01457617-ra.akn.xml`, full bytes SHA-256
   `1cb2b5fc3cbc96701e52f06c34c3ae3cd494eb622aa3f124fb1a93a223e27476`.
   The upstream README and LICENSE at that commit declare **CC BY 4.0**.
   The bounded probe reads a single speech in memory with no database mutation;
   it logs only source/version hashes, offsets and candidate labels. The #331
   operational rights record currently permits `STORE_BODY`, **not** automatic
   `EXTRACT_CANDIDATES`/promotion of its captured passage: the trial must not
   be portrayed as production source-use clearance.

### Reproducibility and release gates

Run locally on the Studio via the resource guard, from an isolated workspace,
after placing the exact archive at `/private/tmp/dp158-wikiner-it-wp3.bz2`:

```sh
python3 /Users/domenico/.local/share/controlcenter/resource-guard/workload_launcher.py --max-wait 300 build -- /private/tmp/dp158-spacy-venv313/bin/python tools/dp158_train_wikiner_ner.py --archive /private/tmp/dp158-wikiner-it-wp3.bz2 --output /private/tmp/dp158-it-wikiner-ner-model-v2 --examples 4000 --epochs 3
```

The builder fails closed for an archive SHA mismatch and refuses overwriting a
preexisting model directory; a deterministic sampling seed and disjoint
same-source holdout are recorded. **The holdout cannot establish accuracy on
Senato parliamentary language, homonyms, nested quotations or reported speech**;
it is only a diagnostic. `dp158_senato_private_ner_readback.py` uses the
existing `ApprovedSpaCyModel` + `SpaCyItalianPrivateAdapter.load()` interface,
checks the Senato input SHA, then proposes spans without any `commit_batch`.
Negative rights/review cases continue to HOLD under the existing extraction
fence. The checker should reproduce archive digest, source text/license chain,
model binary/manifest digest and terms. A different agent may then sign off in
the issue; until that happens model rights, operational extraction and
publication all remain **HOLD**.

### Actual preparation and private inference (Mac Studio, 2026-10-25)

- Training used isolated Python **3.13** + spaCy **3.8.16** on the Studio,
  admitted by the resource guard. Input Figshare archive was verified before
  parsing and training. **3,600** randomly sampled training sentences and
  **400** disjoint holdout sentences, **3** epochs, seed **158**. Exact span
  counts on this same-source silver holdout: **TP 562 / FP 244 / FN 207**;
  this is an internal diagnostic, not an independently adjudicated NER gold.
- Private artifact: `/private/tmp/dp158-it-wikiner-ner-model-v2`.
  `dp158-manifest.json` states `license_review=PENDING_INDEPENDENT_CHECK_AND_APPROVAL`,
  `tokenizer_policy=blank-it`; reloaded pipeline SHA-256:
  `ab6908acc150f1dcbba545df372e446340c12234df1d4635f23f6516dded14b6`.
  The adapter validates this digest again before every inference. An earlier
  run with a serialized tokenizer produced weights but failed model reload;
  it was not accepted as the candidate artifact.
- Direct private readback:
  `tools/dp158_senato_private_ner_readback.py --document /private/tmp/dp158-senato-20250529.xml --model /private/tmp/dp158-it-wikiner-ner-model-v2 --speech-ordinal 40`
  (through resource guard and the isolated Python 3.13): **exit 0**. The exact
  public Senato XML SHA-256 matches the existing #331 Capture, the ephemeral
  normalized speech has SHA-256
  `20945f54e1f69fbe55422db23f3d148526c616e2e2ca784f883da1e1728924ec`;
  **7 candidates: PER=4, LOC=3, ORG=0**. The tool returns offset/label/hash
  for each span but no text, named identity, approved speaker or DB write.
- **Consumer boundary**: MiniPC web service was `active`, `/api/v1/health`
  returned `ok`, `DRAFT` and `dossier_count=0`; its system Python did not
  have spaCy installed. Hence there is no claim of MiniPC NER inference or
  consumer activation from these Studio observations.

**Next-agent review handoff:** an agent distinct from this preparer must
verify exact Figshare article/file/digests and the Wikipedia-derived rights
chain, proposed model output obligations, model metadata and pipeline digest,
source license/attribution, and any repository policy relevant to private
processing. A third, distinct agent must make and record the final licensing
decision in [#158](https://github.com/domenicomassafra/DichiarazioniPubbliche.it/issues/158)
and identify the permitted usage scope; only after those steps may a private
consumer installation be activated, with an `EXTRACT_CANDIDATES` rights record
for any persisted passage and an independent review of generated candidates.
