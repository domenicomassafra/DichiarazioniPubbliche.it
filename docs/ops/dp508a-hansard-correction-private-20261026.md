# DP-508A — authentic correction candidate for private intake (2026-10-26)

**Disposition: HOLD — source verified, no authorized DP intake record.**
This is a source-linked candidate dossier, not a persisted RightOfReply receipt,
private rights clearance, approval, or invitation to submit on behalf of anyone.
Its stable dossier locator is `dp508a:hansard-commons:2026-03-11:80d335e7`.
No personal request payload, login, capture body or credential is included.

## Original and correction provenance

- **Official publisher:** UK Parliament, House of Commons, Hansard, Written
  Corrections, **11 March 2026**, Social Cohesion Action Plan, Housing,
  Communities and Local Government.
- **Canonical source:** https://hansard.parliament.uk/commons/2026-03-11/debates/80d335e7-4f3b-4a67-97ca-8cadea3a9246/WrittenCorrections
- **Immutable locator component:** debate GUID
  `80d335e7-4f3b-4a67-97ca-8cadea3a9246`. This is a durable item
  identifier, *not* a byte-level Capture or proof of immutable HTML.
- **Original version reference:** Official Report, **9 March 2026**,
  Volume **782**, column **80**; official Hansard identifies a ministerial
  statement about the Pride in Place programme.
- **Correction event:** official written correction submitted by **Steve Reed**,
  Secretary of State for Housing, Communities and Local Government, published
  **11 March 2026**. The substantive correction changes the description of
  almost 300 funded units from **constituencies** to **areas**.
- **Kind:** `CORRECTION` of a documented public statement, *not* a
  right-of-reply request sent to DichiarazioniPubbliche.it. The source
  itself attributes the correction to its submitter; it does not authorize
  this project to impersonate that submitter.
- **Observed:** 2026-10-26, official Hansard HTML opened via indexed
  web access and matched against the original-volume/column reference.
  On Mac Studio, direct `curl -sSL` to the canonical URL returned
  **HTTP 403** (5,732 bytes of access-denial material); therefore there is
  **no valid source-body SHA-256** or local Capture. Hashing that response
  as Hansard evidence would be misleading.

## Source-specific rights and privacy review

- **Publisher copyright terms, accessed 2026-10-26:**
  https://www.parliament.uk/site-information/copyright/ and
  https://www.parliament.uk/site-information/copyright/open-parliament-licence/
  — **Open Parliament Licence v3.0** (Parliamentary copyright);
  permits reuse of licensed parliamentary *text* with attribution,
  including: "Contains Parliamentary information licensed under the Open
  Parliament Licence v3.0." The licence excludes personal data, third-party
  rights and audio/video material; source authenticity does not extend
  licensing to those categories. Licence URL returned HTTP 403 from Mac
  Studio, but its published text was independently read through web access.
- **Private proposed purpose:** inspect provenance and rights for a real
  public-office correction, without publishing or creating a new claim.
  Only public office identity, dates, citation, URL, GUID, and changed
  *non-personal funding unit term* are recorded in this dossier.
  No contact details, raw intake body, device/IP identifier or sensitive
  third-party information are retained.
- **Personal-data ground:** no consent or direct request from the
  minister to this product is evidenced. GDPR Regulation (EU) 2016/679,
  Articles 5, 6 and 17, and EDPB Guidelines 1/2024 for Article 6(1)(f)
  require purpose limitation, necessity, balancing of rights and
  demonstrable retention/erasure safeguards. Public status alone is
  insufficient. Relevant official references:
  https://eur-lex.europa.eu/eli/reg/2016/679/oj and
  https://www.edpb.europa.eu/documents/guideline/guidelines-12024-on-processing-of-personal-data-based-on-article-61f-gdpr_en .
  **Disposition:** the minimum public bibliographic locator can be reviewed
  as candidate metadata; clearance for personal intake processing and
  submission has **not** been established.
- **Retention/expiry/revocation:** no private body exists to retain or
  purge. This dossier contains only the public reference and a HOLD reason.
  There is **no adopted numeric TTL** for a future private request.
  Before any actual receipt, record an approved privacy purpose and expiry;
  use the existing `rights_registry.PrivateRightsRegistry` private,
  current-version/supersession mechanism and
  `reply_governance` append-only retention events and
  `purge_unpublished_reply` when eligible. On expired/revoked rights,
  disputed identity, or a withdrawn source: reject processing, hold
  publication and apply the existing revocation/deletion controls.

## Private intake readback and release boundary

- **Existing intake seam:** `submit_right_of_reply` requires a real
  `finding_id`, an authentic submission, enabled launch profile, current
  rate decision, and private store. The live reader has no published Finding
  for this correction; the Hansard notice is not a submission addressed to
  the service. There is no lawful intake request to insert.
- **Registry result:** `private_source_rights_record` for this candidate
  is **NOT CREATED**, `right_of_reply` is **NOT CREATED**, and no
  `RECEIVED_PRIVATE` receipt ID can be claimed. The dossier locator above
  is *not* a DB identifier. No invented grant, consent, submitter or
  reviewed_at timestamp is supplied.
- **Reproducible read-only source check on Mac Studio** (2026-10-26):
  ```sh
  curl -sSL --max-time 18 -o /dev/null -w "status=%{http_code}\n" "https://hansard.parliament.uk/commons/2026-03-11/debates/80d335e7-4f3b-4a67-97ca-8cadea3a9246/WrittenCorrections"
  ```
  Observed `status=403`; this is a HOLD, not a source-body Capture.
  Independently inspect the official Hansard and Open Parliament Licence
  links again before any future processing.
- **Real MiniPC readback, 2026-10-26:** service
  `dichiarazioni-pubbliche-web.service` = `active`;
  `GET http://127.0.0.1:18090/api/v1/health` = `status:ok`,
  `dossier_count:0`, `contract_status:DRAFT`;
  `POST http://127.0.0.1:18090/api/v1/intake` = `HTTP 405`.
  No application mutation or public endpoint activation was performed.
- **Acceptance decision:** `HOLD: NO_AUTHENTIC_DP_SUBMISSION`,
  `HOLD: FINDING_ID_MISSING`,
  `HOLD: INTAKE_LEGAL_BASIS_AND_RETENTION_NOT_CLEARED`,
  `HOLD: DIRECT_SOURCE_CAPTURE_HTTP_403`.
  Do not convert this into a positive intake acceptance merely because
  the underlying Parliamentary correction is authentic.
  [#479](https://github.com/domenicomassafra/DichiarazioniPubbliche.it/issues/479)
  is already **CLOSED** (26 Oct 2026); do not reopen it or create
  a standalone canary. If a real private submission later becomes eligible,
  the active product launch work can link only its verified private receipt
  identifier back to #476.

This satisfies the explicitly permitted **fail-closed HOLD** outcome in
[#476](https://github.com/domenicomassafra/DichiarazioniPubbliche.it/issues/476)
without manufacturing a submission or public endpoint activity.
