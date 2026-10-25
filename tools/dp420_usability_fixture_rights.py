"""Curated DP-420 task-fixture licensing decision, separate from source rights."""


def dp420_usability_fixture_row(code_license: str) -> dict[str, dict]:
    """Record that the task descriptions are original, not copied source text."""
    return {
        "tests/fixtures/studio-garlasco-usability-v1.json": dict(
            artifact_kind="derived",
            origin="Dichiarazioni Pubbliche contributors",
            source_reference="project-authored DP-420 Studio operator task matrix referring to the existing corpus-search-benchmark-v1 gold by case ID; no copied source body",
            retrieved_at="2026-10-25",
            review_date="2026-10-25",
            license_or_terms=code_license,
            license_evidence="LICENSE (project-authored task matrix; reuses only internal benchmark case IDs)",
            attribution="Dichiarazioni Pubbliche contributors. Public figures and the Garlasco case are research subjects; no third-party quotation or transcript is reproduced.",
            modifications="Original operator acceptance prompts, source-link prerequisites, and accessibility modes composed from pre-existing internal benchmark identities.",
            personal_data="names of public figures referenced through benchmark IDs; no private information, media, transcript or copyrighted source text",
            redistribution_status="allowed",
            public_projection_status="internal private Studio QA fixture only; never a published statement or source",
            blocker=None,
        ),
    }
