# GOAL INFINITO — Wave 17: remove CI Node 20 action deprecation

Date: 2026-10-09. Starting Git commit: `31c4bd5e81ca0e41b2646ac8cbd5f0028225f2ee`.
That exact baseline passed GitHub Actions `37989978926`, 11/11 jobs.

## Cause and scope

All seven official action references in `.github/workflows/ci.yml` used older
Node 20-based action versions. GitHub hosted Actions forced the older actions
to execute with Node 24 and reported deprecation warnings. The official
Node 20 deprecation notice and official action release documentation identify
the minimum Node 24-compatible majors:

- <https://github.blog/changelog/2025-09-19-deprecation-of-node-20-on-github-actions-runners/>
- <https://github.com/actions/checkout/blob/main/README.md>
- <https://github.com/actions/setup-python/blob/main/README.md>
- <https://github.com/actions/setup-node/blob/main/README.md>

Upgrade is intentionally minimal: `checkout@v4 → v5` (four uses),
`setup-python@v5 → v6` (two uses), `setup-node@v4 → v5` (one use).
These majors use Node 24 internally and require hosted runner v2.327.1+.
Web still explicitly installs Node 24, uses the same named npm lockfile
cache, and rejects unauthorized public-projection builds. No new dependency,
grant or runner/OS change, and no publish/release/deploy step.

## Evidence

- New `tests/test_ci_workflow_node24.py` first failed on all seven obsolete
  refs, then passed after the minimal version update; it also guards the
  Python/OS matrix, read-only permission and fail-closed frontend build.
- The committed YAML parses with PyYAML (4 jobs, 7 action usages).
- `python3 -m compileall -q tests/test_ci_workflow_node24.py`,
  `git diff --check`, ticket graph contract: PASS.

Remote GitHub Actions proof specific to the Wave 17 commit must be observed
before recording a claim that warning removal worked on runners.
This remains source workflow maintenance, not MiniPC deployment, code-release
authority, or an unblock of Q-306/DP-307/M7.

Owner local experiments (`ContentAuditClient`, owner handoff, DP-407 keyboard
test) are not modified, staged or committed.
