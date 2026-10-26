# DP-516 — original IT/DE primary sources, private manifest (2026-10-26)

Manifest: [config/dp516-live-it-de-manifest.v1.json](../../config/dp516-live-it-de-manifest.v1.json).
Scope: private canonical **metadata**, two verified public figures, two independent
official source families, original IT and DE. No source bodies are stored by
this tranche. The hashes below describe the original HTTP response bytes as
observed on the Studio at 2026-10-26 17:38 UTC; they are **version fences**,
not evidence of a durable archived copy.

| Language | Person, original primary item | Pinned SHA-256 of observed representation |
|---|---|---|
| IT | [Matteo Piantedosi, Ministero dell'Interno, 17 Sep 2026](https://www.interno.gov.it/it/stampa-e-comunicazione/comunicati-stampa/piantedosi-esprime-solidarieta-ministro-valditara) | `4bf12984f4f31a8cecf8a05bbe0be5d241adc264ed80bef01b0812efa3319974` |
| DE | [Olaf Scholz, Deutscher Bundestag, 20/19, 27 Feb 2022](https://dserver.bundestag.de/btp/20/20019.xml), `rede[@id='ID201900100']` | `d7730d8fc24570ca5311353bc7dfbad6e6f04f45708561761e8f6cd16bd9265e` |

The German original is the specific Scholz **speech node**, not the 25 other
speeches in the same XML. Its speaker and node ID were verified against the
actual primary XML on the Studio (26 speeches, one matching node). Original
dates have **day precision**, and are recorded as `published_on` metadata;
an unsupported publication hour is not synthesized. The content IDs are
computed with the repository's existing `research_discovery._url_content_id`.

## Rights and privacy assessment

- **IT:** [Ministero dell'Interno, official legal notice](https://www.interno.gov.it/it/note-legali)
  (observed terms SHA-256 `f072e9778fc8715fcaa203f6ebdfb2f29db9a047016318f4e6c00a5060f8ca09`)
  declares its own text and documents CC BY 4.0 unless otherwise specified,
  requiring attribution and the original URL. Its original statement is
  explicitly attributed to the serving minister, a public figure. The terms
  support reuse of this original text and attributed adaptations subject to
  page-specific restrictions, privacy review and proper attribution.
- **DE:** [Bundestag official terms](https://www.bundestag.de/services/impressum)
  (observed SHA-256 `e3d6b1cd2944010869a949476d9f6c19d22f77157ff90f2cfe6f10a26b341183`)
  identify plenary transcripts as official works under UrhG §5 while
  requiring citation under §63, restricting modifications under §62 and
  warning of third-party rights. For the **original unaltered selected
  speech** this supports bounded original-document access; DE translation
  stays HOLD pending modification and derivative-use review. Photos,
  videos, other speakers and unrelated rights are outside this finding.
- Source legal allowances for FETCH, STORE_BODY, PARSE_TEXT,
  RESEARCH_CAPTURE_PRIVATE, translation, quotation and retention are stated
  **individually** in the JSON. They are analyses of the official source
  terms, **not** installed operational permissions.
- Privacy: the selected original communications concern publicly delivered
  ministerial/parliamentary statements by named public figures. Private
  biographical profiling, incidental third parties, sensitive facts, and
  unselected XML speeches remain excluded from any future capture or quote.

Review provenance: `agent:gpt-6-dp516-primary-source-research-20261026`
examined the two official sources and terms; the already installed
`private-rights-registry-current-leaf` enforces current leaf, rights,
expiry and revocation. **There was no second independent agent review** in
this session. That control has not been represented as fulfilled.

Accordingly both installed append-only `private_source_rights_record`
leaves have `rights_status=UNKNOWN`, **zero permitted uses**, reviewer
`agent:gpt-6-primary-source-20261026`, expiry
`2026-11-02T17:38:35Z`, and distinct official-terms receipts. Their IDs:

- IT: `private-rights:90400cd2dd960156d376355ce4034ba57717ab53f840de7a2443b6ccc18078d7`
- DE: `private-rights:2157d24ea4849f6e3d93a90358c199978b263cb0f082b06985f5b61c97a08f19`

The source/content registry entries likewise use `UNKNOWN` and
`REVIEW_REQUIRED`; source version drift, expiry, supersession and missing
independent review must continue to HOLD. A future agent's positive decision
requires new current source bytes, scoped privacy/legal and attribution
checks and an append-only superseding rights record. This manifest
**never** authorizes body capture, translation dispatch, public quotation,
GO-PUBLIC or historical scaling by itself.

## Actual private MiniPC PostgreSQL readback

2026-10-26 18:44:15 Europe/Rome, `dichiarazioni_pubbliche`, exit 0,
`BEGIN READ ONLY`/ `COMMIT`: total person=4, source=21,
content_item=56, rights=12; language it=55, de=1. This tranche contributed
**two** people, **two** sources, **two** Content metadata rows and **two**
private rights leaves. No Capture, Passage, Statement, batch or provider
request was created by this tranche.

Reproduce the inventory without reading private bodies:

```sql
BEGIN READ ONLY;
SELECT c.id, p.id AS person_id, s.id AS source_id,
       s.metadata->>'source_family' AS family, c.language,
       c.metadata->>'published_on' AS original_date,
       c.content_sha256, c.canonical_url
FROM content_item c
JOIN person p ON p.id = c.metadata->>'person_id' AND p.is_public_figure
JOIN source s ON s.id = c.source_id
WHERE c.metadata->>'dp516_manifest' =
      'dp516-live-it-de-original-primary-20261026'
ORDER BY c.language;
SELECT r.id, r.source_family, r.rights_status,
       cardinality(r.permitted_uses), r.expires_at
FROM private_source_rights_record r
JOIN content_item c ON c.id = r.content_id
WHERE c.metadata->>'dp516_manifest' =
      'dp516-live-it-de-original-primary-20261026'
AND NOT EXISTS (SELECT 1 FROM private_source_rights_record newer
                WHERE newer.supersedes_id = r.id);
COMMIT;
```

The two resulting `content_item` URLs and exact SHA-256 are in the JSON;
no private text is included in this repo or in the issue. For readback,
compare the observed representation to a fresh `curl -fsSL ... | shasum -a 256`;
any mismatch needs a new version and fresh rights adjudication.

## Follow-through (HOLD)

There is still no demonstrated autonomous two-model rights/statement pilot GO,
no production `dp516_pg_batch`/`dp516_pg_version` journal and no authorized
historical batch. The previously closed #478 carried those conditional
requirements into #474. Installing metadata cannot silently satisfy a
durable crash/resume, subscription-quota or publication acceptance; continue
this product work through the existing #352 (DP-516 parent) and #98 (rehearsal)
when an independently approved scoped pilot actually exists.
