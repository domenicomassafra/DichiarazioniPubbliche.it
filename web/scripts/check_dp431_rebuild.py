#!/usr/bin/env python3
"""Failure-injection acceptance for the DP-431 static rebuild guard."""

from __future__ import annotations

import copy
import html
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


WEB_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = WEB_ROOT.parent
sys.path.insert(0, str(WEB_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "poc"))

from dp431_rebuild import RebuildGuardError, rebuild_static  # noqa: E402
from dichiarazioni_pubbliche.public_api import API_BASE_PATH, dispatch  # noqa: E402
from dichiarazioni_pubbliche.public_schema import (  # noqa: E402
    projection_dataset_sha256,
    validate_public_bundle,
)


def _write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _hold_projection(old: dict) -> tuple[dict, str, str, str, str]:
    new = copy.deepcopy(old)
    removed_dossier = new["dossiers"].pop(0)
    removed_finding = removed_dossier["finding_id"]
    removed_person = removed_dossier["speaker"]["id"]
    removed_content = removed_dossier["source"]["content_id"]
    removed_relations = [
        relation["id"]
        for relation in removed_dossier.get("relations") or []
        if relation.get("status") == "APPROVED" and relation.get("review_event_id")
    ]
    for topic in new.get("topics") or []:
        topic["memberships"] = [
            membership
            for membership in topic.get("memberships") or []
            if removed_finding not in (membership.get("finding_ids") or [])
        ]
    new["dossier_count"] = len(new["dossiers"])
    new["dataset_sha256"] = projection_dataset_sha256(new)
    validate_public_bundle(new)
    removed_relation = removed_relations[0] if removed_relations else ""
    return new, removed_finding, removed_person, removed_content, removed_relation


def _corrected_projection(old: dict) -> tuple[dict, str, str, str, list[str]]:
    new = copy.deepcopy(old)
    dossier = new["dossiers"][0]
    old_finding = dossier["finding_id"]
    new_finding = f"{old_finding}:v2"
    old_claim = dossier["claim"]
    new_claim = "La spesa di manutenzione è aumentata di circa il 12% rispetto all'anno precedente."
    dossier["finding_id"] = new_finding
    dossier["claim"] = new_claim
    dossier["finding"]["supersedes_id"] = old_finding
    for correction in dossier.get("corrections") or []:
        correction["previous_finding_id"] = old_finding
        correction["finding_id"] = new_finding
    for topic in new.get("topics") or []:
        for membership in topic.get("memberships") or []:
            membership["finding_ids"] = [
                new_finding if value == old_finding else value
                for value in membership.get("finding_ids") or []
            ]
    new["dataset_sha256"] = projection_dataset_sha256(new)
    validate_public_bundle(new)
    shared_routes = [
        f"persone/{_slug(dossier['speaker']['id'])}/index.html",
        f"contenuti/{_slug(dossier['source']['content_id'])}/index.html",
    ]
    for topic in new.get("topics") or []:
        if any(new_finding in (membership.get("finding_ids") or []) for membership in topic.get("memberships") or []):
            shared_routes.append(f"temi/{topic['slug']}/index.html")
    for relation in dossier.get("relations") or []:
        if relation.get("status") == "APPROVED" and relation.get("review_event_id"):
            shared_routes.append(f"tracce/{_slug(relation['id'])}/index.html")
    return new, old_finding, new_finding, old_claim, shared_routes


def _build_seed(projection_path: Path, output: Path) -> None:
    env = dict(**__import__("os").environ)
    env["DICHIARAZIONI_PUBBLICHE_PUBLIC_PROJECTION_PATH"] = str(projection_path)
    env.pop("DICHIARAZIONI_PUBBLICHE_ALLOW_DEMO_PROJECTION", None)
    result = subprocess.run(
        [str(WEB_ROOT / "node_modules" / ".bin" / "astro"), "build", "--force", "--outDir", str(output)],
        cwd=WEB_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(f"seed build failed:\n{result.stdout[-8000:]}")


def _slug(value: str) -> str:
    return "-".join(part for part in __import__("re").split(r"[^a-z0-9]+", value.lower()) if part)


def _record_slug(projection: dict, content_id: str) -> str:
    for content in projection.get("contents") or []:
        if content.get("content_id") == content_id and content.get("slug"):
            return str(content["slug"])
    return _slug(content_id)


def _api_json(projection_path: Path, route: str, *, expected_status: int = 200) -> dict:
    response = dispatch("GET", route, projection_path=str(projection_path))
    assert response.status == expected_status, f"{route}: API status {response.status}, expected {expected_status}"
    return json.loads(response.body)


def _assert_statement_metadata(
    page: Path,
    *,
    current_claim: str,
    current_finding: str,
    previous_finding: str,
) -> None:
    rendered = html.unescape(page.read_text(encoding="utf-8"))
    assert current_claim in rendered, "current Statement wording missing"
    assert current_finding in rendered, "current Statement finding id missing from history"
    assert previous_finding in rendered, "superseded finding id missing from current Statement history"

    title_match = re.search(r"<title>(.*?)</title>", rendered, flags=re.DOTALL)
    assert title_match and current_claim in title_match.group(1), "Statement title metadata is stale"
    og_title = re.search(r'<meta property="og:title" content="([^"]*)"', rendered)
    assert og_title and current_claim in og_title.group(1), "Statement social title metadata is stale"
    canonical = re.search(r'<link rel="canonical" href="([^"]*)"', rendered)
    expected_route = f"/dichiarazioni/{_slug(current_finding)}/"
    assert canonical and canonical.group(1) == expected_route, "Statement canonical metadata targets the wrong version"
    og_url = re.search(r'<meta property="og:url" content="([^"]*)"', rendered)
    assert og_url and og_url.group(1) == expected_route, "Statement social URL targets the wrong version"
    json_ld_match = re.search(
        r'<script type="application/ld\+json">(.*?)</script>',
        rendered,
        flags=re.DOTALL,
    )
    assert json_ld_match, "Statement JSON-LD metadata missing"
    structured = json.loads(json_ld_match.group(1))
    assert structured["identifier"] == current_finding, "Statement JSON-LD carries a stale finding id"
    assert structured["name"] == current_claim, "Statement JSON-LD carries stale wording"
    assert structured["url"] == expected_route, "Statement JSON-LD targets the wrong canonical route"


def _assert_hold_only(publish: Path) -> None:
    assert (publish / "index.html").is_file(), "fail-closed hold page missing"
    assert (publish / "dp431-hold.json").is_file(), "fail-closed hold receipt missing"
    assert not (publish / "search-index.v1.json").exists(), "stale search index remains current during HOLD"
    for family in ("dichiarazioni", "persone", "temi", "contenuti", "tracce"):
        assert not (publish / family).exists(), f"stale {family} routes remain current during HOLD"


def _run_failure_case(
    *,
    seed: Path,
    old_path: Path,
    new_path: Path,
    root: Path,
    mode: str,
) -> None:
    publish = root / f"publish-{mode}"
    receipts = root / f"receipts-{mode}"
    shutil.copytree(seed, publish)
    try:
        rebuild_static(
            old_projection_path=old_path,
            new_projection_path=new_path,
            publish_dir=publish,
            receipt_dir=receipts,
            inject_failure=mode,
        )
    except RebuildGuardError:
        pass
    else:
        raise AssertionError(f"failure injection unexpectedly published: {mode}")
    _assert_hold_only(publish)
    latest = json.loads((receipts / "latest.json").read_text(encoding="utf-8"))
    assert latest["status"] == "HOLD", f"{mode}: operator receipt not HOLD"


def main() -> int:
    old = json.loads((WEB_ROOT / "src" / "data" / "demo-projection.json").read_text(encoding="utf-8"))
    validate_public_bundle(old)
    new, removed_finding, removed_person, removed_content, removed_relation = _hold_projection(old)
    corrected, old_finding, corrected_finding, old_claim, corrected_shared_routes = _corrected_projection(old)

    # Astro may move prerendered assets with rename(2). Keep the acceptance
    # workspace on the same filesystem as web/.astro so Linux hosts where
    # /tmp is a separate mount do not fail with EXDEV before the DP-431 guard
    # itself is exercised.
    with tempfile.TemporaryDirectory(
        prefix=".dp431-static-rebuild-",
        dir=WEB_ROOT,
    ) as raw:
        root = Path(raw)
        old_path = root / "old.json"
        new_path = root / "held.json"
        corrected_path = root / "corrected.json"
        _write_json(old_path, old)
        _write_json(new_path, new)
        _write_json(corrected_path, corrected)

        seed = root / "seed"
        _build_seed(old_path, seed)
        (seed / "stale-static.txt").write_text("must disappear", encoding="utf-8")

        publish = root / "publish-success"
        receipts = root / "receipts-success"
        shutil.copytree(seed, publish)
        receipt = rebuild_static(
            old_projection_path=old_path,
            new_projection_path=new_path,
            publish_dir=publish,
            receipt_dir=receipts,
        )
        assert receipt["status"] == "CONSISTENT"
        assert receipt["propagation_receipt"]["status"] == "CONSISTENT"
        assert not (publish / "stale-static.txt").exists(), "old static orphan survived clean rebuild"
        assert not (publish / "dichiarazioni" / _slug(removed_finding)).exists(), "held Statement survived"
        assert not (publish / "persone" / _slug(removed_person)).exists(), "held Person survived"
        assert not (publish / "contenuti" / _slug(removed_content)).exists(), "held Content survived"
        if removed_relation:
            assert not (publish / "tracce" / _slug(removed_relation)).exists(), "held Trace survived"
        search = json.loads((publish / "search-index.v1.json").read_text(encoding="utf-8"))
        current_ids = {(row["kind"], row["id"]) for row in search["records"]}
        assert ("finding", removed_finding) not in current_ids
        assert ("person", removed_person) not in current_ids
        assert ("content", removed_content) not in current_ids
        assert search["projection_sha256"] == new["dataset_sha256"]
        assert (publish / "index.nt").is_file()
        linked = json.loads((publish / "linked-data-receipt.json").read_text(encoding="utf-8"))
        assert linked["projection_fingerprint"] == new["dataset_sha256"]
        held_health = _api_json(new_path, f"{API_BASE_PATH}/health")
        assert held_health["data"]["dataset_fingerprint"] == new["dataset_sha256"]
        held_api = _api_json(
            new_path,
            f"{API_BASE_PATH}/findings/{removed_finding}",
            expected_status=404,
        )
        assert held_api["error"]["code"] == "RESOURCE_NOT_FOUND"

        corrected_publish = root / "publish-corrected"
        corrected_receipts = root / "receipts-corrected"
        shutil.copytree(seed, corrected_publish)
        corrected_receipt = rebuild_static(
            old_projection_path=old_path,
            new_projection_path=corrected_path,
            publish_dir=corrected_publish,
            receipt_dir=corrected_receipts,
        )
        assert corrected_receipt["status"] == "CONSISTENT"
        assert not (corrected_publish / "dichiarazioni" / _slug(old_finding)).exists(), "superseded Statement survived"
        current_statement = corrected_publish / "dichiarazioni" / _slug(corrected_finding) / "index.html"
        assert current_statement.is_file(), "corrected Statement missing"
        assert corrected["dossiers"][0]["claim"] in html.unescape(current_statement.read_text(encoding="utf-8"))
        corrected_search = json.loads((corrected_publish / "search-index.v1.json").read_text(encoding="utf-8"))
        corrected_rows = {(row["kind"], row["id"]): row for row in corrected_search["records"]}
        assert ("finding", old_finding) not in corrected_rows, "superseded finding remains searchable"
        assert corrected_rows[("finding", corrected_finding)]["title"] == corrected["dossiers"][0]["claim"]
        corrected_health = _api_json(corrected_path, f"{API_BASE_PATH}/health")
        assert corrected_health["data"]["dataset_fingerprint"] == corrected["dataset_sha256"]
        corrected_api = _api_json(
            corrected_path,
            f"{API_BASE_PATH}/findings/{corrected_finding}",
        )
        assert corrected_api["meta"]["dataset_fingerprint"] == corrected["dataset_sha256"]
        assert corrected_api["data"]["finding_id"] == corrected_finding
        assert corrected_api["data"]["claim"] == corrected["dossiers"][0]["claim"]
        assert corrected_api["data"]["finding"]["supersedes_id"] == old_finding
        old_api = _api_json(
            corrected_path,
            f"{API_BASE_PATH}/findings/{old_finding}",
            expected_status=404,
        )
        assert old_api["error"]["code"] == "RESOURCE_NOT_FOUND"
        content_id = corrected["dossiers"][0]["source"]["content_id"]
        record_api = _api_json(
            corrected_path,
            f"{API_BASE_PATH}/records/{_record_slug(corrected, content_id)}",
        )
        assert record_api["meta"]["dataset_fingerprint"] == corrected["dataset_sha256"]
        assert [row["finding_id"] for row in record_api["data"]["findings"]] == [corrected_finding]
        _assert_statement_metadata(
            current_statement,
            current_claim=corrected["dossiers"][0]["claim"],
            current_finding=corrected_finding,
            previous_finding=old_finding,
        )
        for relative in corrected_shared_routes:
            page = corrected_publish / relative
            body = html.unescape(page.read_text(encoding="utf-8"))
            assert corrected["dossiers"][0]["claim"] in body, f"corrected wording missing from {relative}"
            assert old_claim not in body, f"stale wording survived in {relative}"

        for mode in ("after-invalidate", "stale-statement", "search-fingerprint", "partial-route"):
            _run_failure_case(
                seed=seed,
                old_path=old_path,
                new_path=new_path,
                root=root,
                mode=mode,
            )

        print(
            "dp431-rebuild checks PASS "
            f"(correction {old['dataset_sha256'][:12]} -> {corrected['dataset_sha256'][:12]}, "
            f"hold -> {new['dataset_sha256'][:12]}; stale Statement/Person/Topic/Content/Trace/search/static removed; "
            "API/current metadata/history converge; 4 failure injections fail closed)"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
