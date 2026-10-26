#!/usr/bin/env python3
"""Bounded official CURIA judgment -> durable private held procedural candidates.

The pinned judgment and its public copyright notice permit a tightly scoped
private research capture; anonymous-party privacy, underlying factual claims,
prior-act original and public quotations remain held. No model is called.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.capture_authorization import private_capture_rights_guard  # noqa: E402
from dichiarazioni_pubbliche.capture_pipeline import (  # noqa: E402
    CaptureBodyStore, CaptureEnrichmentPolicy, CapturePipelineStore, ParseResult,
    ParsedSpan, capture_content, verify_passage_roundtrip,
)
from dichiarazioni_pubbliche.corpus_repository import (  # noqa: E402
    INSERT_STATEMENT_CANDIDATE_SQL_V1, PassageRecord, deterministic_corpus_id,
)
from dichiarazioni_pubbliche.private_capture_rights import SourceFamilyUseGuard  # noqa: E402
from dichiarazioni_pubbliche.source_watcher import FetchedBytes, fetch_bytes  # noqa: E402
from tools.dp313_curia_private_intake_rights import (  # noqa: E402
    CONTENT_ID, FAMILY, PARSER_VERSION, POLICY, _identities, _rights,
)
from tools.dp313_curia_private_readback import (  # noqa: E402
    SOURCE_COPYRIGHT, SOURCE_ECLI, SOURCE_SHA256, SOURCE_URL, _official_text,
    evaluate_curia_private,
)

def fetch_official_original() -> bytes:
    """Refuse redirects, non-HTML responses, or incomplete official downloads."""
    fetched = fetch_bytes(SOURCE_URL, max_response_bytes=500_000)
    if (fetched.final_url != SOURCE_URL or fetched.status_code != 200
            or fetched.media_type.split(";", 1)[0].lower() != "text/html"
            or not 100 <= len(fetched.body) <= 500_000):
        raise ValueError("DP313_OFFICIAL_FETCH_IDENTITY_MISMATCH")
    return fetched.body


class CuriaJudgmentParser:
    parser_method = "NATIVE_JUDICIAL_HTML"
    parser_version = PARSER_VERSION

    def __init__(self, *, expected_sha256: str = SOURCE_SHA256) -> None:
        self.expected_sha256 = expected_sha256

    def parse(self, fetched: FetchedBytes) -> ParseResult:
        # verify_passage_roundtrip feeds the already-hashed body through a
        # fixed .invalid locator. The live HTTP authority is enforced before
        # this parser by fetch_official_original and SourceFamilyUseGuard.
        if fetched.final_url not in {SOURCE_URL, "https://roundtrip.invalid/"} or fetched.media_type != "text/html":
            raise ValueError("DP313_SOURCE_OR_MEDIA_CHANGED")
        receipt = evaluate_curia_private(fetched.body, expected_sha256=self.expected_sha256)
        canonical = _official_text(fetched.body)
        spans = tuple(ParsedSpan(
            start_char=item["start_char"], end_char=item["end_char"],
            text=canonical[item["start_char"]:item["end_char"]],
            text_sha256=item["sha256"],
        ) for item in receipt["span_locators"])
        return ParseResult(
            status="SUCCEEDED", parser_method=self.parser_method,
            parser_version=self.parser_version, canonical_text=canonical,
            spans=spans, metadata={
                "source_ecli": SOURCE_ECLI, "canonical_text_sha256": self.expected_sha256,
                "source_family": FAMILY, "source_rights": SOURCE_COPYRIGHT,
                "private_only": True, "procedural_state": "HOLD",
            },
        )


def _existing_chain(store: CapturePipelineStore, storage_root: Path,
                    parsed: ParseResult, roles: list[str]) -> dict[str, object] | None:
    """Reuse a complete source-family chain despite volatile official HTML chrome."""
    raw = store.run(
        """SELECT json_build_object('id',capture.id,'sha',capture.content_sha256,
                   'body',capture.body_ref,'parts',(
                     SELECT json_agg(json_build_object(
                       'id',p.id,'candidate',c.id,'role',c.metadata->>'procedural_role',
                       'start',p.start_char,'end',p.end_char,'sha',p.text_sha256,
                       'text',p.private_text,'statement',c.normalized_statement,
                       'statement_sha',c.statement_text_hash,'speaker',c.speaker_person_id,
                       'privacy',c.metadata->>'privacy_gate',
                       'public',c.metadata->>'publication_authorized',
                       'family',c.metadata->>'source_family',
                       'version',c.metadata->>'version',
                       'state',c.status) ORDER BY p.start_char)
                     FROM passage p
                     JOIN statement_candidate_passage edge ON edge.passage_id=p.id
                     JOIN statement_candidate c ON c.id=edge.statement_candidate_id
                     WHERE p.capture_id=capture.id AND c.content_id=:'content'
                       AND c.metadata->>'case'=:'ecli'
                   ))::text
           FROM content_capture capture
           WHERE capture.content_id=:'content' AND capture.parser_version=:'parser'
             AND capture.metadata->'source_metadata'->>'canonical_text_sha256'=:'digest'
             AND capture.status='CAPTURED' AND capture.rights_status='CLEARED'
             AND capture.hold_status='NONE' AND capture.body_purged_at IS NULL
             AND capture.body_ref IS NOT NULL
           ORDER BY capture.observed_at,capture.id;""",
        content=CONTENT_ID, parser=PARSER_VERSION, digest=SOURCE_SHA256, ecli=SOURCE_ECLI,
    )
    for line in raw.splitlines():
        item = json.loads(line)
        parts = item.get("parts")
        if not isinstance(parts, list) or len(parts) != len(parsed.spans):
            continue
        expected = [
            {"role": role, "start": span.start_char, "end": span.end_char,
             "sha": span.text_sha256, "text": span.text,
             "statement": span.text, "statement_sha": span.text_sha256,
             "speaker": None, "privacy": "HOLD", "public": "false",
             "family": FAMILY, "version": SOURCE_SHA256, "state": "HELD"}
            for role, span in zip(roles, parsed.spans)
        ]
        if any(any(row.get(key) != value for key, value in wanted.items())
               for row, wanted in zip(parts, expected)):
            raise RuntimeError("DP313_EXISTING_CHAIN_CONFLICT")
        original = CaptureBodyStore.open_existing_readonly(storage_root).read(
            item["body"], expected_sha256=item["sha"], max_bytes=500_000,
        )
        if _official_text(original) != parsed.canonical_text:
            raise RuntimeError("DP313_EXISTING_CANONICAL_MISMATCH")
        return {"capture_id": item["id"],
                "candidates": [{"candidate_id": row["candidate"],
                                "passage_id": row["id"], "role": row["role"],
                                "state": row["state"]} for row in parts]}
    return None


def run(*, html: bytes, database_url: str | None, storage_root: Path,
        apply: bool) -> dict[str, object]:
    """Check the real original first, persist only when explicitly applying."""
    document = evaluate_curia_private(html)
    if document["span_states"] != ["HOLD"] * 4:
        raise RuntimeError("DP313_UNEXPECTED_PROMOTION")
    result: dict[str, object] = {
        "state": "PRIVATE_HOLD", "source_ecli": SOURCE_ECLI,
        "canonical_text_sha256": SOURCE_SHA256,
        "span_roles": document["span_roles"],
        "underlying_fact_assessments": document["underlying_fact_assessments"],
        "publication_authorized": False, "model_called": False,
    }
    if not apply:
        return {**result, "persistent": False, "writes": 0}

    store = CapturePipelineStore(database_url=database_url)
    _identities(store)
    registry, subject, current = _rights(store)
    guard = private_capture_rights_guard(
        read_current=registry.read_current, rights_record_id=current.id,
        content_id=CONTENT_ID, canonical_url=SOURCE_URL, source_family=FAMILY,
        read_content_state=store.read_operator_capture_content_state,
    )
    raw_sha = hashlib.sha256(html).hexdigest()
    use = SourceFamilyUseGuard(
        read_current=registry.read_current, subject=subject, rights_record_id=current.id,
        policy_version=POLICY, expected_sha256=raw_sha, expected_media_type="text/html",
    )
    guard()
    # Operator private-capture permission has its own gate; the per-stage
    # SourceFamilyUseGuard intentionally accepts only FETCH/PARSE/STORE/EXTRACT.
    for scope in ("FETCH", "STORE_BODY", "PARSE_TEXT", "EXTRACT_CANDIDATES"):
        use.require(scope)
    fetched = FetchedBytes(html, SOURCE_URL, 200, "text/html", "utf-8", len(html))

    def pinned_fetch(url: str, *, max_response_bytes: int) -> FetchedBytes:
        if url != SOURCE_URL or len(html) > max_response_bytes:
            raise RuntimeError("DP313_FETCH_BOUNDARY_MISMATCH")
        guard()
        use.require("FETCH", content_sha256=raw_sha, media_type="text/html")
        return fetched

    parsed = CuriaJudgmentParser().parse(fetched)
    previous = _existing_chain(store, storage_root, parsed, document["span_roles"])
    if previous is not None:
        return {**result, **previous, "persistent": True, "reused_canonical_case": True,
                "rights_record_id": current.id, "private_stage": "CANDIDATES_HELD",
                "public_stage": "BLOCKED_PRIVACY_AND_RIGHTS"}
    receipt = capture_content(
        content_id=CONTENT_ID, url=SOURCE_URL, store=store,
        body_store=CaptureBodyStore(storage_root), actor_ref="machine:dp313-curia",
        retention_class="DURABLE_PRIVATE", rights_status="CLEARED", language="it",
        parser=CuriaJudgmentParser(), fetcher=pinned_fetch,
        enrichment_policy=CaptureEnrichmentPolicy(metadata_enabled=True, archive_enabled=False),
        rights_guard=guard, source_use_guard=use, max_response_bytes=500_000,
    )
    if receipt.parse_status != "SUCCEEDED" or len(receipt.passage_ids) != 4:
        raise RuntimeError("DP313_CAPTURE_PASSAGES_MISSING")
    captured = store.find_capture(CONTENT_ID, raw_sha)
    if not captured or captured["id"] != receipt.primary_capture_id:
        raise RuntimeError("DP313_CAPTURE_READBACK_MISMATCH")
    original = CaptureBodyStore(storage_root).read(captured["body_ref"], expected_sha256=raw_sha)
    if original != html:
        raise RuntimeError("DP313_CAPTURE_BODY_CHANGED")
    candidates: list[dict[str, str]] = []
    for index, (passage_id, span) in enumerate(zip(receipt.passage_ids, parsed.spans)):
        persisted = store.run(
            """SELECT json_build_object('id',id,'capture',capture_id,
                        'start',start_char,'end',end_char,'sha',text_sha256,
                        'text',private_text)::text
               FROM passage WHERE id=:'id' AND content_id=:'content';""",
            id=passage_id, content=CONTENT_ID,
        )
        actual = json.loads(persisted or "null")
        if actual != {"id": passage_id, "capture": receipt.primary_capture_id,
                      "start": span.start_char, "end": span.end_char,
                      "sha": span.text_sha256, "text": span.text}:
            raise RuntimeError("DP313_PASSAGE_READBACK_MISMATCH")
        passage = PassageRecord(
            id=passage_id, content_id=CONTENT_ID, capture_id=receipt.primary_capture_id,
            selector_type="TEXT_POSITION", start_char=span.start_char,
            end_char=span.end_char, text_sha256=span.text_sha256,
            private_text=span.text, language="it",
            extraction_method=CuriaJudgmentParser.parser_method,
            extraction_version=PARSER_VERSION,
        )
        if not verify_passage_roundtrip(body=original, media_type="text/html",
                                         charset="utf-8", passage=passage,
                                         parser=CuriaJudgmentParser()):
            raise RuntimeError("DP313_PASSAGE_ROUNDTRIP_FAILED")
        use.require("EXTRACT_CANDIDATES", content_sha256=raw_sha, media_type="text/html")
        candidate_id = deterministic_corpus_id("statement-candidate", passage_id, span.text_sha256)
        state = store.run(
            INSERT_STATEMENT_CANDIDATE_SQL_V1,
            id=candidate_id, content_id=CONTENT_ID, speaker_person_id="",
            statement_text_hash=span.text_sha256, normalized_statement=span.text,
            statement_at="", attribution_method="", extraction_model="",
            extraction_version="dp313-court-roles-held-v1", status="HELD",
            metadata=json.dumps({"case": SOURCE_ECLI, "private_only": True,
                                 "procedural_role": document["span_roles"][index],
                                 "assertion_kind": document["assertion_kinds"][index],
                                 "underlying_fact": "NOT_EVALUATED",
                                 "source_family": FAMILY, "version": SOURCE_SHA256,
                                 "privacy_gate": "HOLD", "publication_authorized": False}),
            passage_ids=json.dumps([passage_id]),
        )
        if state not in {"INSERTED", "EXISTING"}:
            raise RuntimeError("DP313_CANDIDATE_CONFLICT")
        linked = store.run(
            """SELECT count(*) FROM statement_candidate candidate
               JOIN statement_candidate_passage edge ON edge.statement_candidate_id=candidate.id
               JOIN passage p ON p.id=edge.passage_id AND p.content_id=edge.content_id
               WHERE candidate.id=:'candidate' AND candidate.content_id=:'content'
                 AND candidate.status='HELD' AND candidate.speaker_person_id IS NULL
                 AND p.id=:'passage' AND p.capture_id=:'capture';""",
            candidate=candidate_id, content=CONTENT_ID, passage=passage_id,
            capture=receipt.primary_capture_id,
        )
        if linked != "1":
            raise RuntimeError("DP313_CANDIDATE_READBACK_FAILED")
        candidates.append({"candidate_id": candidate_id, "passage_id": passage_id,
                           "role": document["span_roles"][index], "state": "HELD"})
    return {**result, "persistent": True, "capture_id": receipt.primary_capture_id,
            "rights_record_id": current.id, "candidates": candidates,
            "reused_canonical_case": False,
            "private_stage": "CANDIDATES_HELD", "public_stage": "BLOCKED_PRIVACY_AND_RIGHTS"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--html", type=Path, help="Previously pinned CURIA HTML; read-only")
    parser.add_argument("--database-url", default=os.getenv("DICHIARAZIONI_PUBBLICHE_DATABASE_URL"))
    parser.add_argument("--storage-root", type=Path,
                        default=Path("~/.local/share/dichiarazioni-pubbliche-captures").expanduser())
    parser.add_argument("--apply-private-intake", action="store_true")
    args = parser.parse_args()
    try:
        if args.apply_private_intake and args.html:
            raise ValueError("DP313_APPLY_REQUIRES_FRESH_OFFICIAL_HTTPS")
        html = args.html.read_bytes() if args.html else fetch_official_original()
        outcome = run(html=html, database_url=args.database_url,
                      storage_root=args.storage_root, apply=args.apply_private_intake)
    except Exception as exc:
        code = str(exc)
        if not (code.startswith("DP313_") or code in {
            "SOURCE_DIGEST_CHANGED", "OFFICIAL_HTML_SIZE_INVALID", "ECLI_MISMATCH"}):
            code = "DP313_PRIVATE_PREFLIGHT_FAILED"
        outcome = {"state": "BLOCKED", "reason_code": code,
                   "persistent": False, "publication_authorized": False}
    print(json.dumps(outcome, ensure_ascii=False, sort_keys=True))
    return 2 if outcome["state"] == "BLOCKED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
