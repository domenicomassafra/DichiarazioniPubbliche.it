# Private ArchiveBox WARC/PDF/METADATA canary — 2026-10-25

This receipt follows the [ArchiveBox donor decision and 2026-10-23 baseline](../donors/archivebox-multiformat.md).
The #358 owner authorized the isolated synthetic canary; this file records the actual 2026-10-25 execution.


**Result: PASS for the private isolated canary**, verified against real output
and the existing `archivebox_multiformat_audit.py` offline validator. This is
not permission to turn on public archival or deploy ArchiveBox permanently.
The only source was the owner-authorized synthetic HTTPS fixture
`https://dp162-canary.test/fixture.html`, URL SHA-256
`bba0d4576f1a9332eb89bb7f7291fa2e69ee2c2a9dd2e65499f84af7a25a56cc`,
body SHA-256 `a45de00f327e7894c00fb95f0ef54cc68b664d0879a04834487388c390be9235`.
Source-use rights were `FETCH,STORE_BODY,PARSE_TEXT,ARCHIVE`, with the original
owner approval fingerprint `1aeac182dbfd73da053c3d6a97dc34539272f172e37ece7082da35dcadebcbc9`.

- **Pinned donor and added browser.** The image was re-pulled at immutable
  `sha256:6478ae1e030db1478858a7c8bb5967b2f6c198cd74cea70b9a74e24ee7ee3e4c`
  and reports ArchiveBox **0.9.73**. Its Debian 13 runtime includes Node
  **24.18.0**, `abxbus` **2.5.74**, `@puppeteer/browsers` **3.0.4**,
  GNU Wget **1.25.0** and Poppler `pdftoppm` **25.03.0**
  (`poppler-utils 25.03.0-5+deb13u4`). The bundled Chrome for Testing
  **153.0.8010.12** is below the plugin's required **153.0.8010.36**;
  the same installed Puppeteer CLI fetched Chrome for Testing
  **156.0.8078.47** to the disposable canary directory. Its executable
  SHA-256 was `230f0db8c5086182f46c59c867c0d461eb525d6552dfad226ea6b4d9ec249db2`.
  The frozen `CHROME_BINARY` path was explicitly accepted by ArchiveBox's
  `install:` checks; no donor source was forked or patched.
- **Licensing and rights readback.** ArchiveBox's
  [MIT license](https://github.com/ArchiveBox/ArchiveBox), Node's
  [MIT license and bundled notices](https://github.com/nodejs/node/blob/v24.18.0/LICENSE),
  Puppeteer's [Apache-2.0 license](https://github.com/puppeteer/puppeteer),
  [Chrome browser terms](https://www.google.com/chrome/terms/), Poppler's
  [upstream releases](https://poppler.freedesktop.org/releases/) and
  [Debian's exact source package](https://sources.debian.org/src/poppler/25.03.0-5%2Bdeb13u4/)
  and [GNU Wget](https://www.gnu.org/software/wget/) were checked with the
  pinned versions. Poppler and Wget carry GPL terms; Chrome has its own
  distribution terms. The granted **private, non-distributed** synthetic use
  is compatible with the reviewed terms; shipping an image or browser bundle
  would trigger further copyright, notice and corresponding-source duties.
  Those distributions and public publication remain out of scope.
- **Network and TLS containment.** The disposable Docker network
  `dp358-isolated-qaongglq` was `--internal` on `172.31.162.0/24`, with
  fixture only at `172.31.162.2`, a one-day self-signed TLS certificate and
  crawler-only `--add-host`. An independent `curl --cacert` preflight
  returned HTTP 200 and the exact body hash above. Wget needed the
  explicit `WGET_ARGS_EXTRA=["--ca-certificate=/tls/canary.crt"]`; without
  it, its first TLS handshake failed with exit 5. Chromium used
  `CHROME_CHECK_SSL_VALIDITY=false` **only within this egress-isolated
  synthetic network**. Production must use normal certificate validation.
  Each crawl used depth 0, maximum one URL, 64 MiB crawl output ceiling,
  16 MiB per snapshot, one concurrent snapshot, a 150-second crawl timeout,
  and a 180-second container watchdog with 2 GiB/2 CPU limits.
- **Privacy is enforced at the API seam.** Initial CLI canaries successfully
  generated a WARC and PDF, but persisted `PERMISSIONS=public` even with
  `PERMISSIONS=private` in the environment and `archivebox config --set`.
  These **failed privacy acceptance** (no ArchiveBox web server was opened).
  Using the official `archivebox.cli.archivebox_add.add(...)` Python API with
  `config={"ONLY_NEW": False, "PERMISSIONS": "private"}`—the same mechanism
  as the already merged `capture_archivebox_adapter.py`—produced persisted
  `crawl.permissions=private` and `snapshot.permissions=private`, both `sealed`.
  Do not replace that API call with a bare CLI `archivebox add`.
- **Final authentic receipt.** Crawl `06ade23bad3073318000a88774649149`,
  snapshot `06ade23bd8da7e39800029f3749aa330`, URL equality and source body
  SHA-256 above. Both `on_Snapshot__35_wget.finite.bg` and
  `on_Snapshot__52_pdf` returned `succeeded`. The six-record WARC was
  `3021 B`, SHA-256
  `4c66e72b8eddd8679c41ecb38249149d1736a54a607b14f139c847c29884f498`;
  it passed full gzip decompression and CRC/trailer verification. The
  one-page `%PDF-1.4` file was `9758 B`, SHA-256
  `907b32ca0356d21fcda7481ff308ca0aaae5ed8b0edda96edee946423b728816`;
  its extracted text matches the original fixture. The separate provenance
  metadata (`crawl_id`, `snapshot_id`, both source hashes,
  `publication_state=HOLD`, private permissions and extractor statuses) was
  `511 B`, SHA-256
  `6aa37c2d62c41e5f2c86cf510029ad69efac6e8aec0bde7638860cae09644ffd`.
  No public URL/locator was generated.
- **Measured cost versus Monolith.** The final run exited `0` on the MiniPC
  (`15:43:52.789631556Z` to `15:44:10.050881144Z`): **17,262 ms**.
  Eight `docker stats` samples yielded a **sampled maximum of 563.2 MiB**
  (576,717 KiB rounded up; not a kernel-observed absolute peak), below
  the 2 GiB cap. The collection **including earlier failed attempts** and
  private audit evidence used **1,814,355 B**, below 64 MiB. Final WARC,
  PDF and metadata together use **13,290 B**. The previous Monolith 2.11.6
  run on the *same synthetic fixture* was 630 ms, 6,728 KiB sampled RSS,
  and 338 B output; the successful ArchiveBox canary is approximately
  **27x slower, 86x higher sampled RSS, and 39x more artifact bytes**,
  in exchange for WARC and PDF retention. Keep this optional; the earlier
  WARC-only, failed-TLS and public-permission attempts are explicitly excluded
  from the final receipt.
- **Offline audit and rollback.** A private directory (mode `0700`) held
  exactly three independent artifact copies and an audit manifest/log
  (each mode `0600`, one link, no symlink). The checked-in validator returned
  `PASS: private WARC/PDF/metadata sha256 audit, 3 artifacts, 13290 bytes`.
  The measured run log SHA-256 was
  `d81e65a124171e28f18e2e0b182b344221fd92c08fbf83545d05343dece31b87`.
  The crawler and fixture containers and the Docker network were removed;
  `docker ps -a --filter name=dp358` and `docker network ls --filter name=dp358`
  returned no entries. The unaffected
  `dichiarazioni-pubbliche-web.service` remained `active`, and
  `/api/v1/health` still returned `status=ok`, `contract_status=DRAFT`,
  `dossier_count=0`. After the successful offline audit, all temporary
  archives, browser binaries, metadata copies, private logs, manifests,
  fixture keys and source files under the dedicated scratch directory were
  purged, with `test ! -e` confirming removal **within the same session**.
  Only the redacted hashes and measurements in this document remain.
- **Operational warning.** ArchiveBox marked the Chrome launch **cleanup
  hook** as failed (`chrome cleanup did not fully stop the browser process
  tree`) even though both extractors, the capture and the container exit
  succeeded. The Docker container removal and zero remaining canary
  resources are independently verified; do not treat the hook warning as a
  clean internal browser shutdown. Permanent installation needs a separate
  authorization and proper TLS/cleanup hardening.
