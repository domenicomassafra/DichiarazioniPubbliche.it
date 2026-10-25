#!/bin/sh
# Chromium gets explicit system runtime mounts, not the host filesystem.
# Filesystem, network, PID, IPC, session and temporary storage are isolated.
set -eu
browser=${DICHIARAZIONI_PLAYWRIGHT_CHROMIUM_BIN:-}
case "$browser" in
    /usr/bin/*|/opt/*) ;;
    *) exit 86 ;;
esac
[ -x "$browser" ] || exit 86
command -v bwrap >/dev/null 2>&1 || exit 86
# Ubuntu's stock bwrap AppArmor profile stacks unpriv_bwrap onto Chrome and
# denies the capabilities its *own* sandbox needs. A root-installed, dedicated
# bwrap executable can receive Ubuntu's per-path userns grant instead. Keep
# the stock binary for distributions where Chromium already works with it.
bwrap_bin=$(command -v bwrap)
dedicated_bwrap=/usr/local/libexec/dp-browser-bwrap
if [ -e "$dedicated_bwrap" ] || [ -L "$dedicated_bwrap" ]; then
    [ -f "$dedicated_bwrap" ] && [ -x "$dedicated_bwrap" ] || exit 86
    [ ! -L "$dedicated_bwrap" ] || exit 86
    [ "$(stat -c %u "$dedicated_bwrap")" = 0 ] || exit 86
    [ "$(stat -c %g "$dedicated_bwrap")" = "$(id -g)" ] || exit 86
    [ "$(stat -c %a "$dedicated_bwrap")" = 750 ] || exit 86
    bwrap_bin=$dedicated_bwrap
fi
# Resolve root-owned distribution symlinks (e.g. /usr/bin/google-chrome ->
# /opt/google/chrome/google-chrome) before discarding /etc/alternatives.
resolved=$(readlink -f "$browser") || exit 86
case "$resolved" in
    /usr/bin/*|/usr/lib/*|/opt/*/*) ;;
    *) exit 86 ;;
esac
[ -x "$resolved" ] || exit 86
# A launcher script only execs host paths that this namespace never mounts.
[ "$(dd if="$resolved" bs=2 count=1 2>/dev/null)" != '#!' ] || exit 86
# Bound descriptors and generated files, including the browser's child processes.
# 64 MiB per file: Chromium's own disk cache writes exceed 4 MiB on a real page
# and SIGXFSZ killed the renderer before any JavaScript effect could be observed.
ulimit -n 256
ulimit -f 65536

# Keep caller arguments exactly; bwrap's optional application tree is only the
# directory containing the executable, never all of /opt or the host root.
set -- -- "$resolved" "$@"
case "$resolved" in
    /opt/*)
        browser_dir=$(dirname "$resolved")
        [ "$browser_dir" != /opt ] || exit 86
        set -- --ro-bind "$browser_dir" "$browser_dir" "$@"
        ;;
esac

# Bubblewrap's tmpfs root is empty. Expose only shared executable/runtime
# libraries, selected read-only public system assets and font configuration.
# There is deliberately no /etc/passwd, /etc/ssh, /home, /root, /usr/local,
# /var/log, /sys or host /run, and no general host directory bind.
exec "$bwrap_bin" --die-with-parent --unshare-net --unshare-pid --unshare-ipc \
    --unshare-uts --hostname dp-browser --new-session \
    --tmpfs / --dir /usr --dir /usr/share \
    --ro-bind /usr/bin /usr/bin --ro-bind /usr/lib /usr/lib \
    --ro-bind-try /usr/lib64 /usr/lib64 \
    --ro-bind-try /usr/share/fonts /usr/share/fonts \
    --ro-bind-try /usr/share/fontconfig /usr/share/fontconfig \
    --symlink usr/bin /bin --symlink usr/lib /lib \
    --symlink usr/lib64 /lib64 \
    --dir /etc --ro-bind-try /etc/fonts /etc/fonts \
    --dir /var --symlink /run /var/run \
    --tmpfs /tmp --tmpfs /run --dev /dev --proc /proc \
    --clearenv --setenv PATH /usr/bin:/bin --setenv HOME /tmp \
    --setenv TMPDIR /tmp --setenv LANG C.UTF-8 \
    --setenv XDG_CONFIG_HOME /tmp/.config --setenv XDG_CACHE_HOME /tmp/.cache \
    --chdir /tmp "$@"
