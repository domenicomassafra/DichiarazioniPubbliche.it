# DP-319B (#449): authenticated private Camera PARSE_TEXT

Scope: the two archived Camera sitting transcripts already linked to the
Garlasco Collection. This is a private processing permission check and creates
no authorisation for a public excerpt, user-visible page or candidate promotion.

## Primary-source review and exact versions

- Camera sitting 0607, original stenographic minutes, 3 February 2026:
  <https://documenti.camera.it/leg19/resoconti/assemblea/html/sed0607/stenografico.htm>.
  Archived Capture SHA-256:
  `2ab7a0739d6ffc766b45526023ab4bd878c0e996fa90aa7d6dec6a3e0cc7de6f`.
  Current initial PG rights record:
  `private-rights:a7d7557a44f99d91d35ac97343b98a6129d2c094b30db474098f249d31f312b7`.
- Camera sitting 0703, original stenographic minutes, 4 August 2026:
  <https://www.camera.it/leg19/410?idSeduta=0703&tipo=stenografico>.
  Archived Capture SHA-256:
  `09aa5d2b696722819ca44c978b0c4000094fc60152a64fe81e4fb7e41a5df53f`.
  Current initial PG rights record:
  `private-rights:a522b988bda7d16b47e8e55d526ab05e3804c573f9196bfdb02b6fffa158493a`.
- Primary Italian legal rule: Law 22 April 1941 no. 633, article 5,
  <https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:legge:1941-04-22;633~art5>,
  and the Ministry of Finance article text:
  <https://def.finanze.it/DocTribFrontend/getAttoNormativoDetail.do?ACTION=getArticolo&codiceOrdinamento=0000000000000050000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000&id=%7B012E634A-9F52-4452-B7F7-980D83EDE0C6%7D>.
  The provision excludes texts of official state acts from copyright
  protection under this law. This documented determination covers only private
  parsing of the official stenographic text that was actually archived;
  it cannot be transferred to site layout, unrelated photographs, embedded
  media, third-party editorial commentary or a public quotation workflow.
- Privacy treatment: only text of public parliamentary interventions,
  already archived under the existing private source/purpose and retention
  policy. The excerpt is attributable to the named parliamentarian in the
  original minutes; the private text check does not authorize biometrics,
  profiling, collection of unrelated personal details or public reuse. Scope remains
  `PRIVATE_OFFICIAL_TEXT_ONLY_NO_PUBLIC_EXCERPT`.
- Jurisdiction IT, policy
  `dp426-camera-article5-private-text-20261025-v1`, existing rights-review
  expiry 24 November 2026. A changed official source/Capture, status, use,
  policy, revocation, supersession or validity window requires a new
  agent review and an independently authenticated receipt.

## Provenance and authority

The existing `private_source_rights_record` metadata is append-only, but its
`reviewer_ref` and `rights_receipt_ref` are **opaque references**, not
authentication. The addition uses the existing local HMAC reviewer credential
authority (DP-310/417) to sign a domain-separated receipt for precisely one
current rights record, Content ID, stored full-body Capture hash, `PARSE_TEXT`,
policy version, issuer role, official source URL, legal basis, jurisdiction and
expiry. The signing key stays outside PostgreSQL in private 0700/0600 files.
The additive `private_camera_parse_attestation` table stores the signed
payload and prohibits UPDATE, DELETE and TRUNCATE. Historical rows survive
reviewer revocation and later rights supersession; each live check re-reads
current rights and the active private signing credential. The fixed actor
`agent:private-rights-reviewer:camera` is the ONLY role admitted to issue.

The authenticated loopback Studio API accepts exactly
`POST /v1/rights/camera-parse-text` with JSON fields `content_id`,
`capture_sha256` and `use`. It returns an explicitly private decision,
never content text or public authorisation. Its database adapter remains
read-only. Other uses including `EXCERPT_PUBLIC` always fail closed;
incorrect hashes, absent/tampered MAC, inactive credentials, expired rights,
supersession and missing archived bytes deny access. The API can opt in with
`--camera-rights-authority-root`, referencing the same private directory
used by the existing reviewer identity administration.

## Private deployment and readback (after independent review and merge)

1. Install the additive migration using the repository's migration runbook,
   with a prior read-only check that the table does not already contain newer
   owner-produced schema. The procedure is repeatable and non-destructive.
2. Provision a distinct local reviewer credential with the existing
   `python -m dichiarazioni_pubbliche.reviewer_identity_admin --root PATH
   provision --credential-id camera-rights-20261026 --actor
   agent:private-rights-reviewer:camera --key-version v1` command, if absent.
   Do not log or export the credential secret. Existing grants do not
   constitute signatures.
3. Use `tools/dp449_camera_parse_receipts.py --authority-root PATH issue
   --content-id content:garlasco:camera:sed0607
   --credential-id camera-rights-20261026` and repeat for `sed0703`.
   Use `inspect` to verify the exact stored receipt for each source.
   The source bytes must already exist in PostgreSQL; the CLI never fetches
   new material, promotes candidates or publishes.
4. Read back both payloads and append-only count with PostgreSQL, run
   authenticated Studio HTTP source checks with valid and invalid hashes,
   check MiniPC service health and ensure both original candidates stay HELD.
   Never simulate credential revocation in the shared live authority:
   the negative test uses an isolated ephemeral credential + PostgreSQL.

The existing coverage need remains BLOCKED on independent source/context
checks under #439. Those checks are independent of the per-use private
authentication in #449.

## Validation and release handoff

The regression suite covers real PostgreSQL with both pinned source versions,
repeatable migration, immutable rows, private HMAC verification, current
permission and expiry, credential revocation, and the actual loopback HTTP
rights-check surface. Run via the ControlCenter resource guard:

```sh
python3 ~/.local/share/controlcenter/resource-guard/workload_launcher.py build -- \
  env LC_ALL=C uv run --no-project --python 3.14 --with pytest --with pyyaml \
  python -m pytest -q tests/test_dp449_camera_parse_authority.py \
  tests/test_dp449_camera_parse_postgres.py tests/test_studio_local_api.py
```

No checked-in receipt is an issued/production credential. A permission
record's opaque ID is never accepted as a signature.
