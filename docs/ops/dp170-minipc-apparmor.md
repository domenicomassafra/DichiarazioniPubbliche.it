# DP-170 — confined Chromium on MiniPC (issue #360)

Ubuntu's `bwrap-userns-restrict` grants `userns` to `/usr/bin/bwrap`, but its
`unpriv_bwrap` child profile denies capabilities. Chrome launched from that
bubblewrap remains stacked with the child profile and exits with code 134:
`The SUID sandbox helper binary was found, but is not configured correctly`.
Trying `--disable-setuid-sandbox` still fails with `No usable sandbox`.
Direct `/opt/google/chrome/chrome` works because Ubuntu ships an AppArmor
`chrome` profile granting `userns`. Direct launch cannot replace the existing
`bwrap --unshare-net` egress boundary.

Ubuntu documents a **path-specific** AppArmor `flags=(unconfined)` profile with
`userns,` for applications requiring nested user namespaces. Apply this pattern
to a root-owned copy of the distribution `bwrap`, limited to the MiniPC runtime
group; do not edit Ubuntu's `/usr/bin/bwrap` or its system profile. The wrapper
selects the dedicated binary only if it has the expected owner, group, mode
and is not a symlink. Without it, other Linux hosts keep using `/usr/bin/bwrap`.

Official sources:

- https://documentation.ubuntu.com/release-notes/24.04/#unprivileged-user-namespace-restrictions
- https://documentation.ubuntu.com/release-notes/25.04/#apparmor-profile-for-bwrap
- https://chromium.googlesource.com/chromium/src/+/main/docs/security/apparmor-userns-restrictions.md

## Administrative install (MiniPC only)

The following requires an authenticated system administrator. Stage the two
tracked files from the same reviewed `main` commit under the user's private
directory before running it. Confirm the MiniPC runtime group is `udodo`.

```sh
sudo install -d -o root -g root -m 0755 /usr/local/libexec
sudo install -o root -g udodo -m 0750 /usr/bin/bwrap /usr/local/libexec/dp-browser-bwrap
sudo install -o root -g root -m 0644 deploy/apparmor/dp-browser-bwrap /etc/apparmor.d/dp-browser-bwrap
sudo apparmor_parser -r /etc/apparmor.d/dp-browser-bwrap
```

Before installation, parse with `apparmor_parser -Q -T` (no kernel load) and
verify the binary/group/`bwrap --version`. After loading, check the actual
AppArmor label inside the wrapper and execute the authorised TodoMVC canary
using `tools/dp170_render_canary.py`; require sandbox ON, network namespace
separate from parent, an observed JavaScript delta and a hash/rights receipt.
Do not treat successful syntax parsing as runtime acceptance. Browser-only
checks must leave the public projection, database, and captures untouched.

For a rollback, remove only the dedicated AppArmor profile with
`sudo apparmor_parser -R /etc/apparmor.d/dp-browser-bwrap`, then remove that
specific profile file and the copied executable, after ensuring no renderer
is running. The wrapper falls back to distribution `bwrap` and therefore
fails closed on the affected Ubuntu host. Keep
`kernel.apparmor_restrict_unprivileged_userns=1`, Chromium sandbox enabled and
the `--unshare-net` boundary throughout. Refresh the dedicated binary after
an Ubuntu `bubblewrap` security update and repeat the canary.
