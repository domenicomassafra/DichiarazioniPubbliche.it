"""Pure allowlisted Statement v3 API wire representation. No I/O or grants."""

from __future__ import annotations

from typing import Any


def statement_v3_wire_record(record: dict[str, Any]) -> dict[str, Any]:
    """Explicit public allowlist; never return the source or internal review rows."""
    locator = record["locator"]
    public_locator = {
        "start_char": locator["start_char"],
        "end_char": locator["end_char"],
    }
    if record["source_kind"] == "TIMED":
        public_locator.update({
            "segment_id": locator["segment_id"],
            "start_ms": locator["start_ms"],
            "end_ms": locator["end_ms"],
        })
    representations: dict[str, dict[str, Any] | None] = {}
    for name in ("summary", "translation"):
        value = record[name]
        if value is None:
            representations[name] = None
            continue
        # A secondary representation has its own type and cannot occupy the
        # "original" field, regardless of its content.
        derived = {
            "wording_type": value["wording_type"],
            "text": value["text"],
            "source_quote_sha256": value["source_quote_sha256"],
        }
        if name == "translation":
            derived["source_language"] = value["source_language"]
            derived["language"] = value["language"]
        representations[name] = derived
    return {
        "statement_id": record["statement_id"],
        "version_id": record["version_id"],
        "statement_date": record["statement_date"],
        "person": {
            "id": record["person_id"],
            "name": record["speaker_name"],
        },
        "source": {
            "content_id": record["content_id"],
            "title": record["source_title"],
            "url": record["source_url"],
            "version_id": record["source_version"],
            "sha256": record["source_sha256"],
            "kind": record["source_kind"],
        },
        "original": {
            "wording_type": "VERBATIM_ORIGINAL",
            "text": record["original_text"],
            "language": record["language"],
            "quote_sha256": record["quote_sha256"],
            "locator": public_locator,
        },
        "speech_act": record["speech_act"],
        "endorsed": record["endorsed"],
        "finding_id": record["finding_id"],
        **representations,
    }
