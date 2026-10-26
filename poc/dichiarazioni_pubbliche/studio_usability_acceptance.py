"""DP-420 private operator acceptance: genuine search gold + observed UI tasks.

This is a read-only acceptance instrument, never a source-rights or publication grant.
No operator task is satisfied by synthetic browser tests or a search benchmark alone.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
from pathlib import Path
from typing import Any, Mapping

from dichiarazioni_pubbliche.corpus_search import CorpusSearchStore
from dichiarazioni_pubbliche.corpus_search_benchmark import load_fixture, run_benchmark
from dichiarazioni_pubbliche.garlasco_pilot_inventory import build_live_inventory
from dichiarazioni_pubbliche.studio_local_api import _StudioReadOnlyDb


ROOT = Path(__file__).resolve().parents[2]
TASKS_PATH = ROOT / "tests" / "fixtures" / "studio-garlasco-usability-v1.json"
_EVIDENCE = re.compile(r"^sha256:[0-9a-f]{64}$")
_IDENTITY = re.compile(r"^(source|capture|passage):[a-z0-9:_.-]{1,180}$")
_RIGHTS = re.compile(r"^private-rights:[a-z0-9:_.-]{1,180}$")
_CANDIDATE = re.compile(r"^statement-candidate:[a-z0-9:_.-]{1,180}$")
_COVERAGE_NEED = re.compile(r"^coverage-need:[a-z0-9:_.-]{1,180}$")
_REQUIRED_MODES = frozenset({
    "wide-desktop", "keyboard-only", "zoom-200", "narrow-viewport",
    "reduced-motion", "screen-reader",
})
_ALLOWED_NEEDS = frozenset({
    "captures", "passages", "statement_candidates", "claim_candidates",
    "collection_coverage_needs",
})
_COLLECTION_COUNT_KEYS = frozenset({
    "captures", "passages", "statement_candidates", "claim_candidates",
    "collection_coverage_needs",
})
_COLLECTION_COUNTS_SQL = """
SELECT json_build_object(
    'captures', (SELECT count(*) FROM content_capture capture
        JOIN research_collection_content member ON member.content_id=capture.content_id
        WHERE member.collection_id='research:garlasco' AND member.status='INCLUDED'),
    'passages', (SELECT count(*) FROM passage passage
        JOIN research_collection_content member ON member.content_id=passage.content_id
        WHERE member.collection_id='research:garlasco' AND member.status='INCLUDED'),
    'statement_candidates', (SELECT count(*) FROM statement_candidate candidate
        JOIN research_collection_content member ON member.content_id=candidate.content_id
        WHERE member.collection_id='research:garlasco' AND member.status='INCLUDED'),
    'claim_candidates', (SELECT count(*) FROM claim_candidate candidate
        JOIN research_collection_content member ON member.content_id=candidate.content_id
        WHERE member.collection_id='research:garlasco' AND member.status='INCLUDED'),
    'collection_coverage_needs', (SELECT count(*) FROM coverage_need
        WHERE collection_id='research:garlasco')
)::text;
""".strip()


def read_live_collection_counts(reader: Any) -> dict[str, int]:
    """Count all actually included Garlasco Content, including post-baseline intake."""
    try:
        raw = reader.run(_COLLECTION_COUNTS_SQL)
        counts = json.loads(raw)
    except (ValueError, TypeError, json.JSONDecodeError):
        raise ValueError("DP420_COLLECTION_COUNTS_INVALID") from None
    except Exception:
        raise RuntimeError("DP420_COLLECTION_READBACK_UNAVAILABLE") from None
    if (not isinstance(counts, dict) or set(counts) != _COLLECTION_COUNT_KEYS
            or any(type(value) is not int or value < 0 for value in counts.values())):
        raise ValueError("DP420_COLLECTION_COUNTS_INVALID")
    return counts


_VERIFY_BINDINGS_SQL = """
SELECT observation.task_id
FROM jsonb_to_recordset(:'observations'::jsonb) AS observation(
    task_id text, source_id text, capture_id text, passage_id text,
    statement_candidate_id text, rights_record_id text, coverage_need_id text,
    expected_result_ids text[]
)
WHERE (
    observation.task_id='coverage-gap'
    AND observation.coverage_need_id IS NOT NULL
    AND EXISTS (SELECT 1 FROM coverage_need need
                WHERE need.id=observation.coverage_need_id
                  AND need.collection_id='research:garlasco')
) OR (
    observation.task_id<>'coverage-gap'
    AND observation.coverage_need_id IS NULL
    AND EXISTS (
        SELECT 1 FROM research_collection_content member
        JOIN content_item item ON item.id=member.content_id
        JOIN source source ON source.id=item.source_id
        JOIN content_capture capture ON capture.content_id=item.id
        JOIN private_source_rights_record rights ON rights.content_id=item.id
        WHERE member.collection_id='research:garlasco'
          AND member.status='INCLUDED'
          AND source.id=observation.source_id
          AND capture.id=observation.capture_id
          AND capture.status='CAPTURED'
          AND rights.id=observation.rights_record_id
          AND rights.rights_status='CLEARED'
          AND rights.record_visibility='PRIVATE'
          AND rights.rights_receipt_ref IS NOT NULL
          AND rights.reviewed_at IS NOT NULL
          AND rights.reviewer_ref IS NOT NULL
          AND (rights.expires_at IS NULL OR rights.expires_at>current_timestamp)
          AND rights.locator_kind='URL'
          AND rights.locator_value=capture.final_url
          AND rights.permitted_uses @> ARRAY['FETCH','STORE_BODY','RESEARCH_CAPTURE_PRIVATE']::text[]
          AND NOT EXISTS (SELECT 1 FROM private_source_rights_record successor
                          WHERE successor.supersedes_id=rights.id)
          AND (observation.expected_result_ids IS NULL OR (
              cardinality(observation.expected_result_ids)>0
              AND EXISTS (SELECT 1 FROM atomic_claim claim
                          WHERE claim.content_id=item.id
                            AND (claim.id=ANY(observation.expected_result_ids)
                                 OR claim.speaker_person_id=ANY(observation.expected_result_ids)))))
          AND (observation.passage_id IS NULL OR EXISTS (
              SELECT 1 FROM passage passage
              WHERE passage.id=observation.passage_id
                AND passage.content_id=item.id AND passage.capture_id=capture.id))
          AND (observation.statement_candidate_id IS NULL OR EXISTS (
              SELECT 1 FROM statement_candidate candidate
              JOIN statement_candidate_passage link
                ON link.statement_candidate_id=candidate.id
               AND link.content_id=candidate.content_id
              JOIN passage passage ON passage.id=link.passage_id
              WHERE candidate.id=observation.statement_candidate_id
                AND candidate.content_id=item.id
                AND passage.id=observation.passage_id
                AND passage.capture_id=capture.id))
    )
)
ORDER BY observation.task_id;
""".strip()


def read_verified_task_bindings(reader: Any, observations: Mapping[str, Any]) -> set[str]:
    """Verify capture/rights lineage against the observed search result's Content."""
    if not isinstance(observations, dict) or len(observations) > 25:
        raise ValueError("DP420_OBSERVATIONS_INVALID")
    _, tasks = _load_tasks()
    search_by_task = {task["id"]: task["search_case"] for task in tasks if "search_case" in task}
    _, _, _, gold = load_fixture()
    gold_by_id = {case.id: list(case.expected_any_ids) for case in gold}
    records = [dict(task_id=name, **({"expected_result_ids": gold_by_id[search_by_task[name]]}
                                     if name in search_by_task else {}), **{
        key: value for key, value in observed.items()
        if key in {"source_id", "capture_id", "passage_id", "statement_candidate_id",
                   "rights_record_id", "coverage_need_id"} and isinstance(value, str)
    }) for name, observed in observations.items() if isinstance(observed, dict)
        and observed.get("status") == "PASS"]
    if not records:
        return set()
    try:
        verified = set(reader.run(_VERIFY_BINDINGS_SQL, observations=json.dumps(records)).splitlines())
    except Exception:
        raise RuntimeError("DP420_BINDINGS_READBACK_UNAVAILABLE") from None
    if not verified <= {record["task_id"] for record in records}:
        raise ValueError("DP420_BINDINGS_INVALID")
    return verified


def _load_tasks() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    fixture = json.loads(TASKS_PATH.read_text(encoding="utf-8"))
    if fixture.get("version") != "studio-garlasco-usability-v1":
        raise ValueError("DP420_TASK_VERSION_INVALID")
    tasks = fixture.get("tasks")
    modes = fixture.get("modes")
    if (
        not isinstance(tasks, list) or not 15 <= len(tasks) <= 25
        or not isinstance(modes, list) or set(modes) != _REQUIRED_MODES
        or len(modes) != len(_REQUIRED_MODES)
    ):
        raise ValueError("DP420_TASK_COVERAGE_INVALID")
    _, _, _, gold = load_fixture()
    search_ids = {case.id for case in gold}
    used_search: list[str] = []
    ids: list[str] = []
    for task in tasks:
        if not isinstance(task, dict) or not isinstance(task.get("goal"), str):
            raise ValueError("DP420_TASK_INVALID")
        name, needs = task.get("id"), task.get("requires")
        if not isinstance(name, str) or not re.fullmatch(r"[a-z0-9-]{3,64}", name):
            raise ValueError("DP420_TASK_ID_INVALID")
        if not isinstance(needs, list) or not needs or not set(needs) <= _ALLOWED_NEEDS:
            raise ValueError("DP420_TASK_PREREQUISITES_INVALID")
        ids.append(name)
        if "search_case" in task:
            used_search.append(task["search_case"])
    if len(ids) != len(set(ids)) or set(used_search) != search_ids or len(used_search) != len(search_ids):
        raise ValueError("DP420_TASK_SEARCH_GOLD_DRIFT")
    return fixture, tasks


def _observed_pass(observed: object, task: Mapping[str, Any], max_actions: int) -> bool:
    if not isinstance(observed, dict) or observed.get("status") != "PASS":
        return False
    elapsed = observed.get("time_to_source_ms")
    actions = observed.get("actions")
    errors = observed.get("navigation_errors")
    if (
        type(elapsed) not in (float, int) or elapsed <= 0
        or type(actions) is not int or not 1 <= actions <= max_actions
        or type(errors) is not int or errors != 0
        or not isinstance(observed.get("evidence_ref"), str)
        or not _EVIDENCE.fullmatch(observed["evidence_ref"])
    ):
        return False
    if "collection_coverage_needs" in task["requires"]:
        need_id = observed.get("coverage_need_id")
        return isinstance(need_id, str) and bool(_COVERAGE_NEED.fullmatch(need_id))
    if "coverage_need_id" in observed:
        return False
    if (
        not isinstance(observed.get("source_id"), str)
        or not _IDENTITY.fullmatch(observed["source_id"])
        or not observed["source_id"].startswith("source:")
        or not isinstance(observed.get("rights_record_id"), str)
        or not _RIGHTS.fullmatch(observed["rights_record_id"])
    ):
        return False
    for need, prefix in (("captures", "capture:"), ("passages", "passage:")):
        if need in task["requires"]:
            value = observed.get(need.removesuffix("s") + "_id")
            if not isinstance(value, str) or not _IDENTITY.fullmatch(value) or not value.startswith(prefix):
                return False
    if "statement_candidates" in task["requires"]:
        candidate_id = observed.get("statement_candidate_id")
        if not isinstance(candidate_id, str) or not _CANDIDATE.fullmatch(candidate_id):
            return False
    return True


def evaluate_acceptance(
    inventory: Mapping[str, Any],
    search: Mapping[str, Any],
    *,
    observations: Mapping[str, Any] | None = None,
    verified_tasks: set[str] | frozenset[str] = frozenset(),
) -> dict[str, Any]:
    """Evaluate the frozen tasks. Missing data and unobserved UI are HOLD, not PASS."""
    fixture, tasks = _load_tasks()
    observations = observations or {}
    task_observations = observations.get("tasks", {})
    mode_observations = observations.get("modes", {})
    if not isinstance(task_observations, dict) or not isinstance(mode_observations, dict):
        raise ValueError("DP420_OBSERVATIONS_INVALID")
    if set(task_observations) - {task["id"] for task in tasks}:
        raise ValueError("DP420_OBSERVATION_UNKNOWN_TASK")
    if set(mode_observations) - _REQUIRED_MODES:
        raise ValueError("DP420_OBSERVATION_UNKNOWN_MODE")

    measured = search.get("cases", [])
    if not isinstance(measured, list):
        raise ValueError("DP420_SEARCH_RESULT_INVALID")
    found = {item["id"]: item["passed"] for item in measured}
    expected = {task["search_case"] for task in tasks if "search_case" in task}
    if (
        set(found) != expected or len(measured) != len(expected)
        or any(type(value) is not bool for value in found.values())
    ):
        raise ValueError("DP420_SEARCH_GOLD_INCOMPLETE")
    counts = inventory.get("counts", {})
    if not isinstance(counts, dict) or inventory.get("publication_authority") is not False:
        raise ValueError("DP420_PRIVATE_INVENTORY_INVALID")

    passed = held = failed = 0
    task_status: dict[str, str] = {}
    for task in tasks:
        name = task["id"]
        observation = task_observations.get(name)
        if isinstance(observation, dict) and observation.get("status") == "FAIL":
            state = "FAIL"
        elif "search_case" in task and not found[task["search_case"]]:
            state = "FAIL"
        elif any(type(counts.get(key)) is not int or counts[key] < 1 for key in task["requires"]):
            state = "HOLD"
        elif name in verified_tasks and _observed_pass(observation, task, fixture["max_source_actions"]):
            state = "PASS"
        else:
            state = "HOLD"
        task_status[name] = state
        passed += state == "PASS"
        held += state == "HOLD"
        failed += state == "FAIL"

    mode_pass = sum(
        isinstance(mode_observations.get(mode), dict)
        and mode_observations[mode].get("status") == "PASS"
        and isinstance(mode_observations[mode].get("evidence_ref"), str)
        and bool(_EVIDENCE.fullmatch(mode_observations[mode]["evidence_ref"]))
        for mode in _REQUIRED_MODES
    )
    mode_failed = sum(
        isinstance(mode_observations.get(mode), dict)
        and mode_observations[mode].get("status") == "FAIL"
        for mode in _REQUIRED_MODES
    )
    failed_search = sum(not value for value in found.values())
    times = sorted(
        item["time_to_source_ms"] for item in task_observations.values()
        if isinstance(item, dict) and item.get("status") in ("PASS", "FAIL")
        and type(item.get("time_to_source_ms")) in (float, int)
        and item["time_to_source_ms"] > 0
    )
    navigation_errors = sum(
        item["navigation_errors"] for item in task_observations.values()
        if isinstance(item, dict) and type(item.get("navigation_errors")) is int
        and item["navigation_errors"] >= 0
    )
    status = "FAIL" if failed or failed_search or mode_failed else (
        "PASS" if passed == len(tasks) and mode_pass == len(_REQUIRED_MODES) else "HOLD"
    )
    return {
        "version": fixture["version"],
        "status": status,
        "accepted": status == "PASS",
        "private_only": True,
        "publication_authority": False,
        "collection_id": "research:garlasco",
        "seed_sha256": inventory.get("seed_sha256"),
        "total_tasks": len(tasks),
        "operator_passed": passed,
        "operator_hold": held,
        "operator_failed": failed,
        "mode_passed": mode_pass,
        "mode_hold": len(_REQUIRED_MODES) - mode_pass - mode_failed,
        "mode_failed": mode_failed,
        "search_cases_total": len(expected),
        "search_cases_passed": len(expected) - failed_search,
        "search_p95_ms": search.get("p95_ms"),
        "operator_timed_tasks": len(times),
        "operator_time_to_source_p95_ms": (
            times[max(0, min(len(times) - 1, int((len(times) - 1) * 0.95 + 0.999999)))]
            if times else None
        ),
        "operator_navigation_errors": navigation_errors,
        "task_status": task_status,
    }


def _load_private_observations(path: Path) -> Mapping[str, Any]:
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(fd, "r", encoding="utf-8") as stream:
        metadata = os.fstat(stream.fileno())
        if (not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid()
                or metadata.st_mode & 0o077):
            raise ValueError("DP420_OBSERVATIONS_UNSAFE")
        if metadata.st_size > 65536:
            raise ValueError("DP420_OBSERVATIONS_OVERSIZED")
        loaded = json.loads(stream.read(65537))
    if not isinstance(loaded, dict) or loaded.get("version") != "studio-garlasco-usability-v1":
        raise ValueError("DP420_OBSERVATIONS_VERSION_INVALID")
    return loaded


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only DP-420 private Studio usability acceptance")
    parser.add_argument("--observations", type=Path, help="Operator-only 0600 JSON evidence and timings")
    args = parser.parse_args(argv)
    try:
        operator = _load_private_observations(args.observations) if args.observations else None
        reader = _StudioReadOnlyDb()
        inventory = build_live_inventory(reader).receipt()
        # The historical inventory counts only Content referenced by the first
        # 30 Garlasco claims; acceptance must also see newer included Content.
        inventory["counts"].update(read_live_collection_counts(reader))
        search = run_benchmark(CorpusSearchStore()).to_dict()
        verified = read_verified_task_bindings(reader, operator.get("tasks", {})) if operator else set()
        receipt = evaluate_acceptance(inventory, search, observations=operator, verified_tasks=verified)
    except (ValueError, RuntimeError, OSError, KeyError, TypeError, json.JSONDecodeError):
        print(json.dumps({"status": "BLOCKED", "reason_code": "DP420_ACCEPTANCE_UNAVAILABLE"}))
        return 2
    print(json.dumps(receipt, sort_keys=True))
    return 0 if receipt["accepted"] else 1 if receipt["status"] == "FAIL" else 2


if __name__ == "__main__":
    raise SystemExit(main())
