#!/bin/sh
# Playwright-only Chromium process: no network interface/routes and no home access.
set -eu
browser=${DICHIARAZIONI_PLAYWRIGHT_CHROMIUM_BIN:-}
case "$browser" in
    /usr/bin/*|/opt/*) ;;
    *) exit 86 ;;
esac
[ -x "$browser" ] || exit 86
command -v bwrap >/dev/null 2>&1 || exit 86
# Bound open descriptors and generated file size.
ulimit -n 256
ulimit -f 4096
exec bwrap --die-with-parent --unshare-net --unshare-pid --unshare-ipc \
    --ro-bind / / --tmpfs /home --tmpfs /root \
    --tmpfs /tmp --dev /dev --proc /proc \
    --setenv HOME /tmp -- \
    "$browser" "$@"
