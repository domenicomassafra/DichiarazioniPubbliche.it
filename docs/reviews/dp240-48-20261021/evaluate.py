"""Recompute DP-240 #48 attribution, provenance and token observations from Pi receipts."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).parent
DATA = json.loads((ROOT / "material.json").read_text())
EXPECTED = {item["id"]: item for item in DATA["items"]}


def read(name: str) -> dict:
    return json.loads((ROOT / f"benchmark-{name}.json").read_text())


def score(name: str, expected_ids: set[str]) -> dict:
    observed = read(name)
    answers = json.loads(observed["answer"])
    items = answers["items"]
    if type(items) is not list:
        raise AssertionError("ITEMS_NOT_LIST")
    received = {}
    for row in items:
        if row["id"] in received:
            raise AssertionError("DUPLICATE_ITEM")
        received[row["id"]] = row
    if set(received) != expected_ids:
        raise AssertionError(f"ITEM_CARDINALITY:{name}")
    correct = 0
    per_item = []
    for key in sorted(expected_ids):
        item, answer = EXPECTED[key], received[key]
        valid_identity = (
            answer["speaker"] == item["expected_speaker"]
            and answer["role"] == item["expected_role"]
            and answer["attribution_status"] == "ATTRIBUTED"
        )
        valid_source = (
            answer["content_id"] == item["content_id"]
            and answer["source_url"] == item["url"]
        )
        correct += valid_identity and valid_source
        per_item.append({"item_id": key, "speaker_correct": bool(valid_identity),
                         "source_content_url_exact": bool(valid_source)})
    usages = [event["usage"] for event in observed["usage_events"]]
    if not usages or any(u["stopReason"] == "error" for u in observed["usage_events"]):
        raise AssertionError("PROVIDER_ERROR")
    # This run has exactly one successful assistant reply, no hidden token allocation.
    usage = usages[-1]
    return {
        "mode": name, "items": len(expected_ids),
        "correct_attributions": int(correct),
        "false_or_source_mismatched": len(expected_ids) - correct,
        "per_item": per_item,
        "tokens": {"input": usage["input"], "output": usage["output"],
                   "reasoning_reported": usage.get("reasoning"),
                   "total_reported": usage["totalTokens"]},
        "provider_meter_cost_reported": usage["cost"]["total"],
        "provider_invoice_cost": None,
        "end_to_end_ssh_wall_seconds": observed["elapsed_ssh_seconds"],
        "peak_remote_rss": observed["remote_peak_rss_kb"],
    }


def main() -> dict:
    single_a = score("single-meloni", {"meloni-2024-09-17"})
    single_b = score("single-mattarella", {"mattarella-2019-12-03"})
    mixed = score("mixed", set(EXPECTED))
    baseline_total_tokens = single_a["tokens"]["total_reported"] + single_b["tokens"]["total_reported"]
    saved = baseline_total_tokens - mixed["tokens"]["total_reported"]
    errors = []
    for mode in ("single-meloni", "single-mattarella"):
        attempt = json.loads((ROOT / f"benchmark-{mode}-provider-failure.json").read_text())
        errors.append({
            "item_id": mode.removeprefix("single-"),
            "provider_attempt_failed": attempt["usage_events"][-1]["stopReason"] == "error",
            "zero_output": not bool(attempt["answer"]),
            "elapsed_ssh_seconds": attempt["elapsed_ssh_seconds"],
            "retry_recovered": True,
        })
    return {
        "scope": "two-item observational model comparison; no causality/statistical inference",
        "singles": [single_a, single_b], "mixed": mixed,
        "both_modes_correct": all(
            x["correct_attributions"] == x["items"] for x in (single_a, single_b, mixed)
        ),
        "mixed_cross_source_mismatch_count": mixed["false_or_source_mismatched"],
        "baseline_total_tokens": baseline_total_tokens,
        "mixed_total_tokens": mixed["tokens"]["total_reported"],
        "token_saving_count": saved,
        "token_saving_fraction": round(saved / baseline_total_tokens, 4),
        "baseline_sum_wall_seconds": round(
            single_a["end_to_end_ssh_wall_seconds"] + single_b["end_to_end_ssh_wall_seconds"], 3
        ),
        "mixed_wall_seconds": mixed["end_to_end_ssh_wall_seconds"],
        "earlier_provider_attempt_failures": errors,
        "limitations": [
            "two Italian official sources only; expected speakers from source/editorial labels",
            "pre-review by two AI models, no independent human gold",
            "shared Gemini family between generator and one reviewer; possible correlated errors",
            "provider reported cost zero is not independently verified billing",
            "peak remote memory unavailable; timings include Pi CLI startup and SSH",
            "normalized bounded excerpts are not immutable first-party raw Passage captures",
            "no production Studio/PostgreSQL candidate write or publication",
        ],
        "larger_batch_approved": False,
        "publication_approved": False,
    }


if __name__ == "__main__":
    result = main()
    (ROOT / "benchmark-metrics.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps({
        "correct": result["both_modes_correct"],
        "token_saving_fraction": result["token_saving_fraction"],
        "provider_failures": len(result["earlier_provider_attempt_failures"])
    }))
