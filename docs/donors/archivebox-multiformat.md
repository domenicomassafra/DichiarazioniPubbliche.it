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
- Transitive inventory checkpoint (MiniPC, 2026-10-22):
  `printf 'archivebox==0.9.73\n' | uv pip compile --python-version 3.13 --no-header --no-annotate --no-emit-index-url -o /tmp/dp162-license-resolve-20261022.txt -`
  resolved **102** Python distributions without installation. Exact PyPI release
  metadata identifies
  [psycopg 3.3.6](https://pypi.org/pypi/psycopg/3.3.6/json) and
  [psycopg-binary 3.3.6](https://pypi.org/pypi/psycopg-binary/3.3.6/json)
  as `LGPL-3.0-only`,
  [browser-cookie3 0.20.1](https://pypi.org/pypi/browser-cookie3/0.20.1/json)
  as LGPL, and
  [certifi 2026.10.19](https://pypi.org/pypi/certifi/2026.10.19/json)
  as MPL-2.0. The ArchiveBox [wget WARC plugin](https://plugins.archivebox.io/)
  requires GNU Wget (MiniPC: v1.25.0), licensed under the
  [GNU GPL](https://www.gnu.org/software/wget/manual/html_node/Overview.html).
  Flagged to the owner in [#162](https://github.com/domenicomassafra/DichiarazioniPubbliche.it/issues/162#issuecomment-6327815867)
  before adoption. Preserve actual installed notices and inspect any
  image-layer/extractor changes before activating the runtime. No ArchiveBox
  distribution, image or extractor was installed by this inventory.
- Alternative: https://github.com/Y2Z/monolith (CC0-1.0), already integrated
  privately as capture_monolith_adapter.py. It processes an approved HTML body
  through stdin, but does not provide WARC/PDF/multiformat preservation. Real
  ArchiveBox overhead and benefit remain unmeasured.

## Implemented offline audit

poc/dichiarazioni_pubbliche/archivebox_multiformat_audit.py only reads existing
private artifacts and a structured canary manifest. It performs no network
access, image pull, service launch, archiving, or publication. It checks WARC
(plain/gzip) and PDF file signatures, SHA-256 and sizes, metadata provenance,
private directory/file permissions, symlink and hardlink escapes, release and immutable
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
0600 beneath the 0700 private root (duplicate keys are rejected); hardlinks
that could share manifest contents outside this root are rejected.
Required sections:

1. donor: tag=v0.9.73, exact commit, license=MIT, and a
   repository:tag@sha256:<64 lowercase hex> immutable image reference.
2. source: kind=SYNTHETIC_HTTPS, original_url_sha256, capture_sha256,
   rights_decision_sha256, and approved_uses exactly
   FETCH/STORE_BODY/PARSE_TEXT/ARCHIVE. This controlled v1 audit requires
   original_url_sha256 and capture_sha256 to equal the two exact synthetic
   fixture fingerprints below; a self-consistent manifest from another
   source is rejected. This pin does not prove a current rights decision
   or that the bytes served via HTTPS matched the checked-in fixture.
3. receipt: UUID crawl_id/snapshot_id, matching source_capture_sha256 and
   original_url_sha256, retention=PRIVATE, publication_state=HOLD;
   no archive_url or public_locator.
4. artifacts: exactly three entries kind=WARC/PDF/METADATA with relative path,
   sha256, bytes. Files must be 0600, parent folders 0700, each <=32 MiB.
   Metadata JSON repeats crawl_id, snapshot_id, source_capture_sha256 and HOLD,
   and must contain neither archive_url nor public_locator. If metadata supplies
   original_url_sha256, it must match the source/receipt URL fingerprint.
   Files with hardlinks outside the private retention boundary are rejected
   (including the rollback log); one inode must have exactly one link.
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

## Controlled HTTPS fixture and real canary — HOLD

The canary below was executed on 2026-10-23 after the owner's licensing
decision; see "Observed canary run" at the end of this document. At the earlier
inspection no ArchiveBox binary/container was installed on the MiniPC. #171 is CLOSED as of 2026-10-21 and its HTML/readability PR #198
is MERGED, but this does not prove a WARC/PDF runtime. The owner approved
a controlled test URL, permitted uses, and short retention on 2026-10-20:
[decision](https://github.com/domenicomassafra/DichiarazioniPubbliche.it/issues/162#issuecomment-6300421019).
The agent selected exactly **`https://dp162-canary.test/fixture.html`**, to be
resolved only inside a disposable, isolated HTTPS test network. The complete
synthetic, self-authored, link-free v1 HTML is
[`docs/donors/archivebox-canary-v1.html`](archivebox-canary-v1.html)
(188 bytes; SHA-256
`a45de00f327e7894c00fb95f0ef54cc68b664d0879a04834487388c390be9235`);
the URL SHA-256 is
`bba0d4576f1a9332eb89bb7f7291fa2e69ee2c2a9dd2e65499f84af7a25a56cc`.
Restrict `FETCH`, `STORE_BODY`, `PARSE_TEXT`, and `ARCHIVE` to this URL and
exact fixture version, private retention at most **24 hours** and publication
`HOLD`. The fixture and choice are **not** a live source-use authorization;
verify an operative decision bound to the served bytes and current URL before
any fetch or donor launch. Predeclare canary limits of 2 GiB peak RSS,
180 seconds, 64 MiB disk, one URL and depth zero; apply real OS/container
resource limits, count all children, and reject redirects or external media.
No `.test` hostname may resolve to a third-party endpoint. Freeze the effective
TLS trust chain, DNS answers and allowlist before the run, and stop if these
cannot be verified. Preserve the runtime package/extractor license decision,
notices, and immutable digest before installing. Do not archive third-party
sources, invoke paid inference, run bulk collection, change production, or
publish any archive.

After the license, live source-use and runtime controls have been verified,
the operator should:

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

The already merged HTML/readability seam is separate from the real WARC/PDF
acceptance of #162. A source-only audit or closed #171 ticket cannot substitute
for the observed private multiformat canary, rights/readback and rollback.

## Observed canary run — 2026-10-23 (owner decision A)

The owner approved, on 2026-10-23, adopting ArchiveBox v0.9.73 **only** for one
internal, private, isolated canary with the dependency list below
([approval](https://github.com/domenicomassafra/DichiarazioniPubbliche.it/issues/162#issuecomment-6359003313),
fingerprint `1aeac182dbfd73da053c3d6a97dc34539272f172e37ece7082da35dcadebcbc9`
= SHA-256 of that comment body). What follows is what was actually observed on
the MiniPC, and what stayed impossible.

- **Pinned runtime.** `docker pull archivebox/archivebox@sha256:6478ae1e030db1478858a7c8bb5967b2f6c198cd74cea70b9a74e24ee7ee3e4c`
  (linux/amd64 sub-manifest of the `0.9.73`/`latest` manifest list
  `sha256:d4720d86c0e91577bccaee59fa238d22a9cfc0674aa594c80f739f0738270af9`),
  4.32 GB, `archivebox --version` = 0.9.73.
- **Effective dependency inventory of the pulled image** (not of a
  hypothetical resolve): 103 Python distributions enumerated from their
  installed metadata. The pinned image has `psycopg 3.3.4` and
  `psycopg-binary 3.3.4` (LGPL-3.0-only), `browser-cookie3 0.20.1` (LGPL),
  and `certifi 2026.6.17` (MPL-2.0), rather than the Python resolver's
  projected `psycopg 3.3.6` / `certifi 2026.10.19`. The donor's `install:wget`
  step uses GNU Wget 1.25.0 (GPL). A subsequent review of the installed
  metadata also identified `zope.interface 8.5` (ZPL-2.1), `ujson 5.13.0`
  (BSD-3-Clause AND TCL) and `regex 2026.7.10` (Apache-2.0 AND CNRI-Python),
  absent from the owner's enumerated approval. These discrepancies are
  documented in the [pending owner question](https://github.com/domenicomassafra/DichiarazioniPubbliche.it/issues/162#issuecomment-6363334313).
  OS-layer and executable notices are still incomplete: do not interpret
  the WARC run as an approval for another run or for production.
- **Isolation.** Disposable bridge `172.31.162.0/24`; a fixture container
  served only `/fixture.html` over TLS with a canary-only CA;
  `dp162-canary.test` resolved to `172.31.162.2` **inside the crawler
  container only** (`--add-host`), so no host DNS change and no public egress
  for the crawl. Container limits `--memory 2g --cpus 2 --pids-limit 512`.
- **Observed run.** `archivebox init` then
  `archivebox add --depth=0 --max-urls=1 --crawl-max-concurrent-snapshots=1 --crawl-timeout=150 --snapshot-max-size=16mb --plugins wget --tag dp162-canary https://dp162-canary.test/fixture.html`
  exited 0; crawl `06adb3922bc87cfd800025380d708d06`, snapshot
  `06adb392def1775680005e8fe0070628`, archiver result
  `on_Snapshot__35_wget.finite.bg` = `succeeded`. Real outputs:
  `wget/warc/1792751918.warc.gz` 2988 B
  `sha256 06c7d19c53004a038b31d270bf80b3049eed67332f4a1786875450c863d69736`
  (plain stream 4201 B `df5eced112538cd2eb537176d219bab5796134aff9b0b1541c906042212b0918`,
  6 `WARC/1.0` records) and the saved body
  `sha256 a45de00f327e7894c00fb95f0ef54cc68b664d0879a04834487388c390be9235`,
  identical to the approved fixture.
- **PDF stayed UNSUPPORTED, not simulated.** The pinned image ships no
  Chrome/Chromium; `plugins/pdf/config.json` requires plugin `chrome`, whose
  `required_binaries` pull Node >= 22.12 (`apt nodejs`), a `pnpm` `abxbus`
  package and a `browsers` download, and `pdf` additionally needs
  `poppler-utils` for `pdftoppm`. Those components are outside the
  2026-10-23 license decision, so enabling them needs a new owner answer; a
  `--plugins pdf` probe archived 0 URLs and produced no PDF.
- **Measured cost.** ArchiveBox: 93.666 s (container `StartedAt`→`FinishedAt`),
  peak RSS 298 700 KiB (max of 2 s `docker stats` samples; `memory.peak` is
  not readable once the container exits), 875 058 B stored in the collection
  (snapshot folder 18 067 B). Monolith 2.11.6 on the same fetched bytes:
  6 728 KiB peak RSS, 0.63 s, 338 B output. So WARC+metadata cost roughly 44x
  the RSS and 149x the wall time of HTML-only preservation.
- **Rollback readback.** Containers removed, bridge network removed, no
  listener left on the canary network, transient collection deleted
  (retention <= 24 h), private receipts (`0600`) preserved and re-hashed.
- **Offline audit of the real artifact set** returned
  `BLOCKED: REQUIRED_ARTIFACTS_MISSING` because no PDF artifact exists — the
  fail-closed behaviour this ticket wants. The WARC path itself was verified
  against the real file (size, SHA-256, gzip magic, full-stream CRC/trailer,
  WARC records), not only against fixtures.
- **Donor default visibility.** ArchiveBox stored both the crawl and the
  snapshot with `permissions = public` (its UI-level default). No server was
  started and no locator was published, but any future use must force private
  permissions — another reason to keep publication `HOLD`.

Multiformat acceptance is therefore still open: the canary proved a real,
rights-bound WARC capture with measured cost inside an isolated
network, and proved that PDF preservation needs an explicit licensing and
provisioning decision for a headless browser. The additional image licensing
question above also remains unanswered; repeat neither capture nor provisioning
until the exact runtime inventory is cleared by the owner.
