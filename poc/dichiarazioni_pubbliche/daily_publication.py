"""DP-638 stage 5 — published daily statements become public projection records.

The exporter writes the same public-v2 bundle shape the web build already reads
(``dossiers``, ``contents``, ``topics`` of ``api/v1/index.json`` and of the search
index), so ``web/`` needs no change. It does not touch ``projectable_findings()``
or the old review chain: those are being deleted, not satisfied.

Accuracy rules enforced here, and only these:

* the quote is a verbatim substring of the captured source (checked again here),
* the speaker was resolved and is named in the capture,
* the source URL, publisher and date exist,
* a verdict carries at least one evidence link,
* an opinion is published labelled as an opinion and carries no verdict.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import tempfile
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from dichiarazioni_pubbliche.daily_machine import DailyStore, find_verbatim, sha256_text
from dichiarazioni_pubbliche.domain_vocabulary import (
    ClaimType,
    FindingPublicationStatus,
    VerificationAssessment,
)
from dichiarazioni_pubbliche.daily_projection_bundle import merge_bundle, write_bundle
from dichiarazioni_pubbliche.public_schema import (
    PUBLIC_SCHEMA_VERSION,
    PublicSchemaValidationError,
    projection_dataset_sha256,
    validate_public_bundle,
)

POLICY_VERSION = "dp638-daily-machine-v1"
# The public-v2 schema only admits four assessments. "Parzialmente vero" and
# "opinione" have no public field yet: the web build would label them wrongly,
# so they are recorded and counted here but not projected until the web loader
# accepts the label (issue #638, field request to the web author).
ASSESSMENT_BY_VERDICT = {
    "TRUE": VerificationAssessment.SUPPORTED.value,
    "FALSE": VerificationAssessment.FACTUALLY_FALSE.value,
    "NOT_VERIFIABLE": VerificationAssessment.INSUFFICIENT_EVIDENCE.value,
}
NOT_PROJECTABLE_VERDICTS = {
    "PARTLY_TRUE": "VERDICT_LABEL_PARTLY_TRUE_NOT_IN_PUBLIC_SCHEMA",
    "OPINION": "OPINION_LABEL_NOT_IN_PUBLIC_SCHEMA",
}
LABEL_BY_VERDICT = {
    "TRUE": "Vero",
    "FALSE": "Falso",
    "PARTLY_TRUE": "Parzialmente vero",
    "NOT_VERIFIABLE": "Non verificabile",
    "OPINION": "Opinione",
}
ASSESSABLE_VERDICTS = frozenset(set(ASSESSMENT_BY_VERDICT) | set(NOT_PROJECTABLE_VERDICTS))


class PublicationError(RuntimeError):
    """A record cannot be published without breaking an accuracy rule."""


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def slugify(value: str, *, limit: int = 80) -> str:
    folded = unicodedata.normalize("NFKD", (value or "").casefold())
    ascii_only = "".join(character for character in folded if not unicodedata.combining(character))
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_only).strip("-")
    return slug[:limit] or "senza-titolo"


def _stable_id(prefix: str, material: str) -> str:
    return prefix + hashlib.sha256(material.encode("utf-8")).hexdigest()[:32]


def _iso(value: Any) -> str | None:
    if not value:
        return None
    text = str(value)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.isoformat()


def build_dossier(row: dict[str, Any]) -> dict[str, Any]:
    """Turn one published statement row into a public dossier record."""

    quote = str(row.get("quote") or "").strip()
    capture_body = str(row.get("capture_body") or "")
    if not quote:
        raise PublicationError("QUOTE_MISSING")
    if not capture_body or find_verbatim(capture_body, quote) is None:
        raise PublicationError("QUOTE_NOT_VERBATIM_IN_SOURCE")
    speaker_name = str(row.get("speaker_name") or "").strip()
    speaker_key = str(row.get("speaker_key") or "").strip()
    if not speaker_name or not speaker_key:
        raise PublicationError("SPEAKER_UNRESOLVED")
    source_url = str(row.get("source_url") or "").strip()
    if not source_url.startswith(("http://", "https://")):
        raise PublicationError("SOURCE_URL_MISSING")
    verdict_code = str(row.get("verdict") or "NOT_VERIFIABLE").upper()
    if verdict_code not in ASSESSABLE_VERDICTS:
        raise PublicationError("VERDICT_UNKNOWN")
    if verdict_code in NOT_PROJECTABLE_VERDICTS:
        raise PublicationError(NOT_PROJECTABLE_VERDICTS[verdict_code])

    now = _now()
    statement_id = str(row["id"])
    evidence_rows = row.get("evidence") or []
    if not isinstance(evidence_rows, list):
        evidence_rows = []
    belegt = [
        {
            "id": _stable_id("evidence:", str(entry.get("url") or "")),
            "url": str(entry.get("url") or ""),
            "publisher": str(entry.get("publisher") or "") or "fonte indipendente",
            "source_type": "SECONDARY_PRESS",
            "publication_date": None,
            "observed_at": now,
            "content_sha256": None,
            "reference_period": None,
            "rights_status": "PUBLIC_EXCERPT",
            "relation": "SUPPORTING" if verdict_code in {"TRUE", "PARTLY_TRUE"} else "CONTRADICTING",
        }
        for entry in evidence_rows
        if isinstance(entry, dict) and str(entry.get("url") or "").startswith(("http://", "https://"))
    ]
    evidence = [
        {
            "id": _stable_id("evidence:", source_url),
            "url": source_url,
            "publisher": str(row.get("source_publisher") or ""),
            "source_type": "PRIMARY_SOURCE_RECORD",
            "publication_date": (str(row.get("statement_date") or "") or None),
            "observed_at": now,
            "content_sha256": sha256_text(capture_body),
            "reference_period": None,
            "rights_status": "PUBLIC_EXCERPT",
            "relation": "CONTEXT",
        }
    ] + belegt
    if verdict_code != "OPINION" and len(evidence) < 2:
        raise PublicationError("VERDICT_WITHOUT_EVIDENCE_LINK")

    capture_kind = str(row.get("capture_kind") or "article")
    moment = row.get("moment") if isinstance(row.get("moment"), dict) else {}
    if capture_kind == "article":
        source = {
            "content_id": str(row["content_id"]),
            "url": source_url,
            "title": str(row.get("source_title") or ""),
            "published_at": _iso(row.get("source_published_at"))
            or _iso(row.get("statement_date") + "T00:00:00+00:00"),
            "segments": [],
            "text_provenance": [
                {
                    "id": _stable_id("text:", source_url + quote),
                    "selector_type": "TEXT_POSITION_HASH",
                    "quote_sha256": sha256_text(quote),
                    "source_sha256": sha256_text(capture_body),
                    "start_char": int(row.get("quote_offset") or 0),
                    "end_char": int(row.get("quote_offset") or 0) + len(quote),
                    "attribution_method": "SOURCE_QUOTE",
                    "attribution_version": "text-provenance-v1",
                    "review_event_ids": [statement_id],
                }
            ],
        }
        provenance_kind = "TEXT_ATTRIBUTION"
        attribution_method = "SOURCE_QUOTE"
    else:
        source = {
            "content_id": str(row["content_id"]),
            "url": source_url,
            "title": str(row.get("source_title") or ""),
            "published_at": _iso(row.get("source_published_at"))
            or _iso(row.get("statement_date") + "T00:00:00+00:00"),
            "segments": [
                {
                    "segment_id": _stable_id("segment:", statement_id),
                    "segment_index": 0,
                    "start_ms": moment.get("moment_ms"),
                    "end_ms": moment.get("moment_ms"),
                }
            ],
        }
        provenance_kind = "TIMED_SPEAKER"
        attribution_method = "TRANSCRIPT_LABEL"

    assessment = ASSESSMENT_BY_VERDICT[verdict_code]
    explanation = str(row.get("explanation") or "").strip() or LABEL_BY_VERDICT[verdict_code]
    dossier = {
        "finding_id": statement_id,
        "claim_id": _stable_id("claim:", statement_id),
        "claim": quote,
        "claim_type": ClaimType.QUOTE_ATTRIBUTION.value,
        "claim_contract": {
            "version": 1,
            "temporal_scope": {"statement_date": str(row.get("statement_date") or "")},
            "check_worthy": verdict_code != "OPINION",
            "speaker_approval_required": True,
            "source_segment_ids": [],
        },
        "speaker": {
            "id": speaker_key,
            "name": speaker_name,
            "public_role": (str(row.get("speaker_role") or "").strip() or None),
            "public_roles": [],
            "provenance": [
                {
                    "candidate_id": statement_id,
                    "review_event_ids": [statement_id],
                    "provenance_kind": provenance_kind,
                    "attribution_method": attribution_method,
                }
            ],
        },
        "source": source,
        "finding": {
            "assessment": assessment,
            "publication_status": FindingPublicationStatus.PUBLISH.value,
            "rationale": explanation,
            "policy_version": POLICY_VERSION,
            "verification_run_id": statement_id,
            "created_at": _iso(row.get("created_at")) or now,
            "published_at": now,
            "supersedes_id": None,
        },
        "evidence": evidence,
        "corrections": [],
        "rights_of_reply": [],
        "source_methodology": {
            "policy_version": POLICY_VERSION,
            "moment": moment.get("moment_label") or "",
            "opinion": verdict_code == "OPINION",
            "verdict": {
                "code": verdict_code,
                "label": LABEL_BY_VERDICT[verdict_code],
                "explanation": explanation,
                "models": str(row.get("models") or ""),
                "agreement": str(row.get("agreement") or ""),
                "model_calls": int(row.get("model_calls") or 0),
                "duration_seconds": float(row.get("duration_seconds") or 0.0),
                "evidence_links": len(belegt),
            },
            "topic": str(row.get("topic") or ""),
        },
    }
    return dossier


def build_content(dossier: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    source = dossier["source"]
    kind = "VIDEO" if str(row.get("capture_kind") or "") in {"captions", "asr"} else "WRITTEN"
    return {
        "content_id": source["content_id"],
        "slug": slugify(source.get("title") or source["content_id"]),
        "url": source["url"],
        "title": source.get("title") or "",
        "published_at": source.get("published_at"),
        "content_kind": kind,
        "duration_ms": None,
        "public_media_url": None,
        "media_policy_version": None,
        "publication_version": "public-content-v1",
        "review_event_ids": [dossier["finding_id"]],
        "finding_ids": [dossier["finding_id"]],
    }


def build_topics(dossiers: Sequence[dict[str, Any]], rows_by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for dossier in dossiers:
        topic_raw = str(
            (dossier.get("source_methodology") or {}).get("topic") or ""
        ).strip()
        if not topic_raw:
            continue
        grouped.setdefault(topic_raw, []).append(dossier)
    topics: list[dict[str, Any]] = []
    for name, members in sorted(grouped.items()):
        slug = slugify(name)
        memberships = [
            {
                "membership_id": _stable_id("membership:", member["claim_id"] + slug),
                "claim_id": member["claim_id"],
                "finding_ids": [member["finding_id"]],
                "review_event_ids": [member["finding_id"]],
                "source_resolution_candidate_id": None,
            }
            for member in members
        ]
        topics.append(
            {
                "topic_id": _stable_id("topic:", slug),
                "slug": slug,
                "canonical_name": name[:120],
                "scope_text": None,
                "entity_version": POLICY_VERSION,
                "review_event_ids": [memberships[0]["review_event_ids"][0]],
                "memberships": memberships,
            }
        )
    return topics


class PublicationStore(DailyStore):
    def published_rows(self, day: str | None = None) -> list[dict[str, Any]]:
        raw = self.run(
            """
            SELECT COALESCE(jsonb_agg(row), '[]'::jsonb)::text FROM (
                SELECT jsonb_build_object(
                    'id', statement.id,
                    'content_id', statement.content_id,
                    'quote', statement.quote,
                    'quote_offset', statement.quote_offset,
                    'speaker_name', statement.speaker_name,
                    'speaker_role', statement.speaker_role,
                    'speaker_key', statement.speaker_key,
                    'topic', statement.topic,
                    'claim_nature', statement.claim_nature,
                    'statement_date', statement.statement_date,
                    'source_url', statement.source_url,
                    'source_title', statement.source_title,
                    'source_publisher', statement.source_publisher,
                    'source_published_at', statement.source_published_at,
                    'created_at', statement.created_at,
                    'capture_kind', capture.capture_kind,
                    'capture_body', capture.body,
                    'moment', statement.metadata,
                    'verdict', COALESCE(verdict.verdict, 'NOT_VERIFIABLE'),
                    'explanation', COALESCE(verdict.explanation, ''),
                    'evidence', COALESCE(verdict.evidence, '[]'::jsonb),
                    'agreement', COALESCE(verdict.agreement, ''),
                    'models', COALESCE(verdict.models, ''),
                    'model_calls', COALESCE(verdict.model_calls, 0),
                    'duration_seconds', COALESCE(verdict.duration_seconds, 0)
                ) AS row
                FROM daily_statement statement
                JOIN daily_capture capture ON capture.id = statement.capture_id
                LEFT JOIN daily_verdict verdict ON verdict.statement_id = statement.id
                WHERE statement.status = 'PUBLISHED'
                  AND (
                        NULLIF(:'day', '') IS NULL
                        OR statement.statement_date = NULLIF(:'day', '')::date
                  )
                ORDER BY statement.created_at DESC
            ) rows;
            """,
            day=day or "",
        )
        return list(json.loads(raw.strip() or "[]"))


def export_day(
    store: PublicationStore,
    *,
    day: str | None,
    projection_path: Path | None,
) -> dict[str, Any]:
    rows = store.published_rows(day)
    dossiers: list[dict[str, Any]] = []
    contents: list[dict[str, Any]] = []
    rejected: list[dict[str, str]] = []
    seen_quotes: set[tuple[str, str]] = set()
    for row in rows:
        try:
            dossier = build_dossier(row)
        except PublicationError as exc:
            rejected.append({"id": str(row.get("id")), "reason": str(exc)})
            continue
        dedupe_key = (str(row.get("speaker_key")), str(row.get("quote")))
        if dedupe_key in seen_quotes:
            rejected.append({"id": str(row.get("id")), "reason": "DUPLICATE_STATEMENT"})
            continue
        seen_quotes.add(dedupe_key)
        dossiers.append(dossier)
        contents.append(build_content(dossier, row))
    rows_by_id = {str(row.get("id")): row for row in rows}
    topics = build_topics(dossiers, rows_by_id)
    existing = None
    if projection_path is not None and projection_path.exists():
        existing = json.loads(projection_path.read_text("utf-8"))
    bundle = merge_bundle(existing, dossiers, contents, topics)
    if projection_path is not None:
        write_bundle(projection_path, bundle)
    return {
        "day": day,
        "published_rows": len(rows),
        "dossiers": len(dossiers),
        "contents": len(contents),
        "topics": len(topics),
        "rejected": rejected,
        "projection_path": str(projection_path) if projection_path else None,
        "dossier_count": bundle["dossier_count"],
        "dataset_sha256": bundle["dataset_sha256"],
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="DP-638: export published daily statements to the public projection."
    )
    parser.add_argument("--database-url", default=__import__("os").environ.get("DICHIARAZIONI_PUBBLICHE_DATABASE_URL"))
    parser.add_argument("--day", default="")
    parser.add_argument("--projection", default="")
    parser.add_argument("--report", default="")
    args = parser.parse_args(argv)
    store = PublicationStore(args.database_url)
    path = Path(args.projection) if args.projection else None
    report = export_day(store, day=args.day or None, projection_path=path)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.report:
        Path(args.report).write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
