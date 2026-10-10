# Informational-preview artifact preflight — 2026-10-10

Scope: the six static informational pages specified in the owner's local
`LAUNCH.md`, with an approved-empty public v2 projection. This is **not**
stable-v1 DP-705 acceptance and does not replace DP-304/307/410/701/702
review. No publication, source-rights clearance or legal approval is inferred.

The new read-only checker `tools/check_informational_preview.py` requires a
fingerprint supplied independently of the built public artifact. For a CI
test-only *empty* projection, prepare a separate JSON file with
`schema_version=dichiarazioni-pubbliche-public-v2`, `dossiers/topics/contents=[]`,
`dossier_count=0`, `methodology.aggregate_person_score=false`, an explicit
`generated_at`, and `dataset_sha256` equal to the SHA-256 of canonical JSON
`{"contents":[],"dossiers":[],"topics":[]}`. It may be used to test the build
contract but is **never** evidence of actual editorial approval.

Run after an isolated Astro build (never copy an old `web/dist` into production):

```sh
python3 tools/check_informational_preview.py \
  --dist /absolute/isolated/build \
  --projection /absolute/separately-provided/index.json \
  --expected-fingerprint /REPLACE_WITH_INDEPENDENT_64_CHAR_SHA/
```

The default exit code remains `2` after a mechanically good bundle: human
release/privacy/legal authority is still pending. For **CI mechanical checks
only**, add `--bundle-only`; a passing source-plus-bundle check then exits `0`
while the receipt still carries `launch_authorized=false` and lists the open
DP-304/307/701/702/owner/MiniPC signoffs. The option refuses a missing source
projection. An optional bundle-only inspection through the Python function
`check_preview_bundle` explicitly reports `source_projection_checked=false`
when no source is available and must not be used as release evidence.

The checker validates the projection fingerprint from its actual empty arrays,
its dataset count and anti-score policy; the generated search-index's original
projection SHA and independently recomputed index SHA; six public canonicals;
`index,follow` for only the public documents; `noindex,nofollow` for optional
account utility pages; exact six-entry sitemap and robots policy; no Studio,
demo, private or unexpected output files, including unreferenced Astro JS
chunks. It reads the original privacy/legal/release ticket statuses and Q-306
register rather than interpreting PLAN-only `DONE` as signoff.

RED-to-GREEN regression coverage: 12 synthetic tests in
`tests/test_informational_preview_preflight.py`, including poisoned index with
a newly computed hash, private input fields, missing projection source,
Studio bundles, demo overrides and absent original-ticket closure.

**Observed blocked artifact, then fixed local build:** an initial isolated
explicit-empty-projection Astro build on the Mac produced eight HTML pages
(six informational and two private account utilities), but still emitted publicly fetchable
`_astro/StudioReadOnlyWorkspace.D05KtirE.js` containing `fixture_only` and
`_astro/StudioWorkspaceClient.C8bXOybZ.js`. The preview checker correctly
rejected that candidate. After the public-build Astro exclusion hook was
updated, a fresh isolated build at `site3` (never deployed) passed the
new checker with six public routes, two `noindex` account routes, zero search
records and no Studio/demo JS assets. The externally pinned *empty-shape*
fingerprint was
`501348d9638ee3c4d929205d2e6dca7eb2c8a552ac006dee837ea032a739ae7a`;
the mechanical receipt was
`c0892453d9446f90d343910e00504796675a210eeccbc9941310cb2fcac250da`.
This remains a test-only public-shape projection, not evidence of editorial
approval or a deployed site.

The separate `tools/check_dp422_live_readback.py` still performs the
MiniPC/live HTTP API/projection/body checks; the two gates cover different
boundaries. A clean local bundle also cannot prove HTTPS, privacy policy,
domain holder, public contact, trademark, counsel or rollback acceptance.
