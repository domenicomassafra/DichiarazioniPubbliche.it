#!/usr/bin/env python3
"""DP-603 — generate `docs/licensing/fixture-inventory.v1.json` from the real tree.

The row *judgements* (rights, attribution, redistribution) are curated human
decisions recorded in ROW_DECISIONS below; the *hashes and existence* are computed
from the actual tracked files. Re-running this after adding a file that has no
decision fails loudly instead of inventing rights.

Usage:
    python3 tools/generate_fixture_inventory.py            # write inventory
    python3 tools/generate_fixture_inventory.py --check    # fail if stale
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "licensing" / "fixture-inventory.v1.json"
SCHEMA_VERSION = "fixture-inventory/v1"
POLICY_VERSION = "DP-603@2026-09-26"

REVIEW_DATE = "2026-09-26"
OWNER = "Dichiarazioni Pubbliche maintainers (owner: repo principal)"

CODE_LICENSE = "Apache-2.0"
FIXTURE_POLICY = "DICHIARAZIONI-PUBBLICHE-FIXTURE-POLICY-1.0"

# Curated rights decisions. Keyed by repo path. Every value is a human decision,
# not an inference from the Apache-2.0 code license.
ROW_DECISIONS: dict[str, dict] = {
    # ---- synthetic fixtures authored for this project ----
    "poc/fixtures/italian_cases.json": dict(
        artifact_kind="synthetic",
        origin="Dichiarazioni Pubbliche contributors",
        source_reference="authored in-repo; see https://www.istat.it/ and https://www.ansa.it/ for the real statistics the numeric rules are written against",
        retrieved_at=REVIEW_DATE,
        license_or_terms=FIXTURE_POLICY,
        license_evidence="docs/licensing/README.md#synthetic-fixture-policy",
        attribution="No external attribution required. Real publishers (ISTAT, ANSA, Fratelli d'Italia) are named as the *subject* of the test cases; the file itself is a synthetic harness, not a copy of their text.",
        modifications="Numeric values transcribed by hand from public statistics to build deterministic verification cases; case structure, ids and expected outcomes authored in-repo.",
        personal_data="public-figure names in a synthetic test harness; no private data, no raw transcript",
        redistribution_status="allowed",
        public_projection_status="not a public artifact; test-only fixture, never projected",
        blocker=None,
    ),
    "tests/fixtures/adversarial-ingestion-v1.json": dict(
        artifact_kind="synthetic",
        origin="Dichiarazioni Pubbliche contributors",
        source_reference="authored in-repo (adversarial ingestion cases)",
        retrieved_at=REVIEW_DATE,
        license_or_terms=FIXTURE_POLICY,
        license_evidence="docs/licensing/README.md#synthetic-fixture-policy",
        attribution="No external attribution required.",
        modifications="None; authored for the adversarial test suite.",
        personal_data="fictional/hostile strings only; no real personal data",
        redistribution_status="allowed",
        public_projection_status="not a public artifact; test-only fixture",
        blocker=None,
    ),
    "tests/fixtures/corpus-search-benchmark-v1.json": dict(
        artifact_kind="derived",
        origin="Dichiarazioni Pubbliche contributors",
        source_reference="project-authored corpus-search benchmark queries and internal record ids derived from the private Garlasco research corpus; contains no source body or transcript excerpt",
        retrieved_at="2026-09-29",
        license_or_terms=CODE_LICENSE,
        license_evidence="LICENSE (project-authored benchmark fixture; no third-party source body)",
        attribution="Project-authored search queries and internal Dichiarazioni Pubbliche record identifiers. Public-figure names are subjects of the benchmark, not copied third-party expression.",
        modifications="Benchmark cases authored in-repo to measure lexical/trigram retrieval against existing private corpus records.",
        personal_data="public-figure names and public-case subject matter only; no private data, raw transcript or evidence body",
        redistribution_status="allowed",
        public_projection_status="internal search benchmark; not a public finding or public projection artifact",
        blocker=None,
    ),
    "tests/fixtures/research-discovery-manifest-v1.json": dict(
        artifact_kind="reference",
        origin="Dichiarazioni Pubbliche contributors",
        source_reference="project-authored DP-209 discovery canary manifest referencing an internal configured source id; contains no fetched platform content",
        retrieved_at="2026-09-29",
        license_or_terms=CODE_LICENSE,
        license_evidence="LICENSE (project-authored configuration fixture; no third-party source body)",
        attribution="No third-party content embedded. The configured source id names a public creator account only as a discovery target.",
        modifications="None; authored in-repo as a bounded metadata-only discovery canary.",
        personal_data="public account identifier only; no private data, media, transcript or source body",
        redistribution_status="allowed",
        public_projection_status="internal discovery fixture; never itself projected publicly",
        blocker=None,
    ),
    "web/src/data/demo-projection.json": dict(
        artifact_kind="synthetic",
        origin="Dichiarazioni Pubbliche contributors",
        source_reference="generated by dichiarazioni_pubbliche.public_projection from fictional inputs; see web/README.md",
        retrieved_at=REVIEW_DATE,
        license_or_terms=FIXTURE_POLICY,
        license_evidence="docs/licensing/README.md#synthetic-fixture-policy",
        attribution="Fictional demo content. Not attributable to any real person, publisher, or dataset.",
        modifications="Fictional dossiers, evidence and findings generated for the demo banner state.",
        personal_data="fictional; explicitly labeled 'Ambiente dimostrativo' in the UI",
        redistribution_status="allowed",
        public_projection_status="demo-only; never the real public projection",
        blocker=None,
    ),
    "web/src/data/content-audit.ts": dict(
        artifact_kind="synthetic",
        origin="Dichiarazioni Pubbliche contributors",
        source_reference="authored in-repo (ContentAudit UX fixture)",
        retrieved_at=REVIEW_DATE,
        license_or_terms=FIXTURE_POLICY,
        license_evidence="docs/licensing/README.md#synthetic-fixture-policy",
        attribution="Fictional 'Rete Civica' content; explicitly demo-only.",
        modifications="None; authored for the ContentAudit route.",
        personal_data="fictional; no real person or publisher",
        redistribution_status="allowed",
        public_projection_status="demo-only; isolated from the public projection",
        blocker=None,
    ),
    "web/src/data/studio.ts": dict(
        artifact_kind="synthetic",
        origin="Dichiarazioni Pubbliche contributors",
        source_reference="authored in-repo (Verify Studio UX fixture)",
        retrieved_at=REVIEW_DATE,
        license_or_terms=FIXTURE_POLICY,
        license_evidence="docs/licensing/README.md#synthetic-fixture-policy",
        attribution="Fictional private-session fixture; demo-only.",
        modifications="None; authored for the Studio routes.",
        personal_data="fictional; no real operator or case",
        redistribution_status="allowed",
        public_projection_status="demo-only; private Studio fixture, never projected",
        blocker=None,
    ),
    "poc/benchmarks/claim-extraction/20260922-gemini-3.8-flash-tiered/diagnostic.json": dict(
        artifact_kind="derived",
        origin="Dichiarazioni Pubbliche contributors",
        source_reference="runtime diagnostic receipt produced 2026-09-22 against the MiniPC OmniRoute runtime",
        retrieved_at="2026-09-22",
        license_or_terms=CODE_LICENSE,
        license_evidence="LICENSE (project-authored runtime receipt)",
        attribution="Project-authored receipt; no third-party text.",
        modifications="Health/canary observations recorded; contains no prompt or provider response body.",
        personal_data="none",
        redistribution_status="allowed",
        public_projection_status="internal engineering receipt; not a public artifact",
        blocker=None,
    ),
    "research/results/poc-benchmark-v0.json": dict(
        artifact_kind="derived",
        origin="Dichiarazioni Pubbliche contributors",
        source_reference="offline benchmark run 2026-09-21 over poc/fixtures/italian_cases.json",
        retrieved_at="2026-09-21",
        license_or_terms=CODE_LICENSE,
        license_evidence="LICENSE (project-authored benchmark receipt)",
        attribution="Project-authored receipt. Historical 'PUBLISH' labels are legacy benchmark output, NOT a publication contract.",
        modifications="None; recorded benchmark result.",
        personal_data="synthetic case subjects from the fixture",
        redistribution_status="allowed",
        public_projection_status="internal historical receipt; the PUBLISH labels are not publication authorization",
        blocker=None,
    ),
    "research/results/content-audit-raffagiulians-bollo-v1.json": dict(
        artifact_kind="derived",
        origin="Dichiarazioni Pubbliche contributors",
        source_reference="derived from poc/content/raffagiulians-bollo-2026/content-audit.json",
        retrieved_at="2026-09-21",
        license_or_terms=CODE_LICENSE,
        license_evidence="LICENSE (project-authored derived receipt)",
        attribution="Derived from a real public-source metadata record; see the source row for rights status.",
        modifications="ContentAudit structure derived from the source metadata; no raw transcript committed.",
        personal_data="identifies a real public figure; public-source metadata only, no private data",
        redistribution_status="pending-review",
        public_projection_status="held pending DP-304/DP-305 rights and privacy review",
        blocker="Real-person public-source metadata: needs DP-304 (privacy) + DP-305 (excerpt) review before any public distribution.",
    ),
    "poc/content/raffagiulians-bollo-2026/content-audit.json": dict(
        artifact_kind="public-source",
        origin="Raffaele Giuliani (public Instagram/TikTok content); structure authored by Dichiarazioni Pubbliche contributors",
        source_reference="https://www.instagram.com/raffagiulians/reel/DdZseq2tjn4/ ; https://www.tiktok.com/@raffagiulians/video/7686596204074896672",
        retrieved_at="2026-09-21",
        license_or_terms="UNKNOWN",
        license_evidence="UNKNOWN",
        attribution="Platform content by Raffaele Giuliani. Public availability is not a redistribution grant; Instagram/TikTok terms reserve rights.",
        modifications="ContentAudit metadata, transcript hashes and claim extraction authored by the project; full transcript NOT committed (raw/transcript.txt is owner-local).",
        personal_data="identifies a real public figure and their spoken claims; public-source only",
        redistribution_status="blocked",
        public_projection_status="BLOCKED — not redistributable and not projectable without owner/legal decision",
        blocker="Platform ToS reserve rights; no redistribution grant. Needs DP-305 (copyright/excerpt) + DP-304 (privacy) review. Do NOT ship in a release or public projection.",
    ),
    "poc/content/pulp-grillo-2026-09-21/content-audit.scaffold.json": dict(
        artifact_kind="public-source",
        origin="Beppe Grillo / Pulp Podcast (public YouTube content); scaffold authored by Dichiarazioni Pubbliche contributors",
        source_reference="https://www.youtube.com/watch?v=QaE00l6JZ8w",
        retrieved_at="2026-09-21",
        license_or_terms="UNKNOWN",
        license_evidence="UNKNOWN",
        attribution="Public YouTube content by Beppe Grillo / Pulp Podcast. YouTube terms reserve rights; auto-caption source.",
        modifications="Scaffold with source metadata and caption hash; no caption body or transcript committed.",
        personal_data="identifies a real public figure; public-source only",
        redistribution_status="blocked",
        public_projection_status="BLOCKED — not redistributable and not projectable without owner/legal decision",
        blocker="YouTube ToS + DP-305 + DP-304 review required. Do NOT ship in a release or public projection.",
    ),
    "research/content-audits/raffagiulians-bollo-2026/source-metadata.json": dict(
        artifact_kind="public-source",
        origin="Raffaele Giuliani (public content); metadata transcribed by Dichiarazioni Pubbliche contributors",
        source_reference="https://www.instagram.com/raffagiulians/reel/DdZseq2tjn4/",
        retrieved_at="2026-09-21",
        license_or_terms="UNKNOWN",
        license_evidence="UNKNOWN",
        attribution="Public platform content; public availability is not a redistribution grant.",
        modifications="Source metadata transcribed; no media committed.",
        personal_data="real public figure; public-source only",
        redistribution_status="blocked",
        public_projection_status="BLOCKED",
        blocker="Same as the parent content audit: platform ToS; DP-304/DP-305 review required.",
    ),
    "research/content-audits/raffagiulians-bollo-2026/claims.json": dict(
        artifact_kind="public-source",
        origin="Raffaele Giuliani (public content); claims extracted by Dichiarazioni Pubbliche contributors",
        source_reference="https://www.instagram.com/raffagiulians/reel/DdZseq2tjn4/",
        retrieved_at="2026-09-21",
        license_or_terms="UNKNOWN",
        license_evidence="UNKNOWN",
        attribution="Extracted claims attributed to a real public speaker; redistribution rights not established.",
        modifications="Atomic claims extracted from the public source; no raw transcript.",
        personal_data="real public figure; derived claims about their statements",
        redistribution_status="blocked",
        public_projection_status="BLOCKED",
        blocker="Platform ToS + DP-301 (intentionality wording) + DP-304/DP-305 review required.",
    ),
    "research/source-candidates/2026-09-25-raffagiulians-public-posts.json": dict(
        artifact_kind="public-source",
        origin="Raffaele Giuliani (public content); harvested by Dichiarazioni Pubbliche contributors",
        source_reference="public posts by @raffagiulians (see poc/content/raffagiulians-bollo-2026 for the canonical reel)",
        retrieved_at="2026-09-25",
        license_or_terms="UNKNOWN",
        license_evidence="UNKNOWN",
        attribution="Public platform content; no redistribution grant established.",
        modifications="Post list harvested; no media committed.",
        personal_data="real public figure",
        redistribution_status="blocked",
        public_projection_status="BLOCKED",
        blocker="Platform ToS; DP-304/DP-305 review required.",
    ),
    "research/source-candidates/2026-09-21-pulp-grillo-64.json": dict(
        artifact_kind="public-source",
        origin="Beppe Grillo / Pulp Podcast (public YouTube content); metadata harvested by Dichiarazioni Pubbliche contributors",
        source_reference="https://www.youtube.com/watch?v=QaE00l6JZ8w",
        retrieved_at="2026-09-21",
        license_or_terms="UNKNOWN",
        license_evidence="UNKNOWN",
        attribution="Public YouTube content; no redistribution grant established.",
        modifications="Source candidate metadata; no media or transcript committed.",
        personal_data="real public figure",
        redistribution_status="blocked",
        public_projection_status="BLOCKED",
        blocker="YouTube ToS; DP-304/DP-305 review required.",
    ),
    "tests/fixtures/postgres-provenance-canary.sql": dict(
        artifact_kind="synthetic",
        origin="Dichiarazioni Pubbliche contributors",
        source_reference="authored in-repo (isolated PostgreSQL provenance canary)",
        retrieved_at=REVIEW_DATE,
        license_or_terms=CODE_LICENSE,
        license_evidence="LICENSE (project-authored SQL canary)",
        attribution="No external attribution required.",
        modifications="None; authored to exercise provenance constraints in a disposable database.",
        personal_data="synthetic rows only; no production data",
        redistribution_status="allowed",
        public_projection_status="not a public artifact; isolated-DB canary only",
        blocker=None,
    ),
    "docs/ux/prototypes-v3/generated-style-02/index.html": dict(
        artifact_kind="reference",
        origin="Dichiarazioni Pubbliche contributors (generated prototype gallery)",
        source_reference="generated in-repo from docs/ux/prototypes-v3 prompt packs",
        retrieved_at=REVIEW_DATE,
 license_or_terms=CODE_LICENSE,
        license_evidence="LICENSE (project-authored generated prototype)",
        attribution="Project-authored prototype gallery. Mockup text/verdicts/names are placeholders, not factual content.",
        modifications="Rendered gallery of generated style-02 screenshots.",
        personal_data="none; generated placeholder text",
        redistribution_status="allowed",
        public_projection_status="internal design reference; not a public artifact",
        blocker=None,
    ),
}

# Visual/reference assets: a curated group generated per-path so hashes are real.
VISUAL_GENERATED_STYLE3 = "docs/ux/prototypes-v3/generated/style3"
VISUAL_GENERATED_STYLE02 = "docs/ux/prototypes-v3/generated-style-02/png"
VISUAL_REFERENCE = "docs/ux/reference/p6.2"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def visual_decision(path: str) -> dict:
    if path.startswith(VISUAL_GENERATED_STYLE3) or path.startswith(VISUAL_GENERATED_STYLE02):
        return dict(
            artifact_kind="reference",
            origin="Dichiarazioni Pubbliche contributors (generated from GPT Image prompt packs in docs/ux/prototypes-v3/)",
            source_reference="generated in-repo; prompt packs at docs/ux/prototypes-v3/*.prompt.md",
            retrieved_at=REVIEW_DATE,
            license_or_terms=CODE_LICENSE,
            license_evidence="LICENSE (project-authored generated visual)",
            attribution="Project-authored generated mockup. Mockup text/verdicts/names are placeholders, not factual content.",
            modifications="Rendered from in-repo design prompt; not a screenshot of any real product.",
            personal_data="none; generated placeholder text",
            redistribution_status="allowed",
            public_projection_status="internal design reference; not a public artifact",
            blocker=None,
        )
    if path.startswith(VISUAL_REFERENCE):
        return dict(
            artifact_kind="reference",
            origin="unknown (imported from a local Downloads folder on 2026-09-23)",
            source_reference="UNKNOWN",
            retrieved_at="2026-09-23",
            license_or_terms="UNKNOWN",
            license_evidence="UNKNOWN",
            attribution="Provenance unknown. Visual reference only; not product authority (docs/ux/reference/p6.2/README.md).",
            modifications="None; imported as a visual reference for composition/density/typography review.",
            personal_data="unknown origin; no content is approved as factual",
            redistribution_status="pending-review",
            public_projection_status="internal design reference; never a public artifact",
            blocker="UNKNOWN origin/license. Owner decision required before redistribution. Consider removing from the tree if not needed.",
        )
    raise KeyError(path)


def build_rows() -> list[dict]:
    tracked = subprocess.run(
        ["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout.split("\0")
    tracked = [p for p in tracked if p]

    rows: list[dict] = []
    covered: set[str] = set()

    for path in tracked:
        decision = None
        if path in ROW_DECISIONS:
            decision = ROW_DECISIONS[path]
        elif path.startswith(VISUAL_GENERATED_STYLE3) and path.endswith(".png"):
            decision = visual_decision(path)
        elif path.startswith(VISUAL_GENERATED_STYLE02) and path.endswith(".png"):
            decision = visual_decision(path)
        elif path.startswith(VISUAL_REFERENCE) and path.endswith(".png"):
            decision = visual_decision(path)
        if decision is None:
            continue

        disk = ROOT / path
        content_hash = sha256(disk) if disk.is_file() else "UNKNOWN"
        row = {
            "asset_id": _asset_id(path),
            "path_or_locator": path,
            **decision,
            "content_hash": content_hash,
            "owner_and_review": {
                "owner": OWNER,
                "reviewer": OWNER,
                "review_date": REVIEW_DATE,
                "re_review_trigger": (
                    "any change to the artifact hash, source reference, or platform terms; "
                    "and at each release gate"
                ),
            },
        }
        # stable field order for a clean diff
        ordered = {k: row[k] for k in REQUIRED_ORDER}
        rows.append(ordered)
        covered.add(path)

    return sorted(rows, key=lambda r: r["path_or_locator"])


def _asset_id(path: str) -> str:
    return path.replace("/", ":")


REQUIRED_ORDER = [
    "asset_id", "path_or_locator", "artifact_kind", "origin", "source_reference",
    "retrieved_at", "content_hash", "license_or_terms", "license_evidence",
    "attribution", "modifications", "personal_data", "redistribution_status",
    "public_projection_status", "owner_and_review", "blocker",
]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if the on-disk inventory is stale")
    args = parser.parse_args(argv)

    rows = build_rows()

    inv = {
        "schema_version": SCHEMA_VERSION,
        "policy_version": POLICY_VERSION,
        "generated_by": "tools/generate_fixture_inventory.py",
        "generated_on": date.today().isoformat(),
        "code_license": CODE_LICENSE,
        "note": (
            "Machine-readable fixture/data licensing inventory (DP-603). Rights are curated "
            "human decisions, not inferred from the Apache-2.0 code license. UNKNOWN license "
            "rows are blocked/pending-review and must NOT be shipped in a release or public "
            "projection until owner/legal review. Enforced by tools/check_licensing_inventory.py."
        ),
        "asset_count": len(rows),
        "assets": rows,
    }

    payload = json.dumps(inv, indent=2, ensure_ascii=False, sort_keys=False) + "\n"

    if args.check:
        if not OUT.is_file():
            print("FAIL: inventory missing; run tools/generate_fixture_inventory.py")
            return 1
        current = OUT.read_text(encoding="utf-8")
        # generated_on changes daily; ignore it in the staleness comparison.
        import re

        def strip(text: str) -> str:
            return re.sub(r'"generated_on": "[^"]+"', '"generated_on": ""', text)

        if strip(current) != strip(payload):
            print("FAIL: inventory is stale; re-run tools/generate_fixture_inventory.py")
            return 1
        print("OK: inventory is up to date.")
        return 0

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(payload, encoding="utf-8")
    print(f"wrote {OUT} with {len(rows)} row(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
