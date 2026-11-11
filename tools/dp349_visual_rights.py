"""Curated DP-349 visual review assets and their redistribution limits.

The owner-supplied design screenshot contains a photographic portrait whose
author/license is unknown. A screenshot of our page containing that crop inherits
the unresolved photo rights; a fixture policy is not a grant for the portrait.
"""

DATE = "2026-11-11"
ROOT = "docs/ux/dp349-review-20261111/"
SOURCE = "Owner-provided DP-349 visual reference (2026-11-11), available in private ControlCenter handoff"
UNRESOLVED = (
    "Owner's design image includes a portrait with unknown photographer/license. "
    "DP-305 rights/attribution review is required before reuse in a public site, "
    "published dataset, or other redistribution beyond the authorized design review."
)
CHROME_SCREENSHOTS = (
    "dichiarazione-1280.png",
    "esplora-768.png",
    "fonte-1280.png",
    "fonte-1440.png",
    "fonte-390.png",
    "fonte-768.png",
    "fonte-950.png",
    "home-1440.png",
    "home-390.png",
    "persona-1280.png",
)


def dp349_visual_rows(fixture_policy: str) -> dict[str, dict]:
    """Explicit reviewed path inventory; hashes are filled by the generator."""
    rows = {}
    for filename in CHROME_SCREENSHOTS:
        photo = filename.startswith("fonte-")
        path = ROOT + "screenshots/" + filename
        rows[path] = dict(
            artifact_kind="derived" if photo else "synthetic",
            origin="Dichiarazioni Pubbliche contributors (real local Chrome capture)",
            source_reference=SOURCE if photo else
                "web/src/data/demo-projection.json and DP-349 authored UI; review method in " + ROOT + "README.md",
            retrieved_at=DATE,
            review_date=DATE,
            license_or_terms="UNKNOWN" if photo else fixture_policy,
            license_evidence="UNKNOWN" if photo else
                "docs/licensing/README.md#synthetic-fixture-policy",
            attribution="Owner-supplied design portrait; photographer unknown." if photo else
                "Project-authored screenshot of fictional sample records, with no externally sourced portrait.",
            modifications=f"Captured {filename} using Chrome CDP at the encoded CSS viewport; no media playback.",
            personal_data="Unidentified photographic portrait from reference; fictional label." if photo else
                "Fictional people/claims only; no private source records.",
            redistribution_status="pending-review" if photo else "allowed",
            public_projection_status="DP-349 design review image only; not a public Content/Statement artifact.",
            blocker=UNRESOLVED if photo else None,
        )

    rows[ROOT + "reference-target-page.png"] = dict(
        artifact_kind="reference",
        origin="Domenico (owner-supplied source-page design screenshot)",
        source_reference=SOURCE,
        retrieved_at=DATE,
        review_date=DATE,
        license_or_terms="UNKNOWN",
        license_evidence="UNKNOWN",
        attribution="Owner-supplied screenshot; portrait photographer and license unknown.",
        modifications="Cropped the page region from the owner's larger annotated reference screenshot.",
        personal_data="Unidentified photographic portrait; no attribution to a real named speaker.",
        redistribution_status="pending-review",
        public_projection_status="DP-349 review only, not consumer or public-v2 data.",
        blocker=UNRESOLVED,
    )
    rows[ROOT + "comparison-target-vs-preview-950.png"] = dict(
        artifact_kind="derived",
        origin="Dichiarazioni Pubbliche contributors (owner source image + project Chrome screenshot)",
        source_reference=ROOT + "reference-target-page.png and screenshots/fonte-950.png",
        retrieved_at=DATE,
        review_date=DATE,
        license_or_terms="UNKNOWN",
        license_evidence="UNKNOWN",
        attribution="Includes a cropped owner-supplied design reference; original portrait photographer unknown.",
        modifications="Side-by-side reference and Chrome preview; left side padded to match candidate screenshot height.",
        personal_data="Unidentified photographic portrait; fictional name/context on the mockup.",
        redistribution_status="pending-review",
        public_projection_status="PR/owner design comparison only; not a published public source or dossier.",
        blocker=UNRESOLVED,
    )
    rows["web/src/data/preview-portrait-349.jpg"] = dict(
        artifact_kind="reference",
        origin="Crop from the owner-supplied DP-349 target image",
        source_reference=ROOT + "reference-target-page.png",
        retrieved_at=DATE,
        review_date=DATE,
        license_or_terms="UNKNOWN",
        license_evidence="UNKNOWN",
        attribution="Photographer and portrait license unknown; purely illustrative in isolated preview.",
        modifications="Extracted 246x168 JPEG crop from the provided design screenshot; embedded as base64 only in opt-in visual preview.",
        personal_data="Portrait of unidentified real person. Label is fictional.",
        redistribution_status="pending-review",
        public_projection_status="No public build, API, sitemap or index; DP-349 opt-in private preview only.",
        blocker=UNRESOLVED,
    )
    return rows
