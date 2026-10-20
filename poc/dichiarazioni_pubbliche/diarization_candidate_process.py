"""#166: bounded exec-worker for explicitly approved anonymous diarization.

The server never executes injected inference callbacks or changes its RLIMITs.
Only named, importable functions with small JSON arguments cross this boundary;
the child normalizes raw engine objects before emitting bounded JSON.
"""
from __future__ import annotations

import functools
import importlib
import inspect
import json
import math
import os
import platform
import resource
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from dichiarazioni_pubbliche.diarization_benchmark import Turn

MAX_JOB_BYTES = 8192
MAX_RESULT_BYTES = 96 * 1024
MAX_WALL_MS = 180_000
MAX_ADDRESS_BYTES = 16 * 1024**3


class RunnerIsolationError(RuntimeError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _describe_runner(runner: object) -> tuple[str, str, dict]:
    kwargs = {}
    if isinstance(runner, functools.partial):
        if runner.args:
            raise RunnerIsolationError("ENGINE_RUNNER_NOT_IMPORTABLE")
        kwargs = runner.keywords or {}
        runner = runner.func
    if not inspect.isfunction(runner) or "<locals>" in runner.__qualname__:
        raise RunnerIsolationError("ENGINE_RUNNER_NOT_IMPORTABLE")
    module, name = runner.__module__, runner.__qualname__
    fixture = module == "tests.test_diarization_candidate_adapter" and name in {
        "fixture_runner", "hung_runner", "memory_hog_runner", "oversized_stdout_runner",
    }
    approved = module == "dichiarazioni_pubbliche.diarization_candidate_adapter" and name == "pyannote_local_runner"
    if not (fixture or approved):
        raise RunnerIsolationError("ENGINE_RUNNER_NOT_APPROVED")
    try:
        encoded = json.dumps(kwargs, allow_nan=False, separators=(",", ":")).encode()
        decoded = json.loads(encoded)
    except (TypeError, ValueError):
        raise RunnerIsolationError("ENGINE_RUNNER_ARGUMENTS_INVALID") from None
    if not isinstance(decoded, dict) or len(encoded) > 4096:
        raise RunnerIsolationError("ENGINE_RUNNER_ARGUMENTS_INVALID")
    return module, name, decoded


def _kill_group(proc: subprocess.Popen) -> None:
    # start_new_session=True gives this inference its own process group.
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    proc.wait()


def execute_candidate(
    runner: object, media: Path, model: Path, *, engine_id: str,
    input_sha256: str, duration_ms: int, wall_ms: int, address_bytes: int,
) -> tuple[tuple[Turn, ...], tuple[tuple[int, int], ...], int, int]:
    """Return only normalized anonymous turns or a stable HOLD error code."""
    if (type(wall_ms) is not int or not 0 < wall_ms <= MAX_WALL_MS
            or type(address_bytes) is not int or not 0 < address_bytes <= MAX_ADDRESS_BYTES
            or os.name != "posix"):
        raise RunnerIsolationError("ENGINE_BUDGET_OR_HOST_INVALID")
    if platform.system() != "Linux":
        # macOS rejects finite RLIMIT_AS, even in a subprocess. Do not run a
        # callback where the requested hard memory limit cannot be enforced.
        raise RunnerIsolationError("ENGINE_ADDRESS_SPACE_LIMIT_UNAVAILABLE")
    if not shutil.which("prlimit"):
        raise RunnerIsolationError("ENGINE_RLIMIT_LAUNCHER_MISSING")
    module, name, kwargs = _describe_runner(runner)
    fixture = module.startswith("tests.")
    command = [sys.executable, "-m", "dichiarazioni_pubbliche.diarization_candidate_process", "--worker"]
    # Real engines require a Linux namespace without network interfaces. CI's
    # synthetic runners never import or execute actual models/providers.
    if not fixture:
        if not shutil.which("bwrap") or Path("/var/run").resolve() != Path("/run"):
            raise RunnerIsolationError("ENGINE_NETNS_REQUIRED")
        command = [shutil.which("bwrap"), "--die-with-parent", "--unshare-net",
                   "--unshare-pid", "--unshare-ipc", "--ro-bind", "/", "/",
                   "--tmpfs", "/run", "--", *command]
    # util-linux prlimit applies resource ceilings *before* execing Python;
    # unlike preexec_fn, this avoids running Python after fork in a threaded
    # parent server. The launcher itself belongs to the bounded child group.
    command = [shutil.which("prlimit"), f"--as={address_bytes}",
               f"--cpu={max(1, math.ceil(wall_ms / 1000) + 1)}",
               "--core=0", f"--fsize={MAX_RESULT_BYTES + 1}", "--", *command]
    job = dict(module=module, name=name, kwargs=kwargs, media=str(media),
               model=str(model), engine_id=engine_id,
               input_sha256=input_sha256, duration_ms=duration_ms)
    data = json.dumps(job, allow_nan=False, separators=(",", ":")).encode()
    if len(data) > MAX_JOB_BYTES:
        raise RunnerIsolationError("ENGINE_REQUEST_TOO_LARGE")
    package_root = Path(__file__).resolve().parents[1]
    env = {key: os.environ[key] for key in ("PATH", "LANG", "TMPDIR", "VIRTUAL_ENV") if key in os.environ}
    env["PYTHONPATH"] = os.pathsep.join((str(package_root), str(package_root.parent)))
    env.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1",
               HF_HUB_DISABLE_TELEMETRY="1", PYANNOTE_METRICS_ENABLED="0",
               HF_DATASETS_OFFLINE="1", OMP_NUM_THREADS="2")
    started = time.monotonic_ns()
    with tempfile.TemporaryFile() as result_file:
        try:
            proc = subprocess.Popen(
                command, stdin=subprocess.PIPE, stdout=result_file,
                stderr=subprocess.DEVNULL, env=env, cwd=str(package_root.parent),
                close_fds=True, start_new_session=True,
            )
        except (OSError, ValueError, subprocess.SubprocessError):
            raise RunnerIsolationError("ENGINE_PROCESS_START_FAILED") from None
        try:
            proc.communicate(input=data, timeout=wall_ms / 1000)
        except subprocess.TimeoutExpired:
            _kill_group(proc)
            raise RunnerIsolationError("ENGINE_TIMEOUT") from None
        finally:
            # Kill any descendant still living in the inference process group.
            _kill_group(proc)
        elapsed_ms = max(0, (time.monotonic_ns() - started) // 1_000_000)
        if proc.returncode != 0 or result_file.tell() > MAX_RESULT_BYTES:
            raise RunnerIsolationError("ENGINE_FAILED_OR_LIMIT")
        result_file.seek(0)
        try:
            payload = json.loads(result_file.read(MAX_RESULT_BYTES + 1))
            if not isinstance(payload, dict) or payload.get("state") != "OK":
                raise ValueError("worker failed")
            raw_turns = payload["turns"]
            raw_overlaps = payload["overlaps"]
            peak = payload["peak_rss_bytes"]
            if (not isinstance(raw_turns, list) or len(raw_turns) > 512
                    or not isinstance(raw_overlaps, list) or len(raw_overlaps) > 512
                    or type(peak) is not int or peak < 0 or peak > address_bytes):
                raise ValueError("worker resource bounds")
            turns = tuple(Turn(*row) for row in raw_turns)
            overlaps = tuple(tuple(row) for row in raw_overlaps)
            if any(type(t.start_ms) is not int or type(t.end_ms) is not int
                   or not 0 <= t.start_ms < t.end_ms <= duration_ms
                   or t.input_sha256 != input_sha256 or not t.speaker_label.startswith("TURN_")
                   for t in turns):
                raise ValueError("worker turns invalid")
            if any(len(row) != 2 or any(type(x) is not int for x in row)
                   or not 0 <= row[0] < row[1] <= duration_ms for row in overlaps):
                raise ValueError("worker overlaps invalid")
        except (ValueError, TypeError, KeyError, IndexError, AttributeError):
            raise RunnerIsolationError("ENGINE_RESULT_INVALID") from None
        if elapsed_ms > wall_ms:
            raise RunnerIsolationError("ENGINE_TIMEOUT")
        return turns, overlaps, elapsed_ms, peak


def _worker() -> None:
    from dichiarazioni_pubbliche.diarization_candidate_adapter import normalize_anonymous_turns
    try:
        data = sys.stdin.buffer.read(MAX_JOB_BYTES + 1)
        if len(data) > MAX_JOB_BYTES:
            raise ValueError("job oversized")
        job = json.loads(data)
        module = importlib.import_module(job["module"])
        runner = getattr(module, job["name"])
        turns, overlaps = normalize_anonymous_turns(
            engine_id=job["engine_id"],
            raw_result=runner(Path(job["media"]), Path(job["model"]), **job["kwargs"]),
            input_sha256=job["input_sha256"], duration_ms=job["duration_ms"],
        )
        raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        peak = int(raw if sys.platform == "darwin" else raw * 1024)
        from dataclasses import asdict
        result = dict(state="OK", turns=[list(asdict(t).values()) for t in turns],
                      overlaps=overlaps, peak_rss_bytes=peak)
        encoded = json.dumps(result, separators=(",", ":")).encode()
        if len(encoded) > MAX_RESULT_BYTES:
            raise ValueError("worker result oversized")
        sys.stdout.buffer.write(encoded)
    except (Exception, KeyboardInterrupt, SystemExit):
        sys.exit(79)


if __name__ == "__main__" and sys.argv[1:] == ["--worker"]:
    _worker()
