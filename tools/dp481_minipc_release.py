#!/usr/bin/env python3
"""DP-518A: immutable MiniPC release and HTTP readback. No GO-PUBLIC."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import hmac
import json
import os
import re
import shutil
import tempfile
import threading
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

if __package__:
    from .dp481_static_contract import check_static_contract
else:
    from dp481_static_contract import check_static_contract


HEX = re.compile(r"[a-f0-9]{64}\Z")
GIT = re.compile(r"[a-f0-9]{40}\Z")
MANIFEST = "manifest.json"


def fail(reason: str) -> None:
    raise ValueError("DP481_" + reason)


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False) + "\n").encode("utf-8")


def safe_files(directory: Path) -> dict[str, str]:
    """Inventory regular, singly linked files; never follow symlinks."""
    hashes: dict[str, str] = {}
    if directory.is_symlink() or not directory.is_dir():
        fail("UNSAFE_ASSET")
    for path in sorted(directory.rglob("*")):
        relative = path.relative_to(directory)
        if path.is_symlink() or (path.is_file() and path.stat().st_nlink != 1):
            fail("UNSAFE_ASSET")
        if any(part.startswith(".") and part != ".well-known" for part in relative.parts):
            fail("UNSAFE_ASSET")
        if path.is_dir():
            continue
        if not path.is_file():
            fail("UNSAFE_ASSET")
        hashes[relative.as_posix()] = file_hash(path)
    return hashes


def file_hash(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            sha.update(chunk)
    return sha.hexdigest()


def collect(release: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for prefix in ("code", "static", "projection"):
        hashes.update({f"{prefix}/{p}": h for p, h in safe_files(release / prefix).items()})
    return hashes


def pointer(root: Path) -> str | None:
    current = root / "current"
    if not current.is_symlink():
        if current.exists():
            fail("POINTER_INVALID")
        return None
    target = os.readlink(current)
    if not re.fullmatch(r"releases/[a-f0-9]{64}", target):
        fail("POINTER_INVALID")
    ident = target.split("/")[1]
    release = root / "releases" / ident
    if release.is_symlink() or not release.is_dir():
        fail("POINTER_INVALID")
    return ident


def validated(root: Path, ident: str) -> dict:
    if not HEX.fullmatch(ident):
        fail("RELEASE_ID_INVALID")
    release = root / "releases" / ident
    if release.is_symlink() or not release.is_dir():
        fail("RELEASE_MISSING")
    path = release / MANIFEST
    if path.is_symlink() or not path.is_file():
        fail("MANIFEST_INVALID")
    try:
        stored = json.loads(path.read_bytes())
    except (OSError, ValueError, UnicodeError):
        fail("MANIFEST_INVALID")
    if not isinstance(stored, dict) or stored.get("release_id") != ident:
        fail("MANIFEST_INVALID")
    material = {k: v for k, v in stored.items() if k != "release_id"}
    if not hmac.compare_digest(digest(canonical(material)), ident):
        fail("MANIFEST_INVALID")
    expected = stored.get("assets")
    if not isinstance(expected, dict) or not expected or any(
        not isinstance(k, str) or not isinstance(v, str) or not HEX.fullmatch(v)
        for k, v in expected.items()
    ):
        fail("MANIFEST_INVALID")
    actual = collect(release)
    if expected != actual:
        fail("HASH_MISMATCH")
    check_static_contract(release, actual)
    if (stored.get("publication_authorized") is not False or
            stored.get("manifest_version") != "dp481-v1"):
        fail("MANIFEST_INVALID")
    for key, item in (("projection_sha256", "projection/index.json"),
                      ("index_sha256", "static/search-index.v1.json")):
        if stored.get(key) != expected.get(item):
            fail("HASH_MISMATCH")
    generation = {k: v for k, v in expected.items() if k.startswith(("static/", "projection/"))}
    code = {k: v for k, v in expected.items() if k.startswith("code/")}
    if (stored.get("generation_sha256") != digest(canonical(generation)) or
            stored.get("code_sha256") != digest(canonical(code)) or
            stored.get("schema_sha256") != expected.get("code/schema.v1.sql") or
            not GIT.fullmatch(str(stored.get("source_git_commit", "")))):
        fail("MANIFEST_INVALID")
    return stored


def stage(root: Path, source: Path, static: Path, projection: Path, *,
          git_sha: str, rights_epoch_ref: str) -> dict:
    """Stage an immutable snapshot."""
    if not GIT.fullmatch(git_sha) or not rights_epoch_ref or len(rights_epoch_ref) > 256:
        fail("SOURCE_AUTHORITY_INVALID")
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    if root.stat().st_mode & 0o077:
        fail("ROOT_PERMISSIONS")
    releases = root / "releases"
    releases.mkdir(exist_ok=True, mode=0o700)
    for directory in (source / "poc", static, projection):
        safe_files(directory)
    schema_source = source / "db" / "schema.v1.sql"
    if schema_source.is_symlink() or not schema_source.is_file():
        fail("SCHEMA_MISSING")
    with tempfile.TemporaryDirectory(prefix=".dp481-stage-", dir=root) as temp:
        candidate = Path(temp) / "release"
        (candidate / "code").mkdir(parents=True)
        shutil.copytree(source / "poc", candidate / "code" / "poc",
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
                        symlinks=True)
        shutil.copy2(schema_source, candidate / "code" / "schema.v1.sql",
                     follow_symlinks=False)
        shutil.copytree(static, candidate / "static", symlinks=True)
        shutil.copytree(projection, candidate / "projection", symlinks=True)
        assets = collect(candidate)
        check_static_contract(candidate, assets)
        try:
            data = json.loads((candidate / "projection" / "index.json").read_bytes())
            schema = data["schema_version"]
        except (OSError, KeyError, ValueError, TypeError, UnicodeError):
            fail("PROJECTION_INVALID")
        if not isinstance(schema, str) or not schema:
            fail("PROJECTION_INVALID")
        from dichiarazioni_pubbliche.public_schema import (
            PublicSchemaValidationError, validate_public_bundle,
        )
        try:
            validate_public_bundle(data)
        except PublicSchemaValidationError:
            fail("PROJECTION_INVALID")
        from dichiarazioni_pubbliche.public_api import dispatch
        wire = dispatch("GET", "/api/v1/index.json",
                        projection_path=candidate / "projection" / "index.json")
        if wire.status != 200:
            fail("PROJECTION_INVALID")
        if "static/search-index.v1.json" not in assets:
            fail("INDEX_MISSING")
        generation = {k: v for k, v in assets.items() if k.startswith(("static/", "projection/"))}
        code = {k: v for k, v in assets.items() if k.startswith("code/")}
        material = {
            "manifest_version": "dp481-v1", "source_git_commit": git_sha,
            "schema_version": schema, "rights_epoch_ref": rights_epoch_ref,
            "schema_sha256": assets["code/schema.v1.sql"],
            "projection_sha256": assets["projection/index.json"],
            "index_sha256": assets["static/search-index.v1.json"],
            "generation_sha256": digest(canonical(generation)),
            "code_sha256": digest(canonical(code)), "assets": assets,
            "api_wire_sha256": digest(wire.body),
            "publication_authorized": False,
        }
        ident = digest(canonical(material))
        manifest = {**material, "release_id": ident}
        (candidate / MANIFEST).write_bytes(canonical(manifest))
        destination = releases / ident
        if destination.exists() or destination.is_symlink():
            validated(root, ident)
            return manifest
        os.rename(candidate, destination)
        for item in sorted(destination.rglob("*"), reverse=True):
            item.chmod(0o555 if item.is_dir() else 0o444)
        destination.chmod(0o555)
    return manifest


def activate(root: Path, release_id: str, *, expected: str | None) -> dict:
    """Compare-and-swap the current symlink under an exclusive host lock."""
    root.mkdir(parents=True, exist_ok=True)
    if root.stat().st_mode & 0o077:
        fail("ROOT_PERMISSIONS")
    with (root / ".activation.lock").open("a+b") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        before = pointer(root)
        if before != expected:
            fail("POINTER_MISMATCH")
        manifest = validated(root, release_id)
        if before != release_id:
            temp = root / (".next-" + str(os.getpid()))
            try:
                temp.symlink_to("releases/" + release_id, target_is_directory=True)
                os.replace(temp, root / "current")
                directory_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
            finally:
                if temp.is_symlink():
                    temp.unlink()
        return {"before": before, "current": pointer(root), "manifest_sha256":
                file_hash(root / "releases" / release_id / MANIFEST),
                "publication_authorized": manifest["publication_authorized"]}


def _http(origin: str, path: str, *, expected_hash: str | None = None) -> bytes:
    address = urlsplit(origin)
    if address.scheme != "http" or address.hostname not in ("127.0.0.1", "localhost"):
        fail("ORIGIN_NOT_LOOPBACK")
    if address.path not in ("", "/") or address.query or address.fragment or address.username:
        fail("ORIGIN_INVALID")
    request = Request(origin.rstrip("/") + quote(path, safe="/"),
                      headers={"Accept-Encoding": "identity", "Cache-Control": "no-cache"})
    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None
    try:
        with build_opener(NoRedirect).open(request, timeout=10) as result:
            if result.status != 200 or result.headers.get("Content-Encoding", "identity") != "identity":
                fail("HTTP_MISMATCH")
            sha = hashlib.sha256()
            size = 0
            chunks = []
            while (chunk := result.read(1024 * 1024)):
                sha.update(chunk)
                size += len(chunk)
                if size > 100 * 1024 * 1024:
                    fail("HTTP_OVERSIZED")
                if expected_hash is None:
                    chunks.append(chunk)
            if expected_hash is not None:
                if not hmac.compare_digest(sha.hexdigest(), expected_hash):
                    fail("HTTP_MISMATCH")
                return b""
            return b"".join(chunks)
    except HTTPError as exc:
        exc.close()
        raise ValueError("DP481_HTTP_MISMATCH") from exc
    except (URLError, OSError) as exc:
        raise ValueError("DP481_HTTP_MISMATCH") from exc


def rehearse(source: Path, static: Path, projection: Path, *, git_sha: str,
             rights_epoch_ref: str) -> dict:
    """Rehearse DRAFT on private loopback."""
    from dichiarazioni_pubbliche.public_api import build_server
    safe_files(static)

    def start(root: Path):
        server = build_server(root / "current/projection/index.json",
                              static_dir=root / "current/static")
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server, thread

    def stop(server, thread):
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()

    with tempfile.TemporaryDirectory(prefix="dp481-minipc-rehearsal-") as temp:
        root = Path(temp) / "authority"
        candidate_static = Path(temp) / "candidate-static"
        shutil.copytree(static, candidate_static)
        marker = candidate_static / "dp481-rehearsal-withdrawn.txt"
        if marker.exists():
            fail("REHEARSAL_COLLISION")
        marker.write_bytes(b"DP481 temporary withdrawn test only")
        prior = stage(root, source, candidate_static, projection,
                      git_sha=git_sha, rights_epoch_ref=rights_epoch_ref)
        activate(root, prior["release_id"], expected=None)
        old, old_thread = start(root)
        old_origin = f"http://127.0.0.1:{old.server_port}"
        try:
            verify(root, origin=old_origin)
            old_sha = digest(_http(old_origin, "/dp481-rehearsal-withdrawn.txt"))
            if old_sha != digest(marker.read_bytes()):
                fail("REHEARSAL_BASELINE")
            marker.unlink()
            safe = stage(root, source, candidate_static, projection,
                         git_sha=git_sha, rights_epoch_ref=rights_epoch_ref)
            try:
                activate(root, safe["release_id"], expected="0" * 64)
            except ValueError as exc:
                if "POINTER_MISMATCH" not in str(exc):
                    raise
            else:
                fail("REHEARSAL_STALE_POINTER_ACCEPTED")
            activate(root, safe["release_id"], expected=prior["release_id"])
            try:
                _http(old_origin, "/dp481-rehearsal-withdrawn.txt")
            except ValueError as exc:
                if "HTTP_MISMATCH" not in str(exc):
                    raise
            else:
                fail("REHEARSAL_STALE_200")
        finally:
            stop(old, old_thread)
        fresh, fresh_thread = start(root)
        try:
            proof = verify(root, origin=f"http://127.0.0.1:{fresh.server_port}")
            try:
                _http(f"http://127.0.0.1:{fresh.server_port}", "/dp481-rehearsal-withdrawn.txt")
            except ValueError as exc:
                if "HTTP_MISMATCH" not in str(exc):
                    raise
            else:
                fail("REHEARSAL_WITHDRAWN_200")
        finally:
            stop(fresh, fresh_thread)
        activate(root, prior["release_id"], expected=safe["release_id"])
        activate(root, safe["release_id"], expected=prior["release_id"])
        rollback, rollback_thread = start(root)
        try:
            verified = verify(root, origin=f"http://127.0.0.1:{rollback.server_port}")
        finally:
            stop(rollback, rollback_thread)
        return {"status": "PASS_PRIVATE_REHEARSAL", "initial_release_id": prior["release_id"],
                "safe_release_id": safe["release_id"], "rollback_release_id": verified["release_id"],
                "live_public_service_changed": False, "stale_pointer_rejected": True,
                "withdrawn_old_listener_http": 404,
                "safe_origin_verified": proof["http_origin_verified"],
                "safe_manifest_sha256": verified["manifest_sha256"],
                "publication_authorized": False}


def verify(root: Path, *, origin: str | None = None) -> dict:
    """Fail on changed pointer, missing/tampered bytes or mismatched HTTP origin."""
    ident = pointer(root)
    if ident is None:
        fail("POINTER_INVALID")
    manifest = validated(root, ident)
    if origin:
        for asset, sha in manifest["assets"].items():
            if asset.startswith("static/"):
                _http(origin, "/" + asset[7:], expected_hash=sha)
        try:
            api_body = _http(origin, "/api/v1/index.json")
            actual = json.loads(api_body)
            expected = json.loads((root / "current" / "projection" / "index.json").read_bytes())
            health = json.loads(_http(origin, "/api/v1/health"))
            from dichiarazioni_pubbliche.public_api import build_index, index_full_bundle_payload
            expected_wire = index_full_bundle_payload(build_index(expected))
        except (ValueError, KeyError, UnicodeError, TypeError) as exc:
            raise ValueError("DP481_HTTP_MISMATCH") from exc
        if (digest(api_body) != manifest["api_wire_sha256"] or
                actual != expected_wire or health.get("data", {}).get("dataset_fingerprint") !=
                expected.get("dataset_sha256")):
            fail("HTTP_MISMATCH")
        nt = manifest["assets"].get("projection/index.nt")
        if nt:
            _http(origin, "/index.nt", expected_hash=nt)
    if pointer(root) != ident:
        fail("POINTER_MISMATCH")
    validated(root, ident)
    return {"status": "PASS", "release_id": ident,
            "pointer_target": "releases/" + ident,
            "source_git_commit": manifest["source_git_commit"],
            "schema_version": manifest["schema_version"],
            "schema_sha256": manifest["schema_sha256"],
            "rights_epoch_ref": manifest["rights_epoch_ref"],
            "code_sha256": manifest["code_sha256"],
            "projection_sha256": manifest["projection_sha256"],
            "index_sha256": manifest["index_sha256"],
            "api_wire_sha256": manifest["api_wire_sha256"],
            "generation_sha256": manifest["generation_sha256"],
            "assets": manifest["assets"],
            "manifest_sha256": file_hash(root / "releases" / ident / MANIFEST),
            "http_origin_verified": bool(origin), "publication_authorized": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path)
    commands = parser.add_subparsers(dest="command", required=True)
    staged = commands.add_parser("stage")
    staged.add_argument("--source", required=True, type=Path)
    staged.add_argument("--static", required=True, type=Path)
    staged.add_argument("--projection", required=True, type=Path)
    staged.add_argument("--git-sha", required=True)
    staged.add_argument("--rights-epoch-ref", required=True)
    activated = commands.add_parser("activate")
    activated.add_argument("--release-id", required=True)
    activated.add_argument("--expect-current", default="none")
    checked = commands.add_parser("verify")
    checked.add_argument("--origin", help="Live loopback same-origin HTTP URL")
    rehearsal = commands.add_parser("rehearse")
    rehearsal.add_argument("--source", required=True, type=Path)
    rehearsal.add_argument("--static", required=True, type=Path)
    rehearsal.add_argument("--projection", required=True, type=Path)
    rehearsal.add_argument("--git-sha", required=True)
    rehearsal.add_argument("--rights-epoch-ref", required=True)
    args = parser.parse_args()
    try:
        if args.command != "rehearse" and args.root is None:
            fail("ROOT_REQUIRED")
        if args.command == "stage":
            result = stage(args.root, args.source, args.static, args.projection,
                           git_sha=args.git_sha, rights_epoch_ref=args.rights_epoch_ref)
        elif args.command == "activate":
            expected = None if args.expect_current == "none" else args.expect_current
            result = activate(args.root, args.release_id, expected=expected)
        elif args.command == "rehearse":
            result = rehearse(args.source, args.static, args.projection,
                              git_sha=args.git_sha, rights_epoch_ref=args.rights_epoch_ref)
        else:
            result = verify(args.root, origin=args.origin)
        print(json.dumps(result, sort_keys=True))
        return 0
    except (ValueError, OSError) as exc:
        print(json.dumps({"status": "FAIL", "reason": str(exc)}, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
