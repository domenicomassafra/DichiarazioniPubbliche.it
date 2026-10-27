# DP-518A — MiniPC immutable release / current pointer

This is a **private DRAFT deployment mechanism**, not publication authority.
The release manifest inventories the actual mirrored Python runtime, database schema file, projection,
search index and every static asset. The `release_id` is SHA-256 of canonical
manifest material; its `manifest_sha256` is the SHA-256 of the stored manifest
file. The source Git commit is an *asserted source reference*: `code_sha256`
and per-file hashes independently record the MiniPC mirror bytes, including
any drift from that Git reference. Do not confuse these two statements.

## Source / consumer boundaries

- Authoritative Git: `domenicomassafra/DichiarazioniPubbliche.it` `main`.
- MiniPC's existing `/home/udodo/src/DichiarazioniPubbliche.it` is a non-Git
  mirror. Its source files are never overwritten or deleted by this operation.
- Existing private projection is
  `/home/udodo/.local/share/dichiarazioni-pubbliche/public/v1/`.
- New release authority lives at
  `/home/udodo/.local/share/dichiarazioni-pubbliche/host-release/`, with
  `releases/<sha256>/` and an atomic `current -> releases/<sha256>` symlink.
- The existing `dichiarazioni-pubbliche-web.service` is switched once to the
  versioned unit in `deploy/systemd/`. The current symlink is never a writable
  source checkout. The service reads `current/code/poc`, `current/static`, and
  `current/projection/index.json` together; the existing static root guard
  returns `404` rather than old `200` on a pointer rotation.

## Dry run: real MiniPC source/projection, isolated HTTP origin

From the MiniPC mirror, after installing the reviewed tool:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=poc python3 tools/dp481_minipc_release.py \
  rehearse --source /home/udodo/src/DichiarazioniPubbliche.it \
  --static /home/udodo/src/DichiarazioniPubbliche.it/web/dist \
  --projection /home/udodo/.local/share/dichiarazioni-pubbliche/public/v1 \
  --git-sha "$PINNED_MAIN_SHA" --rights-epoch-ref PRIVATE_DRAFT_NO_GO
```

This creates two candidate versions in a disposable private temporary tree,
verifies GET bytes from a real loopback HTTP listener, rejects a stale CAS,
rotates the symlink, requires the pinned stale listener to return 404, starts a
new listener to verify all static assets and complete API bundle, and proves
safe restoration after a deliberately unsafe candidate pointer replay. No
live unit, database, user mirror or external endpoint is changed.

## First install (after review and green CI)

Obtain the exact canonical `main` SHA using `git ls-remote origin refs/heads/main`
on Mac Studio. Transfer only the reviewed code and unit through the normal
candidate → verification → switch → rollback process; verify the code's hashes
against the reviewed commit before activation. On MiniPC:

```bash
export DP481_ROOT=/home/udodo/.local/share/dichiarazioni-pubbliche/host-release
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=poc python3 tools/dp481_minipc_release.py \
  --root "$DP481_ROOT" stage \
  --source /home/udodo/src/DichiarazioniPubbliche.it \
  --static /home/udodo/src/DichiarazioniPubbliche.it/web/dist \
  --projection /home/udodo/.local/share/dichiarazioni-pubbliche/public/v1 \
  --git-sha "$PINNED_MAIN_SHA" --rights-epoch-ref PRIVATE_DRAFT_NO_GO
```

Capture the returned `release_id`. The first candidate may only be selected
when there is no `current` yet. Validate its immutable manifest before the
switch; ensure the DRAFT projection is not substituted with demo or live data.
Keep the previously installed user unit as a private, same-host rollback input.
Install the reviewed systemd unit from the mirror, then:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=poc python3 tools/dp481_minipc_release.py \
  --root "$DP481_ROOT" activate --release-id "$NEW_RELEASE" --expect-current none
systemctl --user daemon-reload
systemctl --user restart dichiarazioni-pubbliche-web.service
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=poc python3 tools/dp481_minipc_release.py \
  --root "$DP481_ROOT" verify --origin http://127.0.0.1:18090
```

The last command exits nonzero on a mismatched pointer, a tampered/missing
manifest or asset, any static GET returning other bytes/status, any API bundle
field/HTTP byte drift, or a projection fingerprint mismatch. Its output includes the
release ID, current target, full code/schema/rights/projection/index/generation
pins, API response SHA-256, every asset SHA-256, and the exact manifest SHA-256. Store its private
output in the issue report; it is not permission to GO-PUBLIC.

## Subsequent versions / rollback

Stage and verify the *new* release first. With the current ID read back from
`verify`, atomically switch using `activate --release-id "$NEXT" \
--expect-current "$CURRENT"`. The compare-and-swap rejects an unexpected
pointer, and the read-only content-addressed release cannot be overwritten.
Restart the user unit immediately after changing the pointer, then run HTTP
`verify` again. Until restarted, the old listener refuses to serve pinned
withdrawn static bytes. On failed post-switch HTTP verification, switch only
to a previously verified **known-safe** release with a fresh CAS, restart, and
reverify the entire HTTP origin. Never roll back to a generation containing
revoked content. Preserve historic manifests and private legal/evidence state.

If recovery requires the previous unversioned unit, stop/revert only the web
unit and restore its exact prior file, then daemon-reload/restart and check
both `/api/v1/health` and static readback. This step requires the same live
candidate validation as the forward switch and cannot establish manifest
provenance for that pre-manifest unit.
