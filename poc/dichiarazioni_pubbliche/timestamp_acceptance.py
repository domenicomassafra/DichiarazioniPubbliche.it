"""Fail-closed timestamp acceptance for DP-207's deterministic real-content fixture.

The adapter deliberately does *not* run a model.  It turns the curated ContentAudit
coverage into immutable canonical media ranges, verifies that every claim timestamp is
contained by its claimed segment provenance, and can persist the result into an isolated
PostgreSQL database for replay/read-back acceptance.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dichiarazioni_pubbliche.claim_contract import NON_FACTUAL_CLAIM_TYPES
from dichiarazioni_pubbliche.claim_runtime import ExtractedAtomicClaim, deterministic_claim_id
from dichiarazioni_pubbliche.content_audit import validate_audit
from dichiarazioni_pubbliche.queue_runtime import QueueRuntimeStore


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_AUDIT = ROOT / "poc/content/raffagiulians-bollo-2026/content-audit.json"
DEFAULT_TRANSCRIPT = ROOT / "poc/content/raffagiulians-bollo-2026/raw/transcript.json"
CONTENT_ID = "content:dp207:raffagiulians-bollo-2026"
SOURCE_ID = "source:dp207:raffagiulians"
VARIANT_ID = "variant:dp207:raffagiulians-bollo-2026"
PROMPT_VERSION = "dp207-fixture-v1"
MODEL_ID = "fixture:content-audit"
TIMESTAMP_TOLERANCE_MS = 500

_M_SS = re.compile(r"^(?P<m>\d+):(?P<s>[0-5]\d)(?:\.(?P<ms>\d{1,3}))?$")
_H_MM_SS = re.compile(
    r"^(?P<h>\d+):(?P<m>[0-5]\d):(?P<s>[0-5]\d)(?:\.(?P<ms>\d{1,3}))?$"
)
_TIMESTAMPED_LINE = re.compile(
    r"^\s*(?P<ts>\d+:\d{2}(?:\.\d{1,3})?)\s+(?P<text>.*)$"
)


def parse_media_timestamp(value: str | None) -> int:
    """Parse a documented media timestamp into milliseconds, never defaulting to zero."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError("TIMESTAMP_MISSING")
    value = value.strip()
    match = _H_MM_SS.fullmatch(value)
    if match:
        total = (
            int(match.group("h")) * 3600
            + int(match.group("m")) * 60
            + int(match.group("s"))
        )
        millis = _fraction_ms(match.group("ms"))
        return total * 1000 + millis
    match = _M_SS.fullmatch(value)
    if match:
        total = int(match.group("m")) * 60 + int(match.group("s"))
        millis = _fraction_ms(match.group("ms"))
        return total * 1000 + millis
    raise ValueError("TIMESTAMP_INVALID")


def _fraction_ms(value: str | None) -> int:
    if value is None:
        return 0
    return int(value.ljust(3, "0"))


@dataclass(frozen=True)
class AcceptedSegment:
    segment_id: str
    index: int
    start_ms: int
    end_ms: int
    speaker: str
    kind: str
    claim_ids: tuple[str, ...]
    private_text: str


@dataclass(frozen=True)
class AcceptedClaim:
    fixture_claim_id: str
    claim_id: str
    normalized_claim: str
    claim_type: str
    speaker: str
    source_timestamp: str
    source_timestamp_ms: int
    start_ms: int
    end_ms: int
    segment_ids: tuple[str, ...]
    segment_indices: tuple[int, ...]
    numeric_sensitive: bool
    publication_blocked: bool
    input_sha256: str


@dataclass(frozen=True)
class FixtureAcceptance:
    audit_sha256: str
    transcript_file_sha256: str | None
    transcript_content_sha256: str
    duration_ms: int
    observation_time: str | None
    segments: tuple[AcceptedSegment, ...]
    claims: tuple[AcceptedClaim, ...]


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _private_text_by_timestamp(transcript: dict[str, Any] | None) -> dict[str, str]:
    if not transcript:
        return {}
    result: dict[str, str] = {}
    for line in str(transcript.get("timestamped_text") or "").splitlines():
        match = _TIMESTAMPED_LINE.match(line)
        if match:
            result.setdefault(match.group("ts"), match.group("text").strip())
    return result


def load_fixture_acceptance(
    audit_path: Path = DEFAULT_AUDIT,
    transcript_path: Path | None = DEFAULT_TRANSCRIPT,
) -> FixtureAcceptance:
    audit_bytes = audit_path.read_bytes()
    audit = json.loads(audit_bytes)
    errors = validate_audit(audit)
    if errors:
        raise ValueError("AUDIT_INVALID:" + ";".join(errors))
    claims_raw = list(audit.get("claims") or [])
    coverage = list(audit.get("segment_coverage") or [])
    if len(claims_raw) != 36 or len(coverage) != 84:
        raise ValueError(
            f"FIXTURE_SHAPE_INVALID:claims={len(claims_raw)},segments={len(coverage)}"
        )

    duration_ms = int(round(float(audit["content"]["duration_seconds"]) * 1000))
    if duration_ms != 444_840:
        raise ValueError(f"FIXTURE_DURATION_INVALID:{duration_ms}")

    transcript: dict[str, Any] | None = None
    transcript_file_sha256: str | None = None
    if transcript_path is not None and transcript_path.exists():
        transcript_bytes = transcript_path.read_bytes()
        transcript_file_sha256 = _sha256_bytes(transcript_bytes)
        transcript = json.loads(transcript_bytes)
        if int(round(float(transcript.get("duration_seconds") or 0) * 1000)) != duration_ms:
            raise ValueError("TRANSCRIPT_DURATION_DRIFT")

    private_text = _private_text_by_timestamp(transcript)
    starts = [int(row["start_seconds"]) * 1000 for row in coverage]
    if starts != sorted(starts) or starts[0] != 0 or len(starts) != len(set(starts)):
        raise ValueError("SEGMENT_STARTS_INVALID")

    segments: list[AcceptedSegment] = []
    for index, row in enumerate(coverage):
        if int(row.get("index", -1)) != index:
            raise ValueError("SEGMENT_INDEX_INVALID")
        timestamp_ms = parse_media_timestamp(str(row.get("timestamp") or ""))
        start_ms = starts[index]
        if timestamp_ms != start_ms:
            raise ValueError(f"SEGMENT_TIMESTAMP_DRIFT:{index}")
        end_ms = starts[index + 1] if index + 1 < len(starts) else duration_ms
        if not (0 <= start_ms <= end_ms <= duration_ms):
            raise ValueError(f"SEGMENT_RANGE_INVALID:{index}")
        segment_id = f"segment:dp207:{index:03d}"
        segments.append(
            AcceptedSegment(
                segment_id=segment_id,
                index=index,
                start_ms=start_ms,
                end_ms=end_ms,
                speaker=str(row.get("speaker") or "").strip(),
                kind=str(row.get("kind") or "").strip(),
                claim_ids=tuple(str(value) for value in row.get("claim_ids") or []),
                private_text=private_text.get(str(row.get("timestamp") or ""), ""),
            )
        )

    claims: list[AcceptedClaim] = []
    for raw in claims_raw:
        fixture_claim_id = str(raw["id"])
        mapped = [segment for segment in segments if fixture_claim_id in segment.claim_ids]
        if not mapped:
            raise ValueError(f"CLAIM_SEGMENT_REQUIRED:{fixture_claim_id}")
        timestamp = str(raw.get("timestamp") or "")
        timestamp_ms = parse_media_timestamp(timestamp)
        start_ms = min(segment.start_ms for segment in mapped)
        end_ms = max(segment.end_ms for segment in mapped)
        if not any(
            segment.start_ms - TIMESTAMP_TOLERANCE_MS
            <= timestamp_ms
            <= segment.end_ms + TIMESTAMP_TOLERANCE_MS
            for segment in mapped
        ):
            raise ValueError(f"TIMESTAMP_UNVERIFIED:{fixture_claim_id}")
        if not (0 <= start_ms <= end_ms <= duration_ms):
            raise ValueError(f"CLAIM_RANGE_INVALID:{fixture_claim_id}")

        segment_ids = tuple(segment.segment_id for segment in mapped)
        segment_indices = tuple(segment.index for segment in mapped)
        window_material = json.dumps(
            {
                "transcript_content_sha256": audit["transcript_provenance"]["content_sha256"],
                "segments": [
                    [segment.segment_id, segment.start_ms, segment.end_ms]
                    for segment in mapped
                ],
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        input_sha256 = _sha256_bytes(window_material)
        extracted = ExtractedAtomicClaim(
            normalized_claim=str(raw["normalized_claim"]),
            claim_type=str(raw["type"]),
            check_worthy=str(raw["type"]) not in {kind.value for kind in NON_FACTUAL_CLAIM_TYPES},
            numeric_sensitive=bool(raw.get("numeric_sensitive")),
            speaker=str(raw.get("speaker") or ""),
            source_timestamp=timestamp,
            source_segment_indices=segment_indices,
        )
        claim_id = deterministic_claim_id(
            content_id=CONTENT_ID,
            window_sha256=input_sha256,
            prompt_version=PROMPT_VERSION,
            model=MODEL_ID,
            claim=extracted,
        )
        claims.append(
            AcceptedClaim(
                fixture_claim_id=fixture_claim_id,
                claim_id=claim_id,
                normalized_claim=extracted.normalized_claim,
                claim_type=extracted.claim_type,
                speaker=extracted.speaker,
                source_timestamp=timestamp,
                source_timestamp_ms=timestamp_ms,
                start_ms=start_ms,
                end_ms=end_ms,
                segment_ids=segment_ids,
                segment_indices=segment_indices,
                numeric_sensitive=extracted.numeric_sensitive,
                publication_blocked=False,
                input_sha256=input_sha256,
            )
        )

    if len({claim.claim_id for claim in claims}) != 36:
        raise ValueError("CLAIM_ID_COLLISION")
    numeric = {claim.fixture_claim_id for claim in claims if claim.numeric_sensitive}
    if not {"C07", "C08", "C09"}.issubset(numeric):
        raise ValueError("NUMERIC_ASR_ACCEPTANCE_MISSING")
    inserted = [segment for segment in segments if 414_000 <= segment.start_ms <= 434_000]
    if not inserted or any(segment.speaker != "Giorgia Meloni (inserted clip)" for segment in inserted):
        raise ValueError("INSERTED_CLIP_ATTRIBUTION_INVALID")

    model_receipt = (transcript or {}).get("model_receipt") or {}
    return FixtureAcceptance(
        audit_sha256=_sha256_bytes(audit_bytes),
        transcript_file_sha256=transcript_file_sha256,
        transcript_content_sha256=str(audit["transcript_provenance"]["content_sha256"]),
        duration_ms=duration_ms,
        observation_time=str(model_receipt.get("completed_at") or "") or None,
        segments=tuple(segments),
        claims=tuple(claims),
    )


def _dollar(value: str) -> str:
    tag = "$dp207$"
    if tag in value:
        raise ValueError("AA207_DOLLAR_QUOTE_COLLISION")
    return f"{tag}{value}{tag}"


def persist_fixture_canary(store: QueueRuntimeStore, fixture: FixtureAcceptance) -> dict[str, Any]:
    """Persist/replay the fixture in an *isolated* database supplied by the caller."""
    store.run(
        """
        INSERT INTO source (id, canonical_name, source_type, canonical_url, language)
        VALUES (:'id', 'Raffaele Giuliani — DP-207 fixture', 'SOCIAL_VIDEO',
                'https://www.tiktok.com/@raffagiulians/video/7686596204074896672', 'it')
        ON CONFLICT (id) DO NOTHING;
        """,
        id=SOURCE_ID,
    )
    store.run(
        """
        INSERT INTO content_item (
            id, source_id, source_external_id, canonical_url, title, published_at,
            duration_ms, content_sha256, rights_status, processing_status, metadata
        ) VALUES (
            :'id', :'source_id', 'dp207-raffagiulians-bollo-2026',
            'https://www.tiktok.com/@raffagiulians/video/7686596204074896672',
            'DP-207 deterministic timestamp acceptance fixture',
            '2026-09-21T00:00:00Z', :'duration_ms'::bigint, :'content_sha256',
            'UNKNOWN', 'TRANSCRIPT_CANDIDATE_READY',
            jsonb_build_object('fixture', true, 'ticket', 'DP-207')
        ) ON CONFLICT (id) DO NOTHING;
        """,
        id=CONTENT_ID,
        source_id=SOURCE_ID,
        duration_ms=fixture.duration_ms,
        content_sha256=fixture.transcript_content_sha256,
    )

    transcript_text = "\n".join(segment.private_text for segment in fixture.segments if segment.private_text)
    transcript_hash = _sha256_bytes(transcript_text.encode())
    observed_at = fixture.observation_time or "2026-09-21T18:52:13Z"
    store.run(
        """
        INSERT INTO transcript_variant (
            id, content_id, provider_id, source_kind, language, model_name,
            raw_text_sha256, raw_text, created_at, metadata
        ) VALUES (
            :'id', :'content_id', 'dp207-fixture', 'PRIVATE_REAL_FIXTURE', 'it',
            'fixture:content-audit', :'raw_hash', :'raw_text', :'observed_at'::timestamptz,
            jsonb_build_object('ticket', 'DP-207', 'no_provider_call', true)
        ) ON CONFLICT (id) DO NOTHING;
        """,
        id=VARIANT_ID,
        content_id=CONTENT_ID,
        raw_hash=transcript_hash,
        raw_text=transcript_text,
        observed_at=observed_at,
    )

    segment_rows = [
        {
            "id": segment.segment_id,
            "transcript_id": f"transcript:{segment.index:03d}",
            "index": segment.index,
            "start_ms": segment.start_ms,
            "end_ms": segment.end_ms,
            "speaker": segment.speaker,
            "text": segment.private_text,
        }
        for segment in fixture.segments
    ]
    encoded_segments = _dollar(json.dumps(segment_rows, ensure_ascii=False, separators=(",", ":")))
    store.run_literal(
        f"""
        WITH input AS (
          SELECT * FROM jsonb_to_recordset({encoded_segments}::jsonb) AS x(
            id text, transcript_id text, index integer, start_ms bigint, end_ms bigint,
            speaker text, text text
          )
        ), transcript_insert AS (
          INSERT INTO transcript_segment (
            id, variant_id, segment_index, start_ms, end_ms, speaker_label, text, metadata
          ) SELECT transcript_id, '{VARIANT_ID}', index, start_ms, end_ms, speaker, text,
                   jsonb_build_object('ticket','DP-207')
            FROM input ON CONFLICT (id) DO NOTHING RETURNING id
        ), canonical_insert AS (
          INSERT INTO canonical_transcript_segment (
            id, content_id, segment_index, start_ms, end_ms, speaker_label,
            canonical_text, transcript_status, publication_blocked, sensitive_signature
          ) SELECT id, '{CONTENT_ID}', index, start_ms, end_ms, speaker, text,
                   'RESOLVED', false, '[]'::jsonb
            FROM input ON CONFLICT (id) DO NOTHING RETURNING id
        )
        INSERT INTO canonical_segment_candidate (canonical_segment_id, transcript_segment_id)
        SELECT id, transcript_id FROM input ON CONFLICT DO NOTHING;
        """
    )

    claim_rows = []
    for claim in fixture.claims:
        check_worthy = claim.claim_type not in {kind.value for kind in NON_FACTUAL_CLAIM_TYPES}
        claim_rows.append(
            {
                "id": claim.claim_id,
                "content_id": CONTENT_ID,
                "normalized_claim": claim.normalized_claim,
                "claim_type": claim.claim_type,
                "temporal_scope": {
                    "source_timestamp": claim.source_timestamp,
                    "source_timestamp_ms": claim.source_timestamp_ms,
                    "start_ms": claim.start_ms,
                    "end_ms": claim.end_ms,
                },
                "check_worthy": check_worthy,
                "extraction_model": MODEL_ID,
                "extraction_version": PROMPT_VERSION,
                "metadata": {
                    "fixture_claim_id": claim.fixture_claim_id,
                    "input_sha256": claim.input_sha256,
                    "timestamp_validation": "ACCEPTED",
                    "timestamp_tolerance_ms": TIMESTAMP_TOLERANCE_MS,
                    "numeric_sensitive": claim.numeric_sensitive,
                    "transcript_publication_blocked": claim.publication_blocked,
                    "speaker_label": claim.speaker,
                    "no_provider_call": True,
                },
                "segment_ids": list(claim.segment_ids),
            }
        )
    first_insert = store.insert_atomic_claims(claim_rows)
    replay_insert = store.insert_atomic_claims(claim_rows)

    raw = store.run(
        """
        SELECT json_build_object(
          'claims', (SELECT count(*) FROM atomic_claim WHERE content_id=:'content_id'),
          'edges', (SELECT count(*) FROM claim_segment cs JOIN atomic_claim c ON c.id=cs.claim_id WHERE c.content_id=:'content_id'),
          'segments', (SELECT count(*) FROM canonical_transcript_segment WHERE content_id=:'content_id'),
          'variant_candidates', (
             SELECT count(*) FROM canonical_segment_candidate cc
             JOIN canonical_transcript_segment c ON c.id=cc.canonical_segment_id
             JOIN transcript_segment ts ON ts.id=cc.transcript_segment_id
             WHERE c.content_id=:'content_id' AND ts.variant_id=:'variant_id'
          ),
          'findings', (SELECT count(*) FROM finding f JOIN atomic_claim c ON c.id=f.claim_id WHERE c.content_id=:'content_id'),
          'published_findings', (SELECT count(*) FROM finding f JOIN atomic_claim c ON c.id=f.claim_id WHERE c.content_id=:'content_id' AND f.publication_status='PUBLISH'),
          'provider_receipts', (SELECT count(*) FROM provider_receipt WHERE content_id=:'content_id'),
          'published_at', (SELECT published_at::text FROM content_item WHERE id=:'content_id'),
          'variant_observed_at', (SELECT created_at::text FROM transcript_variant WHERE id=:'variant_id'),
          'min_media_ms', (SELECT min(start_ms) FROM canonical_transcript_segment WHERE content_id=:'content_id'),
          'max_media_ms', (SELECT max(end_ms) FROM canonical_transcript_segment WHERE content_id=:'content_id')
        )::text;
        """,
        content_id=CONTENT_ID,
        variant_id=VARIANT_ID,
    )
    result = json.loads(raw)
    result["first_insert_return"] = first_insert
    result["replay_insert_return"] = replay_insert
    result["verdict"] = "PASS" if (
        result["claims"] == 36
        and result["segments"] == 84
        and result["variant_candidates"] == 84
        and result["edges"] >= 36
        and result["findings"] == 0
        and result["published_findings"] == 0
        and result["provider_receipts"] == 0
        and result["min_media_ms"] == 0
        and result["max_media_ms"] == fixture.duration_ms
        and replay_insert == 36
    ) else "INVARIANT_VIOLATED"
    return result


def acceptance_summary(fixture: FixtureAcceptance) -> dict[str, Any]:
    return {
        "audit_sha256": fixture.audit_sha256,
        "transcript_file_sha256": fixture.transcript_file_sha256,
        "transcript_content_sha256": fixture.transcript_content_sha256,
        "duration_ms": fixture.duration_ms,
        "segment_count": len(fixture.segments),
        "claim_count": len(fixture.claims),
        "claim_segment_edge_count": sum(len(claim.segment_ids) for claim in fixture.claims),
        "numeric_sensitive_claims": [claim.fixture_claim_id for claim in fixture.claims if claim.numeric_sensitive],
        "inserted_clip_segments": [segment.index for segment in fixture.segments if 414_000 <= segment.start_ms <= 434_000],
        "provider_call_count": 0,
        "live_lane": "BLOCKED_BY_DP_202",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="DP-207 deterministic timestamp acceptance")
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--transcript", type=Path, default=DEFAULT_TRANSCRIPT)
    parser.add_argument("--database-url")
    args = parser.parse_args(argv)
    fixture = load_fixture_acceptance(args.audit, args.transcript)
    result: dict[str, Any] = {"fixture": acceptance_summary(fixture)}
    if args.database_url:
        result["database_canary"] = persist_fixture_canary(QueueRuntimeStore(args.database_url), fixture)
        if result["database_canary"]["verdict"] != "PASS":
            print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
            return 1
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
