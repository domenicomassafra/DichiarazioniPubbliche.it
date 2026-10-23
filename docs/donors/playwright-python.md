# Playwright Python — optional private BrowserRenderer (#170)

- Upstream: https://github.com/microsoft/playwright-python
- Release: [v1.64.0](https://github.com/microsoft/playwright-python/releases/tag/v1.64.0), published 2026-10-13.
- Exact upstream tag commit: `387a8a943bb397962f19085c376a301b440029b6` (`git ls-remote ... refs/tags/v1.64.0`).
- License: Apache-2.0; retain the installed distribution's original license and notices. No upstream source is copied.
- Adopted via optional Python package pin `playwright==1.64.0` and its synchronous Chromium API.
- Browser binary: a separately installed `/usr/bin/` or `/opt/` Chromium executable; record its `browser.version` with each rendition. Chromium distribution licenses remain its distributor's responsibility.
- Rationale: the existing safe HTTP capture cannot execute client-side JS; native Playwright supplies Chromium sessions, network interception and deterministic DOM extraction. Project code implements only rights gating, a Linux network namespace, strict HTTPS/DNS checks, resource budgets, and rendition receipts.

The adapter is opt-in and requires Linux bubblewrap for browser process isolation.
The `browser_renderer_netns.sh` wrapper now constructs a fresh `--tmpfs /`
root and read-only binds only `/usr/bin`, `/usr/lib`, optional `/usr/lib64`,
selected font assets/config and, if the browser resolves below `/opt`, only
its resolved binary's own directory. `/etc/passwd`, `/etc/shadow`, `/etc/ssh`,
`/usr/local`, `/home`, `/root`, `/var/log` and the host's `/run` are never
mounted; `/tmp`, `/run`, `/dev` and `/proc` belong to the isolated process.
`bwrap` additionally isolates network, PID, IPC and UTS and clears the parent
environment. A real-wrapper MiniPC regression executes `/usr/bin/sh` in the
sandbox to prove host-path denial, namespace separation, environment clearing
and bounded launch time. The old `--ro-bind / /` implementation failed on the
same test because `/etc/passwd` was readable.

On the MiniPC, Chrome sandbox ON was previously blocked by nested
user-namespace/AppArmor restrictions; `--no-sandbox` is never configured by
the adapter. On Omarchy, the real Chromium 155 browser successfully rendered
the Playwright TodoMVC demo with sandbox ON, `bwrap --unshare-net`, an explicit
source-use approval predating the fetch, and a private hash receipt. See
`docs/evidence/dp170/` for the dated command and result. This demonstrates
the isolated renderer on that Linux host; consumer installation on the MiniPC
remains pending its own host-specific sandbox and source-use checks.
The browser runs without access to the user's home or host network. An isolated
fresh context has no persistent cookie/login profile. The Linux sandbox
masks /run and its /var/run symlink, hiding host user-session AF_UNIX sockets
such as D-Bus. The parent Python transport
fulfills every HTTPS request with `source_watcher.fetch_bytes`, which validates
all DNS answers and pins the connected socket through redirects. WebSockets are
blocked. HTTP redirects for both documents and subresources are refused,
including same-host redirects: Playwright route.fulfill would otherwise hide
the actual fetched URL and undermine rights/provenance validation.
The renderer passes allow_redirects=False to source_watcher.fetch_bytes
before issuing the HTTP request; checking final_url only after a 3xx would
allow an unapproved second GET before the browser route refuses it.
An isolated synthetic transport regression asserts no second GET occurs.
Installing the optional extra does not enable rendering. Runtime activation
remains blocked until the consumer has a reviewed source-use decision, an
explicit host allowlist, an approved network limit, and a recorded browser
binary/version; production never inherits the isolated canary's permission.
