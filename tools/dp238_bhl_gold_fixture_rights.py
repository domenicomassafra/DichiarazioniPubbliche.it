"""DP-238: curated rights metadata for the held BHL OCR reference fixture."""


def dp238_bhl_gold_row() -> dict[str, dict]:
    return {
        "tests/fixtures/dp238_bhl_8992356_gold_v1.json": dict(
            artifact_kind="derived",
            origin="Dichiarazioni Pubbliche contributors; manually compared with BHL scan and IMPACT-BHL expert-corrected PAGE XML",
            source_reference=(
                "BHL Birds of Great Britain and Ireland vol. 2 (1908), page 8992356: "
                "https://www.biodiversitylibrary.org/bibliography/8651 ; "
                "IMPACT-BHL dataset revision f57bb9e58785a3f9266c05880092ec76720450e5: "
                "https://huggingface.co/datasets/finebooks/bhl-impact-gt"
            ),
            retrieved_at="2026-10-22",
            review_date="2026-10-22",
            license_or_terms="IMPACT-BHL PAGE XML: CC-BY-3.0; BHL volume 2 scan: NOT_IN_COPYRIGHT (item-scoped)",
            license_evidence=(
                "https://huggingface.co/datasets/finebooks/bhl-impact-gt ; "
                "https://about.biodiversitylibrary.org/help/copyright-and-reuse/"
            ),
            attribution=(
                "IMPACT Centre of Competence and Biodiversity Heritage Library (2012), "
                "Birds of Great Britain and Ireland vol. 2 (1908); "
                "holding institution American Museum of Natural History Library."
            ),
            modifications=(
                "Project-authored critical-span labels, approximate raster ROIs and pinned "
                "source hashes manually cross-checked against the external gold; "
                "no source raster, PAGE XML or full OCR text is embedded."
            ),
            personal_data="none; historical ornithology page and OCR quality metadata only",
            redistribution_status="metadata-only",
            public_projection_status="HOLD: technical OCR comparison only, never a public quote or editorial source",
            blocker=(
                "No current operational source-use record or public excerpt clearance for an "
                "editorial Capture; critical OCR number 81 failed the independent gold. "
                "Preserve HOLD_PRIVATE_GOLD_FAILURE and source-specific rights gates."
            ),
        ),
    }
