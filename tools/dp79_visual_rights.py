"""Curated DP-436 card-surface screenshots and their redistribution status.

Isolated local Astro build of the real `VerbatimStatementRecord.astro` component
over the synthetic DP-439 governed release. No external media, no real person
and no private source record is shown; the wording is a project-authored
fixture, including the deliberately odd whitespace span used by the parity gate.
"""

DATE = "2026-11-11"
ROOT = "docs/ux/dp79-verbatim-card-20261111/"
SOURCE = (
    "Isolated local Astro build of web/src/components/VerbatimStatementRecord.astro "
    "over tests/test_dp439_person_topic_v3.py published(); method in " + ROOT + "README.md"
)
SCREENSHOTS = (
    "card-full-1280.png",
    "card-special-bytes-1280.png",
)


def dp79_visual_rows(fixture_policy: str) -> dict[str, dict]:
    """Explicit reviewed path inventory; hashes are filled by the generator."""
    rows = {}
    for filename in SCREENSHOTS:
        rows[ROOT + filename] = dict(
            artifact_kind="synthetic",
            origin="Dichiarazioni Pubbliche contributors (agent-browser Chrome CDP capture)",
            source_reference=SOURCE,
            retrieved_at=DATE,
            review_date=DATE,
            license_or_terms=fixture_policy,
            license_evidence="docs/licensing/README.md#synthetic-fixture-policy",
            attribution="No external attribution required; project-authored fixture wording only.",
            modifications=(
                "Captured at a 1280x900 CSS viewport from a scratch Astro site; "
                "no cropping, retouching or external media."
            ),
            personal_data=(
                "Fictional sample person and claims from the governed test fixture; "
                "no real person, portrait or private source record."
            ),
            redistribution_status="allowed",
            public_projection_status=(
                "DP-436 gate evidence only; isolated component render, never a route, "
                "demo projection or public artifact."
            ),
            blocker=None,
        )
    return rows
