"""Curated multilingual fixture rights: DP-312 synthetic and DP-160 EUR-Lex."""


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
        "tests/fixtures/dp160_eurlex_article113_v1.json": dict(
            artifact_kind="reference",
            origin="European Union; Official Journal, Regulation (EU) 2024/1689, Article 113",
            source_reference="https://eur-lex.europa.eu/eli/reg/2024/1689/oj/ita and https://eur-lex.europa.eu/eli/reg/2024/1689/oj/eng",
            retrieved_at="2026-10-23",
            review_date="2026-10-23",
            license_or_terms="EUR-Lex legal-document reuse permitted under Decision 2011/833/EU; document-specific exclusions apply",
            license_evidence="https://eur-lex.europa.eu/content/legal-notice/legal-notice.html?locale=en",
            attribution="European Union, OJ L 2024/1689 of 12 July 2024, Article 113, original IT/EN; cited ELI and source URLs; test-only edited contrasts clearly labelled",
            modifications="Two short original-language quotations excerpted; invalid alternatives and research questions authored as adversarial tests, not source quotations",
            personal_data="none; legal clauses only, no private persons, images or third-party media",
            redistribution_status="allowed",
            public_projection_status="private offline regression only; no licensed-source ingestion or publication authority",
            blocker=None,
        ),
    }
