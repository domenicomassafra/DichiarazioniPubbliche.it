"""Curated DP-349 visual review assets and their redistribution limits.

The owner-supplied design screenshot contains a photographic portrait whose
author/license is unknown. On 12 November 2026 the owner ruled every DP-349
image usable and took editorial responsibility for it, so these rows are
`allowed` while staying design-review evidence: they authorize no statement.
"""

DATE = "2026-11-11"
# Owner decision 12 November 2026 (issue #349): every image supplied for the
# redesign is usable; the publisher takes editorial responsibility for it. The
# rows stay design-review evidence, not a publication grant for a statement.
OWNER_DECISION = "OWNER-GRANT-DP349-20261112"
OWNER_EVIDENCE = (
    "Owner decision 2026-11-12, issue #349: all 22 DP-349 images supplied for "
    "the redesign are usable."
)
OWNER_REVIEW_DATE = "2026-11-12"
ROOT = "docs/ux/dp349-review-20261111/"
SOURCE = "Owner-provided DP-349 visual reference (2026-11-11), available in private ControlCenter handoff"
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
MATRIX_FAMILIES = (
    "content", "explore", "home", "method", "person",
    "statement", "topic", "trace", "utility",
)
FIGMA_FAMILIES = (
    "statement", "home", "person", "topic", "explore", "content", "method",
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
            review_date=OWNER_REVIEW_DATE if photo else DATE,
            license_or_terms=OWNER_DECISION if photo else fixture_policy,
            license_evidence=OWNER_EVIDENCE if photo else
                "docs/licensing/README.md#synthetic-fixture-policy",
            attribution="Owner-supplied design portrait; photographer unknown." if photo else
                "Project-authored screenshot of fictional sample records, with no externally sourced portrait.",
            modifications=f"Captured {filename} using Chrome CDP at the encoded CSS viewport; no media playback.",
            personal_data="Unidentified photographic portrait from reference; fictional label." if photo else
                "Fictional people/claims only; no private source records.",
            redistribution_status="allowed",
            public_projection_status="DP-349 design review image only; not a public Content/Statement artifact.",
            blocker=None,
        )

    # Chrome-only fictional fixtures: two documented 9-family matrices.
    # The earlier matrix was committed with #629 but lacked licensing rows;
    # include it here so contributor acceptance covers the entire PR.
    for directory in (ROOT + "route-matrix/", "docs/ux/dp349-figma-20261111/after-matrix/"):
        for family in MATRIX_FAMILIES:
            for variant in ("desktop", "phone", "zoom200"):
                filename = f"{family}-{variant}.png"
                path = directory + filename
                rows[path] = dict(
                    artifact_kind="synthetic",
                    origin="Dichiarazioni Pubbliche contributors (isolated Chrome CDP)",
                    source_reference="web/src/data/demo-projection.json and web/scripts/check-browser-qa.mjs",
                    retrieved_at=DATE,
                    review_date=DATE,
                    license_or_terms=fixture_policy,
                    license_evidence="docs/licensing/README.md#synthetic-fixture-policy",
                    attribution="Project-authored fictional record captures; no third-party portrait.",
                    modifications=f"Captured {family} at {variant} viewport; contains only labelled demo projection.",
                    personal_data="Fictional fixtures only; no real names, private data or source media.",
                    redistribution_status="allowed",
                    public_projection_status="PR visual review only; never a public dossier or runtime asset.",
                    blocker=None,
                )
        path = directory + "person-phone-grayscale.png"
        rows[path] = dict(rows[directory + "person-phone.png"])
        rows[path]["modifications"] = "Fictional 375px person screenshot rendered in grayscale for contrast review."

    # Figma owner-authored reference remains restricted even though the
    # portrait was fully masked in the committed side-by-side comparisons.
    for family in FIGMA_FAMILIES:
        for state in ("pr629", "implementation"):
            path = f"docs/ux/dp349-figma-20261111/{family}-figma-vs-{state}.png"
            rows[path] = dict(
                artifact_kind="derived",
                origin="Owner-authored Figma frame + Dichiarazioni Pubbliche isolated Chrome capture",
                source_reference="https://www.figma.com/design/emKLEdxy5o1R5e2tDOsafZ/ and docs/ux/dp349-figma-20261111/README.md",
                retrieved_at=DATE,
                review_date=OWNER_REVIEW_DATE,
                license_or_terms=OWNER_DECISION,
                license_evidence=OWNER_EVIDENCE,
                attribution="Owner design excerpt; photograph fully masked in comparison.",
                modifications=f"Side-by-side {family} Figma and {state} Chrome; original portrait area masked.",
                personal_data="No portrait pixels; Figma example names are fictional.",
                redistribution_status="allowed",
                public_projection_status="Design review evidence only, excluded from public site and projection.",
                blocker=None,
            )

    rows[ROOT + "reference-target-page.png"] = dict(
        artifact_kind="reference",
        origin="Domenico (owner-supplied source-page design screenshot)",
        source_reference=SOURCE,
        retrieved_at=DATE,
        review_date=OWNER_REVIEW_DATE,
        license_or_terms=OWNER_DECISION,
        license_evidence=OWNER_EVIDENCE,
        attribution="Owner-supplied screenshot under the owner's 2026-11-12 decision.",
        modifications="Cropped the page region from the owner's larger annotated reference screenshot.",
        personal_data="Unidentified photographic portrait; no attribution to a real named speaker.",
        redistribution_status="allowed",
        public_projection_status="DP-349 review only, not consumer or public-v2 data.",
        blocker=None,
    )
    rows[ROOT + "comparison-target-vs-preview-950.png"] = dict(
        artifact_kind="derived",
        origin="Dichiarazioni Pubbliche contributors (owner source image + project Chrome screenshot)",
        source_reference=ROOT + "reference-target-page.png and screenshots/fonte-950.png",
        retrieved_at=DATE,
        review_date=OWNER_REVIEW_DATE,
        license_or_terms=OWNER_DECISION,
        license_evidence=OWNER_EVIDENCE,
        attribution="Includes a cropped owner-supplied design reference covered by the owner's decision.",
        modifications="Side-by-side reference and Chrome preview; left side padded to match candidate screenshot height.",
        personal_data="Unidentified photographic portrait; fictional name/context on the mockup.",
        redistribution_status="allowed",
        public_projection_status="PR/owner design comparison only; not a published public source or dossier.",
        blocker=None,
    )
    rows["web/src/data/preview-portrait-349.jpg"] = dict(
        artifact_kind="reference",
        origin="Crop from the owner-supplied DP-349 target image",
        source_reference=ROOT + "reference-target-page.png",
        retrieved_at=DATE,
        review_date=OWNER_REVIEW_DATE,
        license_or_terms=OWNER_DECISION,
        license_evidence=OWNER_EVIDENCE,
        attribution="Owner-supplied design crop covered by the owner's 2026-11-12 decision; illustrative only.",
        modifications="Extracted 246x168 JPEG crop from the provided design screenshot; embedded as base64 only in opt-in visual preview.",
        personal_data="Portrait of unidentified real person. Label is fictional.",
        redistribution_status="allowed",
        public_projection_status="No public build, API, sitemap or index; DP-349 opt-in private preview only.",
        blocker=None,
    )
    return rows
