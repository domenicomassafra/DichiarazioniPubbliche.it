"""Opt-in, private single-file HTML snapshot via the unmodified Monolith CLI.

Monolith receives only an already approved HTML body on stdin. Excluding all
external asset types and whitelisting an unreachable domain prevents a second
network traversal, including resource redirects. This is deliberately a
document-only fallback; media archiving is a separate rights decision.
"""

from __future__ import annotations

import hashlib
import os
import re
import resource
import stat
import subprocess
import tempfile
from pathlib import Path

from dichiarazioni_pubbliche.capture_pipeline import (
    ArchiveResult, CapturePipelineError, _validate_capture_target,
)
from dichiarazioni_pubbliche.corpus_repository import ContentCaptureRecord
from dichiarazioni_pubbliche.private_capture_rights import SourceFamilyUseGuard


MONOLITH_VERSION = "2.11.6"
MONOLITH_RELEASE_COMMIT = "e7cc6c8acd5ebf5191379e7ad28a7498c5287148"
MONOLITH_LINUX_X86_64_SHA256 = "680f11831e5e0de4be6a17cbb1ce2542b8536bc50f7dd83a12cfd2a4e63c25c7"
MONOLITH_ADAPTER_VERSION = "monolith-2.11.6-private-stdin-v1"
MAX_MONOLITH_INPUT_BYTES = 2 * 1024 * 1024
MAX_MONOLITH_OUTPUT_BYTES = 4 * 1024 * 1024
_SHA = re.compile(r"^[a-f0-9]{64}$")


def _digest_file(path: Path, *, limit: int) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            size += len(chunk)
            if size > limit:
                raise CapturePipelineError("MONOLITH_INPUT_TOO_LARGE")
            digest.update(chunk)
    return digest.hexdigest(), size


def _limit_output(limit: int) -> None:
    resource.setrlimit(resource.RLIMIT_FSIZE, (limit, limit))


class MonolithArchiveAdapter:
    """Requires an explicit current source-use guard and pinned executable bytes."""

    provider = "monolith-private-html"
    synchronous_private_snapshot = True

    def __init__(
        self, *, binary_path: Path, binary_sha256: str, private_root: Path,
        source_use_guard: SourceFamilyUseGuard,
        max_output_bytes: int = MAX_MONOLITH_OUTPUT_BYTES,
        timeout_seconds: float = 10,
    ) -> None:
        if not isinstance(binary_sha256, str) or not _SHA.fullmatch(binary_sha256):
            raise ValueError("MONOLITH_BINARY_SHA256_INVALID")
        if not (type(max_output_bytes) is int and 1 <= max_output_bytes <= MAX_MONOLITH_OUTPUT_BYTES):
            raise ValueError("MONOLITH_OUTPUT_LIMIT_INVALID")
        if (isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float))
                or not 0 < timeout_seconds <= 30):
            raise ValueError("MONOLITH_TIMEOUT_INVALID")
        if source_use_guard is None:
            raise ValueError("MONOLITH_SOURCE_USE_GUARD_REQUIRED")
        self.binary_path = Path(binary_path).expanduser()
        self.binary_sha256 = binary_sha256
        self.private_root = Path(private_root).expanduser().resolve()
        self.source_use_guard = source_use_guard
        self.max_output_bytes = max_output_bytes
        self.timeout_seconds = timeout_seconds

    @staticmethod
    def _failure(code: str) -> ArchiveResult:
        return ArchiveResult("FAILED", MonolithArchiveAdapter.provider, {
            "error_category": code, "adapter_version": MONOLITH_ADAPTER_VERSION,
        })

    def _binary_valid(self) -> bool:
        path = self.binary_path
        if not path.is_absolute() or path.is_symlink() or not path.is_file():
            return False
        if not os.access(path, os.X_OK):
            return False
        try:
            if not stat.S_ISREG(path.stat().st_mode) or path.stat().st_size > 50_000_000:
                return False
            observed, _ = _digest_file(path, limit=50_000_000)
        except (OSError, CapturePipelineError):
            return False
        return observed == self.binary_sha256

    def archive(self, *, capture: ContentCaptureRecord, body_path: Path | None) -> ArchiveResult:
        if (capture.status != "CAPTURED" or capture.hold_status != "NONE"
                or capture.media_type not in {"text/html", "application/xhtml+xml"}):
            return self._failure("MONOLITH_CAPTURE_INELIGIBLE")
        try:
            _validate_capture_target(capture.final_url, final=True)
            self.source_use_guard.bind_capture(
                content_id=capture.content_id, url=capture.final_url,
            )
            self.source_use_guard.bind_fetched(final_url=capture.final_url)
            self.source_use_guard.require(
                "ARCHIVE", content_sha256=capture.content_sha256,
                media_type=capture.media_type,
            )
        except CapturePipelineError:
            return self._failure("MONOLITH_CAPTURE_URL_INVALID")
        # SourceUseBlocked is intentionally propagated to the pipeline's
        # fail-closed receipt handler, with no private reason or URL exposed.
        if body_path is None or body_path.is_symlink() or not body_path.is_file():
            return self._failure("MONOLITH_BODY_MISSING")
        try:
            if not body_path.resolve().is_relative_to(self.private_root / "captures"):
                return self._failure("MONOLITH_BODY_OUTSIDE_PRIVATE_STORE")
            original_sha, size = _digest_file(body_path, limit=MAX_MONOLITH_INPUT_BYTES)
        except (OSError, CapturePipelineError):
            return self._failure("MONOLITH_BODY_INVALID_OR_TOO_LARGE")
        if original_sha != capture.content_sha256 or size == 0:
            return self._failure("MONOLITH_BODY_HASH_MISMATCH")
        if not self._binary_valid():
            return self._failure("MONOLITH_BINARY_INVALID")

        self.private_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            os.chmod(self.private_root, 0o700)
        except OSError:
            return self._failure("MONOLITH_PRIVATE_ROOT_UNAVAILABLE")
        with tempfile.TemporaryDirectory(prefix=".monolith-", dir=self.private_root) as work:
            work_path = Path(work)
            staged = work_path / "snapshot.html"
            flags = [
                str(self.binary_path), "-a", "-c", "-f", "-F", "-i", "-j", "-v",
                "-I", "-M", "-d", "no-assets.invalid", "-b", capture.final_url,
                "-o", "-", "-",
            ]
            env = {
                "PATH": "/usr/bin:/bin", "HOME": work,
                "TMPDIR": work, "HTTP_PROXY": "http://127.0.0.1:9",
                "HTTPS_PROXY": "http://127.0.0.1:9",
                "http_proxy": "http://127.0.0.1:9",
                "https_proxy": "http://127.0.0.1:9", "NO_PROXY": "",
            }
            try:
                # Check the pinned full donor binary, not a user-installed replacement.
                version = subprocess.run(
                    [str(self.binary_path), "-V"], cwd=work, env=env,
                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                    timeout=self.timeout_seconds, check=False,
                )
                if (version.returncode != 0 or
                        version.stdout.strip() != f"monolith {MONOLITH_VERSION}".encode()):
                    return self._failure("MONOLITH_VERSION_MISMATCH")
                with body_path.open("rb") as body, staged.open("wb") as output:
                    os.fchmod(output.fileno(), 0o600)
                    completed = subprocess.run(
                        flags, stdin=body, stdout=output, stderr=subprocess.DEVNULL,
                        cwd=work, env=env, timeout=self.timeout_seconds,
                        preexec_fn=lambda: _limit_output(self.max_output_bytes),
                        check=False,
                    )
            except subprocess.TimeoutExpired:
                return self._failure("MONOLITH_TIMEOUT")
            except OSError:
                return self._failure("MONOLITH_EXECUTION_UNAVAILABLE")
            if staged.stat().st_size >= self.max_output_bytes:
                return self._failure("MONOLITH_OUTPUT_TOO_LARGE")
            if completed.returncode != 0:
                return self._failure("MONOLITH_PROCESS_FAILED")
            content = staged.read_bytes()
            if not re.search(br"<\s*(?:!doctype\s+html|html)\b", content[:512], re.I):
                return self._failure("MONOLITH_OUTPUT_INVALID")
            # The rights record can be revoked while the subprocess runs.
            self.source_use_guard.require(
                "ARCHIVE", content_sha256=capture.content_sha256,
                media_type=capture.media_type,
            )
            digest = hashlib.sha256(content).hexdigest()
            ref = f"archives/{digest[:2]}/{digest}.html"
            target = self.private_root / ref
            target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            if target.is_symlink() or (target.exists() and not target.is_file()):
                return self._failure("MONOLITH_TARGET_INVALID")
            if target.exists():
                if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
                    return self._failure("MONOLITH_EXISTING_HASH_MISMATCH")
            else:
                os.replace(staged, target)
                os.chmod(target, 0o600)
            return ArchiveResult("SUCCEEDED", self.provider, {
                "snapshot_kind": "PRIVATE_HTML", "snapshot_ref": ref,
                "snapshot_sha256": digest, "snapshot_bytes": len(content),
                "source_capture_id": capture.id,
                "original_url_sha256": hashlib.sha256(capture.final_url.encode()).hexdigest(),
                "adapter_version": MONOLITH_ADAPTER_VERSION,
                "binary_sha256": self.binary_sha256,
                "external_assets": "EXCLUDED", "publication_state": "HOLD",
            })
