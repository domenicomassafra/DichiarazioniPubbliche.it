#!/usr/bin/env python3
"""Independent cross-language DP-431 review: actual TS builder vs Python guard.

Bounded synthetic fixtures only; this script does not publish, access a DB,
read private corpus material or require any HTTP/provider services.
"""
from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "web"
sys.path[:0] = [str(ROOT / "poc"), str(ROOT / "tests")]
from test_correction_propagation import check, scenarios, search_index  # noqa: E402
from dichiarazioni_pubbliche import correction_propagation as propagation  # noqa: E402


def _real_typescript(projections: list[dict]) -> list[list[dict]]:
    js = """
import {buildSearchIndexMaterial} from './src/lib/searchIndex.ts';
let data='';
for await (const chunk of process.stdin) data += chunk;
const items=JSON.parse(data);
process.stdout.write(JSON.stringify(items.map(item=>buildSearchIndexMaterial(item).records)));
"""
    command = ["node", "--experimental-strip-types", "--input-type=module", "-e", js]
    result = subprocess.run(
        command, cwd=WEB, input=json.dumps(projections, ensure_ascii=False),
        encoding="utf-8", stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        env={**os.environ, "NODE_NO_WARNINGS": "1"}, timeout=30, check=False,
    )
    if result.returncode != 0:
        raise AssertionError(f"real TS search index builder failed: {result.stderr[-2500:]}")
    return json.loads(result.stdout)


def main() -> None:
    cases = scenarios()
    projections = [case[key] for case in cases for key in ("old_projection", "new_projection")]
    # First-class Contents and legacy fallback must both match the actual TS
    # builder. The topical facet cannot inherit any private candidate source.
    for present in (True, False):
        shaped = copy.deepcopy(cases[0]["new_projection"])
        if not present:
            shaped.pop("contents", None)
        shaped["dossiers"][0]["speaker"]["public_roles"] = [
            {"role": "Consigliere", "organization_name": "Ente pubblico"}
        ]
        shaped["dossiers"][0]["finding"]["published_at"] = "2026-10-12"
        shaped["dossiers"][0]["corrections"] = [{"id": "correction:1"}]
        shaped["dossiers"][0]["rights_of_reply"] = [{"id": "reply:1"}]
        shaped["dossiers"][0]["wording"] = {
            "source_occurrence": {"wording_type": "REPORTED_QUOTE"}
        }
        projections.append(shaped)
    built = _real_typescript(projections)
    expected_types = {"finding", "person", "topic", "content"}
    types_seen: set[str] = set()
    for number, (projection, records) in enumerate(zip(projections, built, strict=True)):
        state = propagation._projection_state(projection)
        canonical = propagation._expected_search_records(state)
        actual = {(record["kind"], record["id"]): record for record in records}
        types_seen.update(record["kind"] for record in records)
        if actual != canonical or len(records) != len(actual):
            raise AssertionError(f"DP431_TS_PY_METADATA_PARITY_FAIL:fixture:{number}")
    assert types_seen == expected_types, types_seen

    # Real public Topic membership contains only one reviewed Finding.
    # Injecting a *nonpublic* membership or a private term under the unchanged
    # fingerprint must force HOLD; no private roster has been loaded here.
    scenario = copy.deepcopy(cases[0])
    index = search_index(scenario["new_projection"])
    finding = next(row for row in index["records"] if row["kind"] == "finding")
    safe_topics = list(finding["topic_ids"])
    for change in (
        lambda row: row["topic_ids"].append("topic:private-candidate"),
        lambda row: row.pop("topic_ids"),
        lambda row: row.update({"private_note": "PRIVATE_CANDIDATE"}),
        lambda row: row.update({"secondary_terms": ["PRIVATE_CANDIDATE"]}),
    ):
        bad = copy.deepcopy(index)
        changed = next(row for row in bad["records"] if row["kind"] == "finding")
        change(changed)
        receipt = check(scenario, search_index=bad)
        assert not receipt.consistent and "SEARCH_INDEX_STALE_METADATA" in receipt.blockers
    assert finding["topic_ids"] == safe_topics
    print(f"DP431_TS_PY_PARITY_PASS {len(projections)} real TS builds; 4 kinds; first-class/legacy Content; private facet/missing/extra HOLD")


if __name__ == "__main__":
    main()
