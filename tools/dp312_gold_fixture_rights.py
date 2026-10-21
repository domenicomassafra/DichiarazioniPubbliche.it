"""DP-312 separately curated rights decision for original multilingual test gold."""


def dp312_gold_row(fixture_policy: str) -> dict[str, dict]:
    return {
        "tests/fixtures/dp312_multilingual_gold_v1.json": dict(
            artifact_kind="synthetic",
            origin="Dichiarazioni Pubbliche contributors",
            source_reference="original, fictional IT/EN/DE/FR speech-act contrast labels fixed in-repo for DP-312",
            retrieved_at="2026-10-20",
            review_date="2026-10-20",
            license_or_terms=fixture_policy,
            license_evidence="docs/licensing/README.md#synthetic-fixture-policy",
            attribution="No third-party attribution: fictional words and labels; no independent human review.",
            modifications="Original deterministic lexical contrasts and negative translations; no real speech copied.",
            personal_data="none; fictional source and utterer identifiers only",
            redistribution_status="allowed",
            public_projection_status="private regression fixture; never a publishable source, Finding or Statement",
            blocker=None,
        ),
    }
