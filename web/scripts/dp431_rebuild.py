#!/usr/bin/env python3
"""Fail-closed static rebuild guard for DP-431.

The guard retires the currently served directory before a changed projection is rebuilt,
builds Astro into a clean sibling staging directory, binds every generated file to the new
projection fingerprint in a route/static manifest, and reuses the canonical
correction-propagation checker before publishing the staged directory.

This module is build tooling only. It does not create publication authority or read the
operational database.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Iterable, Mapping


WEB_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = WEB_ROOT.parent
sys.path.insert(0, str(REPO_ROOT / "poc"))

import dichiarazioni_pubbliche.correction_propagation as propagation  # noqa: E402
from dichiarazioni_pubbliche.correction_propagation import (  # noqa: E402
    ROUTE_STATIC_MANIFEST_VERSION,
    check_correction_propagation,
)
from dichiarazioni_pubbliche.linked_data import (  # noqa: E402
    projection_linked_data_receipt,
    projection_ntriples,
)


REBUILD_RECEIPT_VERSION = "dp431-static-rebuild-v1"
HOLD_VERSION = "dp431-static-hold-v1"


class RebuildGuardError(RuntimeError):
    def __init__(self, code: str, *, details: Mapping[str, Any] | None = None):
        super().__init__(code)
        self.code = code
        self.details = dict(details or {})


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RebuildGuardError("DP431_PROJECTION_READ_FAILED", details={"path": str(path)}) from exc
    if not isinstance(value, dict):
        raise RebuildGuardError("DP431_PROJECTION_INVALID", details={"path": str(path)})
    return value


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _public_id_slug(value: str) -> str:
    output = []
    dash = False
    for char in str(value).lower():
        if "a" <= char <= "z" or "0" <= char <= "9":
            output.append(char)
            dash = False
        elif output and not dash:
            output.append("-")
            dash = True
    return "".join(output).strip("-")


def _route_file(root: Path, route: str) -> Path:
    normalized = route.strip("/")
    return root / (normalized or ".") / "index.html"


def _route_for_file(root: Path, path: Path) -> str:
    rel = path.relative_to(root).as_posix()
    if rel == "index.html":
        return "/"
    if rel.endswith("/index.html"):
        return f"/{rel[:-len('index.html')]}"
    return f"/{rel}"


def _expected_routes(projection: Mapping[str, Any]) -> dict[str, dict[str, str]]:
    state = propagation._projection_state(projection)
    dossiers = [row for row in projection.get("dossiers") or [] if isinstance(row, Mapping)]
    topics = [row for row in projection.get("topics") or [] if isinstance(row, Mapping)]
    contents = [row for row in projection.get("contents") or [] if isinstance(row, Mapping)]

    routes: dict[str, dict[str, str]] = {
        "finding": {},
        "person": {},
        "topic": {},
        "content": {},
        "trace": {},
    }
    for finding_id in state.findings:
        routes["finding"][finding_id] = f"/dichiarazioni/{_public_id_slug(finding_id)}/"
    for person_id in state.people:
        routes["person"][person_id] = f"/persone/{_public_id_slug(person_id)}/"

    topic_by_id = {str(row.get("topic_id") or ""): row for row in topics}
    for topic_id in state.topics:
        row = topic_by_id.get(topic_id) or {}
        slug = str(row.get("slug") or "").strip() or _public_id_slug(topic_id)
        routes["topic"][topic_id] = f"/temi/{slug}/"

    explicit_content_by_id = {str(row.get("content_id") or ""): row for row in contents}
    for content_id in state.contents:
        row = explicit_content_by_id.get(content_id) or {}
        slug = str(row.get("slug") or "").strip() or _public_id_slug(content_id)
        routes["content"][content_id] = f"/contenuti/{slug}/"

    for dossier in dossiers:
        for relation in dossier.get("relations") or []:
            if not isinstance(relation, Mapping):
                continue
            if relation.get("status") != "APPROVED" or not relation.get("review_event_id"):
                continue
            relation_id = str(relation.get("id") or "").strip()
            if relation_id:
                routes["trace"][relation_id] = f"/tracce/{_public_id_slug(relation_id)}/"
    return routes


def _all_built_routes(root: Path) -> set[str]:
    if not root.is_dir():
        return set()
    return {
        _route_for_file(root, path)
        for path in root.rglob("index.html")
        if path.is_file()
    }


def _assert_exact_route_families(root: Path, projection: Mapping[str, Any]) -> None:
    expected = _expected_routes(projection)
    routes = _all_built_routes(root)
    route_sets = {
        "finding": set(expected["finding"].values()),
        "person": set(expected["person"].values()),
        "topic": set(expected["topic"].values()),
        "content": set(expected["content"].values()),
        "trace": set(expected["trace"].values()),
    }
    prefix_by_kind = {
        "finding": "/dichiarazioni/",
        "person": "/persone/",
        "topic": "/temi/",
        "content": "/contenuti/",
        "trace": "/tracce/",
    }
    for kind, prefix in prefix_by_kind.items():
        actual = {route for route in routes if route.startswith(prefix)}
        if actual != route_sets[kind]:
            raise RebuildGuardError(
                "DP431_ROUTE_INVENTORY_MISMATCH",
                details={
                    "kind": kind,
                    "missing": sorted(route_sets[kind] - actual),
                    "unexpected": sorted(actual - route_sets[kind]),
                },
            )

    legacy_expected = {
        "/fact-check/": {
            route.replace("/dichiarazioni/", "/fact-check/", 1)
            for route in route_sets["finding"]
        },
        "/contents/": {
            route.replace("/contenuti/", "/contents/", 1)
            for route in route_sets["content"]
        },
        "/compare/": {
            route.replace("/tracce/", "/compare/", 1)
            for route in route_sets["trace"]
        },
    }
    person_slugs = {route.removeprefix("/persone/").strip("/") for route in route_sets["person"]}
    legacy_expected["/record/"] = {
        *(f"/record/{slug}/" for slug in person_slugs),
        *(f"/record/person/{slug}/" for slug in person_slugs),
    }
    for prefix, expected_routes in legacy_expected.items():
        if prefix == "/record/":
            actual = {route for route in routes if route.startswith(prefix)}
        else:
            actual = {route for route in routes if route.startswith(prefix)}
        if actual != expected_routes:
            raise RebuildGuardError(
                "DP431_LEGACY_ROUTE_INVENTORY_MISMATCH",
                details={
                    "prefix": prefix,
                    "missing": sorted(expected_routes - actual),
                    "unexpected": sorted(actual - expected_routes),
                },
            )


def _assert_entity_text(root: Path, projection: Mapping[str, Any]) -> None:
    state = propagation._projection_state(projection)
    routes = _expected_routes(projection)
    for kind in ("finding", "person", "topic", "content"):
        for identifier, route in routes[kind].items():
            path = _route_file(root, route)
            if not path.is_file():
                continue
            title = state.titles.get((kind, identifier))
            rendered = html.unescape(path.read_text(encoding="utf-8"))
            if title and title not in rendered:
                raise RebuildGuardError(
                    "DP431_ROUTE_ENTITY_TEXT_STALE",
                    details={"kind": kind, "id": identifier, "route": route},
                )


def _search_index_hash(index: Mapping[str, Any]) -> str:
    material = {key: value for key, value in index.items() if key != "index_sha256"}
    return _sha256_bytes(_stable_json(material).encode("utf-8"))


def _load_search_index(root: Path, expected_fingerprint: str) -> dict[str, Any]:
    path = root / "search-index.v1.json"
    if not path.is_file():
        raise RebuildGuardError("DP431_SEARCH_INDEX_MISSING")
    value = _load_json(path)
    if value.get("projection_sha256") != expected_fingerprint:
        raise RebuildGuardError(
            "DP431_SEARCH_INDEX_FINGERPRINT_MISMATCH",
            details={"observed": value.get("projection_sha256"), "expected": expected_fingerprint},
        )
    claimed = str(value.get("index_sha256") or "")
    actual = _search_index_hash(value)
    if claimed != actual:
        raise RebuildGuardError(
            "DP431_SEARCH_INDEX_HASH_MISMATCH",
            details={"claimed": claimed, "actual": actual},
        )
    return value


def _write_linked_data(root: Path, projection: dict[str, Any]) -> dict[str, Any]:
    triples = projection_ntriples(projection)
    receipt = projection_linked_data_receipt(projection)
    (root / "index.nt").write_text(triples, encoding="utf-8")
    _atomic_json(root / "linked-data-receipt.json", receipt)
    return receipt


def _file_inventory(root: Path, fingerprint: str) -> list[dict[str, Any]]:
    output = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        rel = path.relative_to(root).as_posix()
        output.append(
            {
                "path": rel,
                "bytes": path.stat().st_size,
                "sha256": _sha256_file(path),
                "projection_fingerprint": fingerprint,
            }
        )
    return output


def _route_static_manifest(
    root: Path,
    projection: Mapping[str, Any],
) -> dict[str, Any]:
    state = propagation._projection_state(projection)
    expected = _expected_routes(projection)
    entries: list[dict[str, Any]] = []
    for kind in propagation._ENTITY_KINDS:
        for identifier, route in sorted(expected[kind].items()):
            path = _route_file(root, route)
            if not path.is_file():
                continue
            entries.append(
                {
                    "artifact_id": f"current:{kind}:{identifier}",
                    "entity_kind": kind,
                    "entity_id": identifier,
                    "view": "CURRENT",
                    "projection_fingerprint": state.fingerprint,
                    "entity_sha256": state.entity_sha256[(kind, identifier)],
                    "route": route,
                    "file_sha256": _sha256_file(path),
                }
            )

    return {
        "manifest_version": ROUTE_STATIC_MANIFEST_VERSION,
        "projection_fingerprint": state.fingerprint,
        "entries": entries,
        "trace_routes": sorted(expected["trace"].values()),
        "files": _file_inventory(root, state.fingerprint),
    }


def _install_hold(publish_dir: Path, run_id: str, old_fp: str, new_fp: str) -> None:
    publish_dir.parent.mkdir(parents=True, exist_ok=True)
    retired = publish_dir.parent / f".dp431-retired-{run_id}"
    if retired.exists():
        shutil.rmtree(retired)
    if publish_dir.exists():
        os.replace(publish_dir, retired)

    hold = publish_dir.parent / f".dp431-hold-{run_id}"
    if hold.exists():
        shutil.rmtree(hold)
    hold.mkdir(parents=True)
    (hold / "index.html").write_text(
        "<!doctype html><html lang=\"it\"><meta charset=\"utf-8\">"
        "<meta name=\"robots\" content=\"noindex,nofollow\">"
        "<title>Registro temporaneamente non disponibile</title>"
        "<main><h1>Registro temporaneamente non disponibile</h1>"
        "<p>È in corso una rigenerazione del record pubblico. Nessun dato precedente viene servito come corrente.</p></main>",
        encoding="utf-8",
    )
    _atomic_json(
        hold / "dp431-hold.json",
        {
            "version": HOLD_VERSION,
            "status": "HOLD",
            "old_projection_fingerprint": old_fp,
            "new_projection_fingerprint": new_fp,
        },
    )
    os.replace(hold, publish_dir)
    if retired.exists():
        shutil.rmtree(retired)


def _replace_hold_with_stage(publish_dir: Path, stage: Path, run_id: str) -> None:
    old_hold = publish_dir.parent / f".dp431-old-hold-{run_id}"
    if old_hold.exists():
        shutil.rmtree(old_hold)
    if publish_dir.exists():
        os.replace(publish_dir, old_hold)
    try:
        os.replace(stage, publish_dir)
    except Exception:
        if old_hold.exists() and not publish_dir.exists():
            os.replace(old_hold, publish_dir)
        raise
    if old_hold.exists():
        shutil.rmtree(old_hold)


def _run_astro_build(stage: Path, projection_path: Path) -> None:
    env = os.environ.copy()
    env["DICHIARAZIONI_PUBBLICHE_PUBLIC_PROJECTION_PATH"] = str(projection_path.resolve())
    env.pop("DICHIARAZIONI_PUBBLICHE_ALLOW_DEMO_PROJECTION", None)
    command = [str(WEB_ROOT / "node_modules" / ".bin" / "astro"), "build", "--force", "--outDir", str(stage)]
    result = subprocess.run(
        command,
        cwd=WEB_ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if result.returncode != 0:
        raise RebuildGuardError(
            "DP431_ASTRO_BUILD_FAILED",
            details={"returncode": result.returncode, "output": result.stdout[-8000:]},
        )


def _inject_failure(
    stage: Path,
    mode: str,
    old_projection: Mapping[str, Any],
    new_projection: Mapping[str, Any],
) -> None:
    if mode == "none":
        return
    if mode == "search-fingerprint":
        path = stage / "search-index.v1.json"
        index = _load_json(path)
        index["projection_sha256"] = old_projection["dataset_sha256"]
        _atomic_json(path, index)
        return
    if mode == "partial-route":
        expected = _expected_routes(new_projection)
        for kind in ("finding", "person", "topic", "content"):
            routes = list(expected[kind].values())
            if routes:
                target = _route_file(stage, routes[0])
                if target.exists():
                    target.unlink()
                    return
        raise RebuildGuardError("DP431_FAILURE_INJECTION_NO_ROUTE")
    if mode == "stale-statement":
        old = propagation._projection_state(old_projection)
        new = propagation._projection_state(new_projection)
        removed = sorted(set(old.findings) - set(new.findings))
        if not removed:
            raise RebuildGuardError("DP431_FAILURE_INJECTION_NO_REMOVED_FINDING")
        identifier = removed[0]
        route = f"/dichiarazioni/{_public_id_slug(identifier)}/"
        target = _route_file(stage, route)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            f"<!doctype html><html lang=\"it\"><main><h1>{html.escape(old.titles[('finding', identifier)])}</h1></main>",
            encoding="utf-8",
        )
        return
    raise RebuildGuardError("DP431_FAILURE_INJECTION_UNKNOWN", details={"mode": mode})


def _receipt_paths(receipt_dir: Path, run_id: str) -> tuple[Path, Path]:
    return receipt_dir / f"{run_id}.json", receipt_dir / "latest.json"


def _write_operator_receipt(receipt_dir: Path, run_id: str, value: Mapping[str, Any]) -> None:
    run_path, latest_path = _receipt_paths(receipt_dir, run_id)
    _atomic_json(run_path, value)
    _atomic_json(latest_path, value)


def rebuild_static(
    *,
    old_projection_path: Path,
    new_projection_path: Path,
    publish_dir: Path,
    receipt_dir: Path,
    inject_failure: str = "none",
) -> dict[str, Any]:
    old_projection = _load_json(old_projection_path)
    new_projection = _load_json(new_projection_path)
    old_state = propagation._projection_state(old_projection)
    new_state = propagation._projection_state(new_projection)
    if old_state.fingerprint == new_state.fingerprint:
        raise RebuildGuardError("DP431_REBUILD_REQUIRES_CHANGED_FINGERPRINT")

    run_id = f"{int(time.time() * 1000)}-{os.getpid()}"
    stage = publish_dir.parent / f".dp431-stage-{run_id}"
    if stage.exists():
        shutil.rmtree(stage)

    base_receipt: dict[str, Any] = {
        "version": REBUILD_RECEIPT_VERSION,
        "run_id": run_id,
        "old_projection_fingerprint": old_state.fingerprint,
        "new_projection_fingerprint": new_state.fingerprint,
        "publish_dir": str(publish_dir),
    }
    try:
        _install_hold(publish_dir, run_id, old_state.fingerprint, new_state.fingerprint)
        if inject_failure == "after-invalidate":
            raise RebuildGuardError("DP431_INJECTED_AFTER_INVALIDATE")

        _run_astro_build(stage, new_projection_path)
        linked_receipt = _write_linked_data(stage, new_projection)
        _inject_failure(stage, inject_failure, old_projection, new_projection)

        search_index = _load_search_index(stage, new_state.fingerprint)
        manifest = _route_static_manifest(stage, new_projection)
        propagation_receipt = check_correction_propagation(
            old_projection=old_projection,
            new_projection=new_projection,
            search_index=search_index,
            linked_data_receipt=linked_receipt,
            route_static_manifest=manifest,
        )
        if not propagation_receipt.consistent:
            raise RebuildGuardError(
                "DP431_PROPAGATION_HOLD",
                details={"propagation_receipt": asdict(propagation_receipt)},
            )

        _assert_exact_route_families(stage, new_projection)
        _assert_entity_text(stage, new_projection)

        result = {
            **base_receipt,
            "status": "CONSISTENT",
            "propagation_receipt": asdict(propagation_receipt),
            "route_static_manifest": manifest,
            "published_file_count": len(manifest["files"]),
        }
        _write_operator_receipt(receipt_dir, run_id, result)
        _replace_hold_with_stage(publish_dir, stage, run_id)
        return result
    except Exception as exc:
        if stage.exists():
            shutil.rmtree(stage)
        if isinstance(exc, RebuildGuardError):
            code = exc.code
            details = exc.details
        else:
            code = "DP431_REBUILD_UNEXPECTED_FAILURE"
            details = {"error_type": type(exc).__name__, "message": str(exc)}
        failure = {**base_receipt, "status": "HOLD", "error": code, "details": details}
        hold_receipt = publish_dir / "dp431-hold.json"
        if hold_receipt.is_file():
            _atomic_json(
                hold_receipt,
                {
                    "version": HOLD_VERSION,
                    "status": "HOLD",
                    "error": code,
                    "old_projection_fingerprint": old_state.fingerprint,
                    "new_projection_fingerprint": new_state.fingerprint,
                },
            )
        _write_operator_receipt(receipt_dir, run_id, failure)
        if isinstance(exc, RebuildGuardError):
            raise
        raise RebuildGuardError(code, details=details) from exc


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--old-projection", type=Path, required=True)
    parser.add_argument("--new-projection", type=Path, required=True)
    parser.add_argument("--publish-dir", type=Path, default=WEB_ROOT / "dist")
    parser.add_argument("--receipt-dir", type=Path, default=WEB_ROOT / ".dp431-receipts")
    parser.add_argument(
        "--inject-failure",
        choices=("none", "after-invalidate", "stale-statement", "search-fingerprint", "partial-route"),
        default="none",
    )
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = _parser().parse_args(list(argv) if argv is not None else None)
    try:
        receipt = rebuild_static(
            old_projection_path=args.old_projection,
            new_projection_path=args.new_projection,
            publish_dir=args.publish_dir.resolve(),
            receipt_dir=args.receipt_dir.resolve(),
            inject_failure=args.inject_failure,
        )
    except RebuildGuardError as exc:
        print(json.dumps({"status": "HOLD", "error": exc.code, "details": exc.details}, ensure_ascii=False))
        return 2
    print(
        json.dumps(
            {
                "status": receipt["status"],
                "old_projection_fingerprint": receipt["old_projection_fingerprint"],
                "new_projection_fingerprint": receipt["new_projection_fingerprint"],
                "published_file_count": receipt["published_file_count"],
                "propagation_receipt_sha256": receipt["propagation_receipt"]["receipt_sha256"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
