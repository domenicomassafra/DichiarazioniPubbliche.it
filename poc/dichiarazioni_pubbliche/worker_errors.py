from __future__ import annotations


class BlockedJob(RuntimeError):
    pass


class DeferredJob(RuntimeError):
    def __init__(self, reason: str, delay_seconds: int) -> None:
        super().__init__(reason)
        self.delay_seconds = max(delay_seconds, 0)


class RetryableJob(RuntimeError):
    def __init__(self, reason: str, delay_seconds: int = 60) -> None:
        super().__init__(reason)
        self.delay_seconds = max(delay_seconds, 0)
