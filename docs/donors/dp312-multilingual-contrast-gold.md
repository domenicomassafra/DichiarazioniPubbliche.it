# DP-312 — Multilingual contrast gold: legal/source and donor receipt

Date: 2026-10-20. Scope: private source-only evaluation, no editorial approval.

`tests/fixtures/dp312_multilingual_gold_v1.json` has 22 **original fictional**
IT/EN/DE/FR utterances and 5 distinct translation-risk contrasts. No third-party
text, audio, video, likeness, private personal data, historical quote, or actual
source claim was copied. The repository's
**DICHIARAZIONI-PUBBLICHE-FIXTURE-POLICY-1.0** covers the test materials under
Apache-2.0 (see `docs/licensing/README.md#synthetic-fixture-policy` and
`tools/generate_fixture_inventory.py`). Original annotations were fixed in the JSON
*before* executing tests against the classifier. The comparison is independent
of the classifier's return values, but **no external independent human reviewer
has adjudicated it**. It does not establish a publishable real-source gold set.

Prior-art/legal review:

- [spaCy Matcher](https://spacy.io/api/matcher) and
  [spaCy source](https://github.com/explosion/spaCy) (**MIT**; active 3.8 series
  and repository development) offer token/phrase pattern matching. Existing
  regex screening is already adequate for the six missing quantifier cues;
  adding a full NLP dependency would not prove semantic scope or reviewer
  authority. No source code or model copied.
- [European Commission Speech Repository disclaimer](https://speech-repository.webcloud.ec.europa.eu/content/legal-disclaimer)
  references CC BY 4.0 for EU-owned content but excludes some third-party and
  personality rights. Its [legal notice](https://speech-repository.webcloud.ec.europa.eu/content/legal-notice)
  separately limits redistribution without prior written authorization.
  Since these conditions cannot by themselves certify any particular speaker
  or source clip, no material was copied from that repository.
- [European Commission reuse notice](https://commission.europa.eu/legal-notice_en)
  describes EU-owned content under CC BY 4.0 but explicitly excludes rights
  of third parties. This is a possible future document-specific review path,
  never a blanket permission to publish transcribed words.

Reused existing Python `re` (stdlib/PSF) and `context_integrity`,
`wording_risk_patterns`, `wording_contract`, `relation_runtime` (project
Apache-2.0). No external dependency or novel speech-act parser was introduced.
The new regression checks exact source-hash revision and distinct utterer,
translation parity and a real private relation consumer. The source texts and
annotation references remain fictional; public publication and persisted
Finding/summary invalidation remain unverified.
