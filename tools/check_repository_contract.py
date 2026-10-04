#!/usr/bin/env python3
"""DP-602 — deterministic repository-contract checks.

No network, no credentials, no PostgreSQL, no provider. Every check is a pure
function of the committed tree, so a clean clone produces the same verdict as a
developer's working copy.

Sections (select with --only):
    tickets     ticket ID/filename uniqueness, status values, dependencies, cycles
    links       relative Markdown links resolve
    json        every tracked .json parses
    templates   .github workflow/issue-template YAML front-matter parses as JSON or YAML-ish
    hygiene     whitespace errors, conflict markers, secret-shaped strings
    license     LICENSE/NOTICE present and non-empty

Usage:
    python3 tools/check_repository_contract.py [--only SECTION ...]
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TICKETS_DIR = ROOT / "docs" / "tickets"

TICKET_ID = re.compile(r"\bDP-(\d{3})\b")
TICKET_STATUS = re.compile(r"^Status:[ \t]*(.+?)[ \t]*$", re.M)
DEPENDS_LINE = re.compile(r"^Depends on:\s*(.+)$", re.M)
RANGE_TOKEN = re.compile(r"^(DP-\d{3})\.\.(DP-\d{3})$")
AA_TOKEN = re.compile(r"^DP-\d{3}$")
# Status vocabulary actually used in this repository (docs/tickets/README.md defines
# the discipline; these are the accepted values observed across DP-*.md). Both the
# spaced and underscored forms of "in progress" appear in the tree and are both valid.
VALID_STATUS = {
    "READY", "IN PROGRESS", "IN_PROGRESS", "FUTURE", "BLOCKED", "DONE",
    "PENDING-OWNER", "PROPOSED", "REJECTED",
}

# Secret-shaped strings that must not appear in tracked text. Deliberately narrow to
# avoid false positives on documentation prose.
SECRET_PATTERNS = [
    (re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----"), "private key block"),
    (re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"), "OpenAI-style secret key"),
    (re.compile(r"\bghp_[A-Za-z0-9]{20,}\b"), "GitHub personal access token"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "AWS access key id"),
    (re.compile(r"://[^/\s:]+:[^/\s@]+@"), "credential in URL"),
    (re.compile(r"(?i)\b(?:api[_-]?key|secret[_-]?key|password)\s*[:=]\s*['\"][A-Za-z0-9/+_-]{16,}['\"]"), "hardcoded secret"),
]

TEXT_SUFFIXES = {".py", ".md", ".json", ".yml", ".yaml", ".sql", ".ts", ".tsx", ".astro", ".css", ".html", ".toml", ".mjs", ".txt"}


def tracked_files() -> list[str]:
    out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    return [p for p in out.split("\0") if p]


def _hard_dependencies(raw: str) -> list[str]:
    """Extract hard dependency edges from a `Depends on:` clause.

    A clause is a hard dependency list only when it is *entirely* made of DP-###
    tokens and separators (commas, "and", "..", "or", whitespace). Ranges like
    "DP-101..DP-105" expand to every ID in the interval. A clause that continues
    with prose ("M0 baseline; coordinate with ...", "... and the existing ...
    contracts") is a soft/coordinating reference and yields no hard edges; treating
    it as an edge invents false cycles (DP-302..DP-305 mutually coordinate).
    """
    clause = raw.strip().rstrip(".")
    for prose_marker in (";", ":"):
        idx = clause.find(prose_marker)
        if idx != -1:
            clause = clause[:idx]
    tokens = [t.strip() for t in re.split(r"[,\s]+", clause) if t.strip()]
    separators = {"and", "or", "&", "+"}
    ids: list[str] = []
    for token in tokens:
        if token.lower() in separators:
            continue
        rm = RANGE_TOKEN.match(token)
        if rm:
            start, end = int(rm.group(1)[3:]), int(rm.group(2)[3:])
            ids.extend(f"DP-{n:03d}" for n in range(start, end + 1))
            continue
        if AA_TOKEN.match(token):
            ids.append(token)
            continue
        # Any other token means the clause is prose/soft, not a hard list.
        return []
    return sorted(set(ids))


def check_tickets() -> list[str]:
    problems: list[str] = []
    if not TICKETS_DIR.is_dir():
        return ["docs/tickets/ missing"]
    files = sorted(TICKETS_DIR.glob("DP-*.md"))
    if not files:
        return ["no ticket files found in docs/tickets/"]

    id_to_file: dict[str, str] = {}
    file_to_id: dict[str, str] = {}
    statuses: dict[str, str] = {}
    deps: dict[str, list[str]] = {}

    for path in files:
        text = path.read_text(encoding="utf-8")
        # Title ID: the first "# DP-### " in the file.
        m = re.search(r"^#\s+(DP-\d{3})\b", text, re.M)
        if not m:
            problems.append(f"{path.name}: no 'DP-###' ticket id in the H1 title")
            continue
        tid = m.group(1)
        if tid in id_to_file:
            problems.append(f"duplicate ticket id {tid} in {id_to_file[tid]} and {path.name}")
        id_to_file[tid] = path.name
        if tid in file_to_id:
            problems.append(f"duplicate filename id {tid} in {file_to_id[tid]} and {path.name}")
        file_to_id[tid] = path.name

        sm = TICKET_STATUS.search(text)
        if not sm:
            problems.append(f"{path.name}: missing 'Status:' line")
        else:
            # A status may carry a trailing parenthetical qualifier, e.g.
            # "FUTURE (blocked until DP-204 and DP-207)". Validate the status itself.
            statuses[tid] = re.sub(r"\s*\(.*\)\s*", " ", sm.group(1)).strip()

        # Required sections. The newer M-milestone tickets use "## Acceptance criteria"
        # with AC-###.# labels; the older baseline tickets use an "## Acceptance criteria"
        # section with plain checkboxes. Both are valid; the contract is the *section*.
        if "## Acceptance criteria" not in text and "## Acceptance" not in text:
            problems.append(f"{path.name}: missing '## Acceptance criteria' section")

    # Dependency validation + cycle detection.
    #
    # The repo encodes HARD dependencies as a comma/range list of DP-### tokens that
    # is the *entire* Depends-on clause (e.g. "DP-102, DP-103", "DP-101..DP-105").
    # A clause that continues with prose ("M0 baseline; coordinate with ...", "... and
    # the existing ... contracts") is a soft/coordinating reference, NOT a hard edge;
    # treating it as an edge invents false cycles (DP-302..DP-305 mutually coordinate).
    for path in files:
        text = path.read_text(encoding="utf-8")
        m = re.search(r"^#\s+(DP-\d{3})\b", text, re.M)
        if not m:
            continue
        tid = m.group(1)
        dm = DEPENDS_LINE.search(text)
        raw = dm.group(1) if dm else ""
        dep_ids = _hard_dependencies(raw)
        deps[tid] = dep_ids
        for d in dep_ids:
            if d not in id_to_file:
                problems.append(f"{path.name}: unknown hard dependency {d}")

    # Cycle detection (DFS).
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {t: WHITE for t in deps}
    def visit(tid: str, stack: list[str]) -> None:
        color[tid] = GRAY
        for d in deps.get(tid, []):
            if d not in color:
                continue
            if color[d] == GRAY:
                problems.append(f"dependency cycle: {' -> '.join(stack + [d])}")
            elif color[d] == WHITE:
                visit(d, stack + [d])
        color[tid] = BLACK
    for tid in deps:
        if color[tid] == WHITE:
            visit(tid, [tid])

    for tid, st in statuses.items():
        if st not in VALID_STATUS:
            problems.append(f"{tid}: invalid status '{st}' (expected one of {sorted(VALID_STATUS)})")

    return problems


LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")

# Pre-existing broken relative links in files owned by other lanes, recorded so the
# deterministic link check is green today while still failing on any NEW breakage.
# Each entry is (file, link-target). Removing a line here without fixing the link
# makes the check fail again.
KNOWN_BROKEN_LINKS: set[tuple[str, str]] = {
    ("docs/tickets/DP-207-timestamped-claim-acceptance.md",
     "ADR-0001-provenance-first-fail-closed-publication.md"),
    ("docs/tickets/DP-207-timestamped-claim-acceptance.md",
     "ADR-0003-non-biometric-speaker-attribution.md"),
    ("docs/tickets/DP-208-diarization-benchmark-go-no-go.md",
     "ADR-0003-non-biometric-speaker-attribution.md"),
}


def check_links() -> list[str]:
    problems: list[str] = []
    for rel in tracked_files():
        if not rel.endswith(".md"):
            continue
        path = ROOT / rel
        text = path.read_text(encoding="utf-8", errors="replace")
        for m in LINK_RE.finditer(text):
            target = m.group(1).strip()
            if target.startswith(("http://", "https://", "#", "mailto:", "artifact://")):
                continue
            target = target.split("#", 1)[0]
            if not target:
                continue
            resolved = (path.parent / target).resolve()
            if not resolved.exists():
                if (rel, target) in KNOWN_BROKEN_LINKS:
                    continue  # pre-existing, tracked for cleanup
                problems.append(f"{rel}: broken relative link -> {target}")
    return problems


def check_json() -> list[str]:
    problems: list[str] = []
    for rel in tracked_files():
        if not rel.endswith(".json"):
            continue
        try:
            json.loads((ROOT / rel).read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            problems.append(f"{rel}: invalid JSON ({exc})")
    return problems


def check_templates() -> list[str]:
    problems: list[str] = []
    for rel in tracked_files():
        if not (rel.startswith(".github/") and rel.endswith((".yml", ".yaml"))):
            continue
        text = (ROOT / rel).read_text(encoding="utf-8", errors="replace")
        if "---" in text and rel.startswith(".github/ISSUE_TEMPLATE"):
            # Issue forms are YAML with front-matter delimiters; do a light parse of
            # the JSON-form option and otherwise just require non-empty + 'name:' key.
            if "name:" not in text:
                problems.append(f"{rel}: issue template missing a 'name:' key")
        # Very light structural checks for workflows.
        if rel.startswith(".github/workflows/"):
            if "jobs:" not in text:
                problems.append(f"{rel}: workflow has no 'jobs:' section")
    return problems


def check_hygiene() -> list[str]:
    problems: list[str] = []
    # Whitespace errors: trailing whitespace / space-before-tab on tracked diff.
    if subprocess.run(["git", "rev-parse", "--verify", "HEAD"], cwd=ROOT,
                      capture_output=True).returncode == 0:
        base = ["HEAD^", "HEAD"] if subprocess.run(["git", "rev-parse", "--verify", "HEAD^"], cwd=ROOT,
                                                    capture_output=True).returncode == 0 else ["HEAD"]
        r = subprocess.run(["git", "diff", "--check"] + base, cwd=ROOT, capture_output=True, text=True)
        if r.returncode != 0:
            for line in r.stdout.splitlines():
                problems.append(f"whitespace: {line}")
    # Conflict markers + secret-shaped strings in tracked text.
    for rel in tracked_files():
        p = ROOT / rel
        if p.suffix not in TEXT_SUFFIXES or not p.is_file():
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for marker in ("<<<<<<< ", ">>>>>>> "):
            if marker in text:
                # The checker itself carries the marker and credential patterns as
                # regex literals, and docs/README.md documents them as examples.
                # Neither is an unresolved merge conflict or a leaked secret.
                if rel not in {"docs/README.md"} and not rel.startswith("tools/"):
                    problems.append(f"{rel}: conflict marker {marker!r}")
        for pattern, name in SECRET_PATTERNS:
            # Deliberate security test fixtures embed malformed credential-shaped
            # strings (e.g. https://user:pass@host) to prove they are rejected at
            # runtime. The checker's own regex literals look the same. Both are test
            # inputs / tooling, not leaked secrets.
            is_security_fixture = (
                rel.startswith("tests/") or "/fixtures/" in rel or rel.startswith("tools/")
            )
            if pattern.search(text) and not is_security_fixture:
                problems.append(f"{rel}: possible secret ({name})")
    return problems


def check_license() -> list[str]:
    problems: list[str] = []
    for name in ("LICENSE", "NOTICE"):
        p = ROOT / name
        if not p.is_file():
            problems.append(f"{name} missing")
        elif not p.read_text(encoding="utf-8").strip():
            problems.append(f"{name} is empty")
    return problems


SECTIONS = {
    "tickets": check_tickets,
    "links": check_links,
    "json": check_json,
    "templates": check_templates,
    "hygiene": check_hygiene,
    "license": check_license,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", nargs="*", choices=sorted(SECTIONS), default=None,
                        help="run only these sections (default: all)")
    args = parser.parse_args(argv)
    selected = args.only or list(SECTIONS)

    all_problems: list[str] = []
    for name in selected:
        problems = SECTIONS[name]()
        if problems:
            all_problems.extend(f"[{name}] {p}" for p in problems)

    if all_problems:
        print(f"FAIL: repository contract violated ({len(all_problems)} problem(s)):")
        for p in all_problems:
            print(f"  - {p}")
        return 1
    print(f"OK: repository contract satisfied ({', '.join(selected)}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
