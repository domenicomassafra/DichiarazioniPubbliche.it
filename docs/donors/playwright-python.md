# Playwright Python — optional private BrowserRenderer (#170)

- Upstream: https://github.com/microsoft/playwright-python
- Release: [v1.64.0](https://github.com/microsoft/playwright-python/releases/tag/v1.64.0), published 2026-10-13.
- Exact upstream tag commit: `387a8a943bb397962f19085c376a301b440029b6` (`git ls-remote ... refs/tags/v1.64.0`).
- License: Apache-2.0; retain the installed distribution's original license and notices. No upstream source is copied.
- Adopted via optional Python package pin `playwright==1.64.0` and its synchronous Chromium API.
- Browser binary: a separately installed `/usr/bin/` or `/opt/` Chromium executable; record its `browser.version` with each rendition. Chromium distribution licenses remain its distributor's responsibility.
- Rationale: the existing safe HTTP capture cannot execute client-side JS; native Playwright supplies Chromium sessions, network interception and deterministic DOM extraction. Project code implements only rights gating, a Linux network namespace, strict HTTPS/DNS checks, resource budgets, and rendition receipts.

The adapter is opt-in and requires Linux bubblewrap for browser process isolation.
The browser runs without access to the user's home or host network. An isolated
fresh context has no persistent cookie/login profile. The parent Python transport
fulfills every HTTPS request with `source_watcher.fetch_bytes`, which validates
all DNS answers and pins the connected socket through redirects. WebSockets are
blocked. HTTP redirects for both documents and subresources are refused,
including same-host redirects: Playwright route.fulfill would otherwise hide
the actual fetched URL and undermine rights/provenance validation.
Deployment remains blocked until a real target has reviewed capture
rights, explicit allowlisted resource hosts, accepted network limits and a
recorded browser binary/version. Installing the optional extra does not enable
rendering. No real source was fetched for #170.
