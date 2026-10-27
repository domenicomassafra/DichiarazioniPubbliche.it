"""Source-validated public Statement v3 read models (DP-435/436/437).

The public_api module re-exports these functions for existing callers. Runtime
imports of public_api preserve its public error type and testable validation
seam without introducing import cycles when the v3 module is imported first.
"""
from __future__ import annotations

import copy
import re
from typing import Any

from .public_schema import PUBLIC_STATEMENT_SCHEMA_VERSION, PublicSchemaValidationError
from .public_statement_v3_wire import statement_v3_wire_record as _statement_v3_record


# DP-435/436/437 source-validated Statement v3 read models.
def _statement_v3_snapshot(
    bundle: dict[str, Any], *, allow_statement_v3: bool,
    current_public_dataset_sha256: str | None,
) -> dict[str, Any]:
    from . import public_api as _api
    if not allow_statement_v3:
        raise _api._unavailable()
    # Compare against the separately authenticated current release.
    if (not isinstance(current_public_dataset_sha256, str)
        or re.fullmatch(r"[0-9a-f]{64}", current_public_dataset_sha256) is None):
        raise _api._unavailable()
    try:
        if not isinstance(bundle, dict) or bundle.get("schema_version") != PUBLIC_STATEMENT_SCHEMA_VERSION:
            raise _api._unavailable()
        # Validate and serialize one detached public snapshot. The caller may
        # still mutate the original bundle after validation (e.g. during a
        # rights withdrawal); never emit its new, unverified quote or identity
        # under the old dataset fingerprint.
        validated = _api.validate_public_bundle(
            copy.deepcopy(bundle), allow_statement_v3=True
        )
        if validated["dataset_sha256"] != current_public_dataset_sha256:
            raise _api._unavailable()
        for record in validated["statements"]:
            _api._validate_statement_v3_source_url(record["source_url"])
        return validated
    except (PublicSchemaValidationError, KeyError, TypeError, ValueError) as exc:
        raise _api._unavailable() from exc


def list_public_statements_v3(
    bundle: dict[str, Any], *, allow_statement_v3: bool = False,
    current_public_dataset_sha256: str | None = None,
) -> dict[str, Any]:
    """Build an opt-in read payload pinned to the independently current release."""
    validated = _statement_v3_snapshot(
        bundle, allow_statement_v3=allow_statement_v3,
        current_public_dataset_sha256=current_public_dataset_sha256,
    )
    statements = [
        _statement_v3_record(record)
        for record in sorted(
            validated["statements"],
            key=lambda record: (record["statement_id"], record["version_id"]),
        )
    ]
    return {
        "meta": {
            "public_schema_version": validated["schema_version"],
            "dataset_sha256": validated["dataset_sha256"],
            "generated_at": validated["generated_at"],
            "count": len(statements),
        },
        "data": statements,
    }


def get_public_statement_v3(
    bundle: dict[str, Any], statement_id: str, *, allow_statement_v3: bool = False,
    current_public_dataset_sha256: str | None = None,
) -> dict[str, Any]:
    """Read only from the independently current release; no historical fallback."""
    from . import public_api as _api
    validated = _statement_v3_snapshot(
        bundle, allow_statement_v3=allow_statement_v3,
        current_public_dataset_sha256=current_public_dataset_sha256,
    )
    record = next(
        (item for item in validated["statements"] if item["statement_id"] == statement_id),
        None,
    )
    if record is None:
        raise _api._not_found()
    return {
        "meta": {
            "public_schema_version": validated["schema_version"],
            "dataset_sha256": validated["dataset_sha256"],
            "generated_at": validated["generated_at"],
        },
        "data": _statement_v3_record(record),
    }


def list_public_opinions_by_person_content_v3(
    bundle: dict[str, Any],
    *,
    allow_statement_v3: bool = False,
    current_public_dataset_sha256: str | None = None,
    person_id: str | None = None,
    content_id: str | None = None,
) -> dict[str, Any]:
    """Offline opt-in public opinion archive grouped by Person and Content.

    This is a pure read model, NOT an HTTP endpoint or publication authority.
    Only source/context/attribution/rights-gated v3 original Statements can
    enter. OPINION alone is not a verdict and an unendorsed/quoted/critical
    Statement cannot become the recorded person's expressed position.

    The caller MUST obtain current_public_dataset_sha256 separately from
    the currently authorized release. A historical but internally valid
    snapshot cannot be admitted after the published set changes. Pinning a
    hash supplied by the same untrusted bundle is NOT a rights attestation.
    """
    from . import public_api as _api
    if not allow_statement_v3:
        raise _api._unavailable()
    for name, value in (("person_id", person_id), ("content_id", content_id)):
        if value is not None and (
            not isinstance(value, str) or _api._ID_TOKEN_RE.fullmatch(value) is None
        ):
            raise _api._bad_request(f"Invalid {name} identifier")
    if (not isinstance(current_public_dataset_sha256, str)
        or re.fullmatch(r"[0-9a-f]{64}", current_public_dataset_sha256) is None):
        raise _api._unavailable()
    try:
        # No mutable source/proof callback or iterator should modify original
        # wording between validation and response assembly.
        snapshot = _statement_v3_snapshot(
            copy.deepcopy(bundle), allow_statement_v3=True,
            current_public_dataset_sha256=current_public_dataset_sha256,
        )
    except (TypeError, ValueError, RecursionError) as exc:
        raise _api._unavailable() from exc
    if snapshot["dataset_sha256"] != current_public_dataset_sha256:
        raise _api._unavailable()

    # The bundle can also contain publicly reportable quoted/critical speech
    # and factual assertions. None of those are endorsed public opinions.
    # The source-level gates already determined publishability; do not infer
    # it from person names, source title, a Finding or a model summary.
    grouped: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for row in snapshot["statements"]:
        if row["speech_act"] != "OPINION" or row["endorsed"] is not True:
            continue
        if person_id is not None and row["person_id"] != person_id:
            continue
        if content_id is not None and row["content_id"] != content_id:
            continue
        grouped.setdefault(row["person_id"], {}).setdefault(
            row["content_id"], [],
        ).append(_statement_v3_record(row))

    people: list[dict[str, Any]] = []
    count = 0
    content_groups = 0
    for speaker_id, contents in sorted(grouped.items()):
        public_contents = []
        for source_id, statements in sorted(contents.items()):
            statements.sort(
                key=lambda item: (
                    item["statement_date"], item["statement_id"], item["version_id"],
                ), reverse=True,
            )
            public_contents.append({"content_id": source_id, "statements": statements})
            count += len(statements)
            content_groups += 1
        people.append({"person_id": speaker_id, "contents": public_contents})
    return {
        "meta": {
            "public_schema_version": snapshot["schema_version"],
            "dataset_sha256": snapshot["dataset_sha256"],
            "generated_at": snapshot["generated_at"],
            "scope": "ENDORSED_OPINIONS_ONLY",
            "count": count,
            "person_count": len(people),
            "content_group_count": content_groups,
        },
        "data": people,
    }
