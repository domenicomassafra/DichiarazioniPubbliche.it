from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable

from dichiarazioni_pubbliche.claim_runtime import matches_returned_model
from dichiarazioni_pubbliche.claim_extraction_transport import (
    _cost_from_response, _read_env_file, call_omniroute, response_content,
)
from dichiarazioni_pubbliche.private_capture_rights import SourceFamilyUseGuard


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_AUDIT = ROOT / "poc" / "content" / "raffagiulians-bollo-2026" / "content-audit.json"
DEFAULT_TRANSCRIPT = ROOT / "poc" / "content" / "raffagiulians-bollo-2026" / "raw" / "transcript.json"
DEFAULT_MODEL = "antigravity/gemini-3.8-flash-tiered"
DEFAULT_BASE_URL = "http://127.0.0.1:20128"

NOT_FACT_CHECKABLE = {"NOT_FACT_CHECKABLE"}
NUMERIC_PATTERN = re.compile(
    r"(?:\d|%|\beuro\b|\bmiliard\w*\b|\bmilion\w*\b|\bpercent\w*\b|\bper\s+cento\b)",
    re.IGNORECASE,
)

STOPWORDS = {
    "a",
    "ad",
    "al",
    "alla",
    "alle",
    "anche",
    "che",
    "chi",
    "ci",
    "come",
    "con",
    "da",
    "dal",
    "dalla",
    "delle",
    "di",
    "e",
    "ed",
    "gli",
    "ha",
    "hanno",
    "i",
    "il",
    "in",
    "la",
    "le",
    "lo",
    "ma",
    "nei",
    "nel",
    "nella",
    "non",
    "o",
    "per",
    "piu",
    "più",
    "si",
    "sono",
    "su",
    "un",
    "una",
}


@dataclass(frozen=True)
class ReferenceClaim:
    claim_id: str
    timestamp: str
    seconds: float
    speaker: str
    claim_type: str
    normalized_claim: str
    assessment: str
    check_worthy: bool
    numeric_sensitive: bool


@dataclass(frozen=True)
class ExtractedClaim:
    index: int
    timestamp: str
    seconds: float
    speaker: str
    claim_type: str
    claim_text: str
    check_worthy: bool
    numeric_sensitive: bool
    raw: dict[str, Any]


def parse_timestamp(value: str | int | float | None) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return 0.0
    if re.fullmatch(r"\d+(?:\.\d+)?", text):
        return float(text)
    parts = text.split(":")
    try:
        nums = [float(part) for part in parts]
    except ValueError:
        return 0.0
    if len(nums) == 2:
        return nums[0] * 60 + nums[1]
    if len(nums) == 3:
        return nums[0] * 3600 + nums[1] * 60 + nums[2]
    return 0.0


def _normalize_text(value: str) -> str:
    value = value.casefold()
    value = re.sub(r"[^\w\s]", " ", value, flags=re.UNICODE)
    return re.sub(r"\s+", " ", value).strip()


def _content_tokens(value: str) -> set[str]:
    return {
        token
        for token in _normalize_text(value).split()
        if len(token) > 1 and token not in STOPWORDS
    }


def _text_similarity(left: str, right: str) -> float:
    lt = _content_tokens(left)
    rt = _content_tokens(right)
    if not lt or not rt:
        jaccard = 0.0
    else:
        jaccard = len(lt & rt) / len(lt | rt)
    ratio = SequenceMatcher(None, _normalize_text(left), _normalize_text(right)).ratio()
    containment = 0.0
    if lt and rt:
        containment = len(lt & rt) / min(len(lt), len(rt))
    return max(jaccard, ratio * 0.78, containment * 0.88)


def _speaker_similarity(left: str, right: str) -> float:
    a = _normalize_text(left)
    b = _normalize_text(right)
    if not a or not b:
        return 0.0
    if a == b or a in b or b in a:
        return 1.0
    at = _content_tokens(a)
    bt = _content_tokens(b)
    return 1.0 if at & bt else 0.0


def _time_similarity(left: float, right: float) -> float:
    delta = abs(left - right)
    if delta <= 3:
        return 1.0
    if delta <= 8:
        return 0.82
    if delta <= 15:
        return 0.58
    if delta <= 30:
        return 0.22
    return 0.0


def pair_score(reference: ReferenceClaim, extracted: ExtractedClaim) -> float:
    text = _text_similarity(reference.normalized_claim, extracted.claim_text)
    timing = _time_similarity(reference.seconds, extracted.seconds)
    speaker = _speaker_similarity(reference.speaker, extracted.speaker)
    return 0.56 * text + 0.34 * timing + 0.10 * speaker


def load_reference_claims(path: Path = DEFAULT_AUDIT) -> list[ReferenceClaim]:
    audit = json.loads(path.read_text())
    claims: list[ReferenceClaim] = []
    for item in audit["claims"]:
        normalized = str(item.get("normalized_claim") or "")
        assessment = str(item.get("assessment") or "")
        timestamp = str(item.get("timestamp") or "0:00")
        claims.append(
            ReferenceClaim(
                claim_id=str(item["id"]),
                timestamp=timestamp,
                seconds=parse_timestamp(timestamp),
                speaker=str(item.get("speaker") or ""),
                claim_type=str(item.get("type") or ""),
                normalized_claim=normalized,
                assessment=assessment,
                check_worthy=assessment not in NOT_FACT_CHECKABLE,
                numeric_sensitive=bool(NUMERIC_PATTERN.search(normalized)),
            )
        )
    return claims


def load_transcript_text(path: Path = DEFAULT_TRANSCRIPT) -> str:
    raw = json.loads(path.read_text())
    text = str(raw.get("timestamped_text") or raw.get("full_text") or "").strip()
    if not text:
        raise ValueError(f"Transcript is empty: {path}")
    return text


def taxonomy_from_reference(references: Iterable[ReferenceClaim]) -> list[str]:
    return sorted({item.claim_type for item in references if item.claim_type})


def build_prompt(transcript: str, claim_types: Iterable[str]) -> str:
    taxonomy = ", ".join(claim_types)
    return f"""You are performing claim extraction only. Do not fact-check and do not use external knowledge.

Extract every atomic public claim from the Italian timestamped transcript below.

Rules:
- Preserve the speaker actually making the statement; an inserted clip is not the narrator.
- Keep claims atomic. Split independent propositions, but do not split one proposition into cosmetic fragments.
- Include factual claims, numeric claims, predictions, motive attributions, historical attributions, policy positions, and value/rhetorical claims when they are meaningful statements in the content.
- check_worthy=true when the statement can or should be investigated against evidence; pure value judgments/rhetoric should normally be false.
- numeric_sensitive=true when the correctness materially depends on a number, percentage, amount of money, date/year, rate, threshold, or arithmetic relation.
- source_timestamp must be the nearest timestamp visible in the transcript, formatted M:SS.
- claim_text must be a concise neutral normalization of what was said, not a verdict.
- Do not add claims that are not present in the transcript.

Allowed claim_type values:
{taxonomy}

Return JSON only, exactly in this shape:
{{
  "claims": [
    {{
      "source_timestamp": "M:SS",
      "speaker": "speaker name",
      "claim_type": "ONE_ALLOWED_VALUE",
      "claim_text": "neutral atomic claim",
      "check_worthy": true,
      "numeric_sensitive": false
    }}
  ]
}}

TRANSCRIPT:
---BEGIN TRANSCRIPT---
{transcript}
---END TRANSCRIPT---"""


def _strip_json_fence(text: str) -> str:
    value = text.strip()
    if value.startswith(chr(96) * 3):
        value = re.sub(r"^.{3}(?:json)?\s*", "", value, count=1, flags=re.IGNORECASE)
        value = re.sub(r"\s*.{3}$", "", value, count=1)
    return value.strip()


def parse_model_payload(text: str) -> dict[str, Any]:
    value = _strip_json_fence(text)
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        start = value.find("{")
        end = value.rfind("}")
        if start < 0 or end <= start:
            raise
        parsed = json.loads(value[start : end + 1])
    if not isinstance(parsed, dict) or not isinstance(parsed.get("claims"), list):
        raise ValueError("Model output must be an object with a claims array")
    return parsed


def normalize_extracted_claims(payload: dict[str, Any]) -> list[ExtractedClaim]:
    claims: list[ExtractedClaim] = []
    for index, raw in enumerate(payload.get("claims", []), start=1):
        if not isinstance(raw, dict):
            continue
        text = str(raw.get("claim_text") or "").strip()
        if not text:
            continue
        timestamp = str(raw.get("source_timestamp") or raw.get("timestamp") or "0:00")
        numeric = raw.get("numeric_sensitive")
        if not isinstance(numeric, bool):
            numeric = bool(NUMERIC_PATTERN.search(text))
        claims.append(
            ExtractedClaim(
                index=index,
                timestamp=timestamp,
                seconds=parse_timestamp(timestamp),
                speaker=str(raw.get("speaker") or "").strip(),
                claim_type=str(raw.get("claim_type") or raw.get("type") or "").strip(),
                claim_text=text,
                check_worthy=bool(raw.get("check_worthy", True)),
                numeric_sensitive=bool(numeric),
                raw=raw,
            )
        )
    return claims


def match_claims(
    references: list[ReferenceClaim],
    extracted: list[ExtractedClaim],
    *,
    threshold: float = 0.49,
) -> tuple[list[tuple[int, int, float]], list[list[float]]]:
    matrix = [[pair_score(ref, pred) for pred in extracted] for ref in references]
    candidates: list[tuple[float, int, int]] = []
    for ref_index, row in enumerate(matrix):
        for pred_index, score in enumerate(row):
            if score >= threshold:
                candidates.append((score, ref_index, pred_index))
    candidates.sort(reverse=True)

    used_refs: set[int] = set()
    used_preds: set[int] = set()
    matches: list[tuple[int, int, float]] = []
    for score, ref_index, pred_index in candidates:
        if ref_index in used_refs or pred_index in used_preds:
            continue
        used_refs.add(ref_index)
        used_preds.add(pred_index)
        matches.append((ref_index, pred_index, score))
    matches.sort()
    return matches, matrix


def _safe_div(num: int | float, den: int | float) -> float:
    return float(num) / float(den) if den else 0.0


def evaluate_extraction(
    references: list[ReferenceClaim],
    extracted: list[ExtractedClaim],
    *,
    threshold: float = 0.49,
) -> dict[str, Any]:
    matches, matrix = match_claims(references, extracted, threshold=threshold)
    matched_ref_ids = {r for r, _, _ in matches}
    matched_pred_ids = {p for _, p, _ in matches}

    type_ok = 0
    speaker_ok = 0
    check_ok = 0
    numeric_ok = 0
    rows = []
    for ref_index, pred_index, score in matches:
        ref = references[ref_index]
        pred = extracted[pred_index]
        type_match = ref.claim_type == pred.claim_type
        speaker_match = _speaker_similarity(ref.speaker, pred.speaker) >= 1.0
        check_match = ref.check_worthy == pred.check_worthy
        numeric_match = ref.numeric_sensitive == pred.numeric_sensitive
        type_ok += int(type_match)
        speaker_ok += int(speaker_match)
        check_ok += int(check_match)
        numeric_ok += int(numeric_match)
        rows.append(
            {
                "reference_id": ref.claim_id,
                "reference_timestamp": ref.timestamp,
                "extracted_index": pred.index,
                "extracted_timestamp": pred.timestamp,
                "match_score": round(score, 4),
                "type_match": type_match,
                "speaker_match": speaker_match,
                "check_worthy_match": check_match,
                "numeric_sensitive_match": numeric_match,
            }
        )

    near_threshold = max(threshold - 0.08, 0.0)
    over_split_reference_ids = []
    for ref_index, row in enumerate(matrix):
        plausible = sum(1 for score in row if score >= near_threshold)
        if plausible > 1:
            over_split_reference_ids.append(references[ref_index].claim_id)

    under_split_prediction_indices = []
    for pred_index in range(len(extracted)):
        plausible = sum(
            1
            for ref_index in range(len(references))
            if matrix[ref_index][pred_index] >= near_threshold
        )
        if plausible > 1:
            under_split_prediction_indices.append(extracted[pred_index].index)

    matched = len(matches)
    return {
        "reference_claims": len(references),
        "extracted_claims": len(extracted),
        "matched_claims": matched,
        "claim_recall": _safe_div(matched, len(references)),
        "claim_precision": _safe_div(matched, len(extracted)),
        "type_accuracy_on_matched": _safe_div(type_ok, matched),
        "speaker_accuracy_on_matched": _safe_div(speaker_ok, matched),
        "check_worthy_accuracy_on_matched": _safe_div(check_ok, matched),
        "numeric_sensitive_accuracy_on_matched": _safe_div(numeric_ok, matched),
        "unmatched_reference_ids": [
            ref.claim_id for idx, ref in enumerate(references) if idx not in matched_ref_ids
        ],
        "unmatched_extracted_indices": [
            pred.index for idx, pred in enumerate(extracted) if idx not in matched_pred_ids
        ],
        "possible_over_split_reference_ids": over_split_reference_ids,
        "possible_under_split_prediction_indices": under_split_prediction_indices,
        "matching_threshold": threshold,
        "matches": rows,
    }


def require_live_benchmark_preflight(
    *,
    model: str,
    parent_canary_receipt: Path | None,
    source_use_guard: SourceFamilyUseGuard | None,
    transcript_path: Path,
) -> None:
    """Recheck the DP-201 parent and current source permission before any LLM call."""
    if model != DEFAULT_MODEL:
        raise RuntimeError("DP202_MODEL_UNAUTHORIZED")
    if parent_canary_receipt is None:
        raise RuntimeError("DP202_PARENT_CANARY_UNVERIFIED")
    try:
        receipt = json.loads(parent_canary_receipt.read_text())
        usage = receipt["usage"]
        valid = (
            receipt["status"] == "CANARY_PASSED"
            and receipt["model_requested"] == DEFAULT_MODEL
            and matches_returned_model(DEFAULT_MODEL, receipt["model_returned"])
            and receipt["subscription_gateway_verified"] is True
            and receipt["schema_constrained"] is True
            and receipt["model_identity_exact"] is True
            and type(receipt["model_calls"]) is int
            and receipt["model_calls"] == 1
            and isinstance(receipt["request_id"], str)
            and bool(receipt["request_id"].strip())
            and type(usage["prompt_tokens"]) is int
            and usage["prompt_tokens"] > 0
            and type(usage["completion_tokens"]) is int
            and usage["completion_tokens"] >= 0
            and (
                receipt.get("observed_cost_usd") is None
                or receipt["observed_cost_usd"] == 0
            )
        )
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        valid = False
    if not valid:
        raise RuntimeError("DP202_PARENT_CANARY_UNVERIFIED")

    # The registry guard must read an up-to-date, source-specific rights record.
    # A CLI flag or an unbound approval JSON is not a source-use permission.
    if not isinstance(source_use_guard, SourceFamilyUseGuard):
        raise RuntimeError("DP202_SOURCE_RIGHTS_UNVERIFIED")
    try:
        digest = hashlib.sha256(transcript_path.read_bytes()).hexdigest()
        if source_use_guard.expected_sha256 != digest:
            raise RuntimeError("DP202_SOURCE_RIGHTS_UNVERIFIED")
        source_use_guard.require("PARSE_TEXT", content_sha256=digest)
    except Exception:
        raise RuntimeError("DP202_SOURCE_RIGHTS_UNVERIFIED") from None


def run_live_benchmark(
    *,
    audit_path: Path = DEFAULT_AUDIT,
    transcript_path: Path = DEFAULT_TRANSCRIPT,
    model: str = DEFAULT_MODEL,
    base_url: str = DEFAULT_BASE_URL,
    api_key: str = "",
    threshold: float = 0.49,
    max_tokens: int = 4096,
    timeout_seconds: float = 120.0,
    parent_canary_receipt: Path | None = None,
    source_use_guard: SourceFamilyUseGuard | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    require_live_benchmark_preflight(
        model=model,
        parent_canary_receipt=parent_canary_receipt,
        source_use_guard=source_use_guard,
        transcript_path=transcript_path,
    )
    references = load_reference_claims(audit_path)
    transcript = load_transcript_text(transcript_path)
    prompt = build_prompt(transcript, taxonomy_from_reference(references))
    response, elapsed = call_omniroute(
        prompt=prompt,
        model=model,
        base_url=base_url,
        api_key=api_key,
        max_tokens=max_tokens,
        timeout_seconds=timeout_seconds,
    )
    payload = parse_model_payload(response_content(response))
    extracted = normalize_extracted_claims(payload)
    metrics = evaluate_extraction(references, extracted, threshold=threshold)
    metrics["model"] = model
    metrics["latency_seconds"] = round(elapsed, 3)
    metrics["usage"] = response.get("usage")
    metrics["cost_usd"] = _cost_from_response(response)
    metrics["response_id"] = response.get("id")
    metrics["prompt_ground_truth_leakage"] = False
    return metrics, response


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Benchmark claim extraction against the 36-claim Giuliani ground truth."
    )
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--transcript", type=Path, default=DEFAULT_TRANSCRIPT)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument(
        "--base-url",
        default=os.environ.get("OMNIROUTE_BASE_URL", DEFAULT_BASE_URL),
    )
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--parent-canary-receipt", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--threshold", type=float, default=0.49)
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument("--timeout", type=float, default=120.0)
    args = parser.parse_args()

    env_file = _read_env_file(args.env_file)
    api_key = os.environ.get("OMNIROUTE_API_KEY") or env_file.get("OMNIROUTE_API_KEY", "")
    metrics, response = run_live_benchmark(
        audit_path=args.audit,
        transcript_path=args.transcript,
        model=args.model,
        base_url=args.base_url,
        api_key=api_key,
        threshold=args.threshold,
        max_tokens=args.max_tokens,
        timeout_seconds=args.timeout,
        parent_canary_receipt=args.parent_canary_receipt,
    )

    if args.output_dir:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        (args.output_dir / "raw-response.json").write_text(
            json.dumps(response, ensure_ascii=False, indent=2) + "\n"
        )
        (args.output_dir / "report.json").write_text(
            json.dumps(metrics, ensure_ascii=False, indent=2) + "\n"
        )

    summary = {
        key: metrics[key]
        for key in (
            "model",
            "reference_claims",
            "extracted_claims",
            "matched_claims",
            "claim_recall",
            "claim_precision",
            "type_accuracy_on_matched",
            "speaker_accuracy_on_matched",
            "check_worthy_accuracy_on_matched",
            "numeric_sensitive_accuracy_on_matched",
            "latency_seconds",
            "cost_usd",
        )
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
