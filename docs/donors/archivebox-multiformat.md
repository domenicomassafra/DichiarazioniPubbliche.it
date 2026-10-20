# ArchiveBox multiformat canary — issue #162

## Donor, license, dependency

Use the whole upstream ArchiveBox as a **separate private MiniPC service**, via its
documented CLI/API and existing ArchiveAdapter seam; do not vendor Django or
the upstream application. The HTML/readability opt-in adapter from **PR #198
(issue #171)** was merged into main on 2026-10-20 (`dae5ea1`), but its real
MiniPC donor canary and source-use approval remain on HOLD. This ticket
assesses WARC/PDF/metadata preservation, process limits, rollback and comparison with
the existing Monolith path; it must not activate or modify #171.

- Upstream: https://github.com/ArchiveBox/ArchiveBox ; release v0.9.73
  published 2026-10-06; tag commit
  6f5d2f60a01a7ca1171d3b3ddac3310d13c47fab.
- License: MIT, https://github.com/ArchiveBox/ArchiveBox/blob/v0.9.73/LICENSE .
  Preserve the copyright/permission notice. Separately inventory resolved
  browser, extractor, image-layer and optional-model licenses before deployment,
  and send any LGPL/MPL/GPL/AGPL dependency for explicit review.
- Pinned upstream wheel archivebox-0.9.73-py3-none-any.whl:
  sha256 2b4a4be06420cbe0f6991bc18d45df62f324c84f2f652c2cb056a2be3a3ca117;
  source tarball: sha256 bb9c7b72565ff27a1f4da4ed67731db3124faceaf975e22a67b7f13e4a22ea98.
  A Docker tag alone is insufficient: pin and report the *verified local image
  digest* at provisioning time, plus the effective CLI/API version and plugins.
- Alternative: https://github.com/Y2Z/monolith (CC0-1.0), already integrated
  privately as capture_monolith_adapter.py. It processes an approved HTML body
  through stdin, but does not provide WARC/PDF/multiformat preservation. Real
  ArchiveBox overhead and benefit remain unmeasured.

## Implemented offline audit

poc/dichiarazioni_pubbliche/archivebox_multiformat_audit.py only reads existing
private artifacts and a structured canary manifest. It performs no network
access, image pull, service launch, archiving, or publication. It checks WARC
(plain/gzip) and PDF file signatures, SHA-256 and sizes, metadata provenance,
private directory/file permissions and symlink escapes, release and immutable
image identification, recorded rights decision fingerprint, archive HOLD and
absence of public locators in both receipt and metadata, resource bounds, Monolith baseline numbers, and a hashed rollback log.
For gzip WARC, the entire compressed stream is checked (CRC/trailer included)
with a 32 MiB limit on uncompressed data; truncated or over-expanded streams
fail closed. This still does not parse WARC record semantics.

With an *already approved and completed* canary, run:

~~~sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=poc \
  python3 -m dichiarazioni_pubbliche.archivebox_multiformat_audit \
  --private-root /path/to/private-canary \
  --manifest /path/to/private-canary/manifest.json
~~~

The schema is archivebox-multiformat-canary-v1. Manifest JSON must be mode
0600 beneath the 0700 private root (duplicate keys are rejected).
Required sections:

1. donor: tag=v0.9.73, exact commit, license=MIT, and a
   repository:tag@sha256:<64 lowercase hex> immutable image reference.
2. source: kind=SYNTHETIC_HTTPS, original_url_sha256, capture_sha256,
   rights_decision_sha256, and approved_uses exactly
   FETCH/STORE_BODY/PARSE_TEXT/ARCHIVE.
3. receipt: UUID crawl_id/snapshot_id, matching source_capture_sha256 and
   original_url_sha256, retention=PRIVATE, publication_state=HOLD;
   no archive_url or public_locator.
4. artifacts: exactly three entries kind=WARC/PDF/METADATA with relative path,
   sha256, bytes. Files must be 0600, parent folders 0700, each <=32 MiB.
   Metadata JSON repeats crawl_id, snapshot_id, source_capture_sha256 and HOLD,
   and must contain neither archive_url nor public_locator.
5. metrics: measured positive peak_rss_kib, duration_ms, disk_bytes, and
   explicitly chosen max_rss_kib, max_duration_ms, max_disk_bytes. Exceeding
   any limit, or counting fewer disk bytes than artifacts, fails.
6. monolith: positive measured peak_rss_kib, duration_ms, disk_bytes for the
   same controlled source in the MiniPC environment.
7. rollback: service_stopped=true, private_artifacts_preserved=true,
   run_log_path, run_log_bytes, run_log_sha256. The auditor rehashes the file.

The unit tests use synthetic format-header bytes and fake IDs, and deliberately
do **not** attest an actual ArchiveBox run. PASS means only offline integrity
of the supplied artifact set; WARC/PDF are not fully semantically parsed.
The rights decision fingerprint is not itself a signed permit: the current
source-use record must be checked by the real pipeline. Likewise, a manifest
cannot prove a service was stopped without an operator's independent readback.

## Owner-controlled real canary — HOLD

No ArchiveBox binary/container was installed on the MiniPC at the previous
inspection. #171 remains OPEN / needs-owner with runtime source-use HOLD even
though its HTML/readability source PR #198 is MERGED. **Before activation**,
the owner must approve an exact *owner-controlled synthetic HTTPS origin*, an operative
source-family permit for FETCH, STORE_BODY, PARSE_TEXT, ARCHIVE on that capture,
private retention and network policy, and a one-time isolated ArchiveBox
service/canary. Do not archive third-party sources, invoke paid inference,
run bulk collection, change production, or publish any archive.

After that approval, the operator should:

1. Resolve the v0.9.73 upstream release SHA and third-party license inventory;
   inspect immutable image digest, ArchiveBox CLI version and available WARC/PDF
   plugin names with the *actual* v0.9.73 distribution. If unsupported, record
   UNSUPPORTED rather than simulate WARC/PDF output.
2. Provision a disposable collection and process separate from production
   storage/DB, with private files and a rollback strategy. Limit one URL, depth
   zero, bounded size/time/CPU/RSS/disk/concurrency, and only the explicitly
   required plugins. Deny metadata/internal/private outbound IPs, DNS rebinding,
   disallowed redirects, remote media and uploads; allow only the approved
   synthetic HTTPS host.
3. Confirm real source-use FETCH/STORE_BODY/PARSE_TEXT/ARCHIVE decisions and
   original URL/body SHA, run exactly one authorized ArchiveBox request and
   record crawl/snapshot IDs, original-vs-snapshot hashes, all saved outputs,
   failure codes, idempotent retry, privacy and retention. Recheck ARCHIVE after
   the process. Never emit a public archive URL.
4. Collect real measurements for ArchiveBox and the same approved HTML input
   through existing Monolith: time, peak RSS, CPU, bytes, error/failure, artifact
   completeness. Freeze resource budgets *before* execution and retain run log.
   Stop/rollback the isolated service, verify rollback, preserve private receipts.
5. Write the versioned manifest using **observed** results, run the offline
   audit, verify unchanged public projection, attach a redacted proof to #162,
   and assess whether the additional preservation is worth its overhead.
   Missing output, rights or proof remains HOLD rather than a fake success.

Enabling the already merged HTML/readability adapter and adding multiformat
capture in production both depend on independently authorized runtime evidence;
#171 still requires its live source-use canary and #162 requires WARC/PDF proof.
