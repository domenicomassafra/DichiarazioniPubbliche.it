"""Cross-process, non-blocking admission for local Ollama and whisper.cpp CPU work."""

from __future__ import annotations

import fcntl
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


class LocalInferenceBusy(RuntimeError):
    """The operator-local inference budget is already in use."""


LOCK_PATH = Path.home() / ".local/state/dichiarazioni-pubbliche/local-inference.lock"


@contextmanager
def local_inference_slot() -> Iterator[None]:
    """Permit one bounded local CPU inference across separate worker processes.

    This does not control external Ollama clients, only the two DP adapters.
    Never queue/wait indefinitely while holding a queue job lease.
    """
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    handle = os.open(
        LOCK_PATH,
        os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise LocalInferenceBusy("LOCAL_INFERENCE_BUSY") from exc
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)
    finally:
        os.close(handle)
