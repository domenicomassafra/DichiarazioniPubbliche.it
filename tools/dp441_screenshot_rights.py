"""Rights decisions for project-authored DP-441 offline browser screenshots."""

SCREENSHOTS = (
    ("home", 1440),
    ("home", 390),
    ("explore", 320),
    ("statement", 1440),
    ("statement", 390),
    ("intersection", 390),
    ("source", 390),
    ("trace", 390),
)


def dp441_screenshot_rows(fixture_policy: str) -> dict[str, dict]:
    """All 16 screenshots share one verified, fictional source and rights basis."""
    return {
        f"prototypes/redesign-candidates/screenshots/{variant}-{view}-{width}.png": dict(
            artifact_kind="reference",
            origin="Dichiarazioni Pubbliche contributors (Chrome offline render, 2026-10-25)",
            source_reference="prototypes/redesign-candidates/build.py and capture.mjs; render-evidence.json SHA-256",
            retrieved_at="2026-10-25",
            license_or_terms=fixture_policy,
            license_evidence="docs/licensing/README.md#synthetic-fixture-policy",
            attribution="Project-authored screenshot of clearly marked fictional records; no third-party images or content.",
            modifications="PNG captured with the dedicated Studio automation Chrome at an indicated CSS viewport.",
            personal_data="none; fictional, unnamed example person and source only",
            redistribution_status="allowed",
            public_projection_status="offline DP-441 design comparison only; never public-projection data",
            blocker=None,
        )
        for variant in ("atlante", "biblioteca")
        for view, width in SCREENSHOTS
    }
