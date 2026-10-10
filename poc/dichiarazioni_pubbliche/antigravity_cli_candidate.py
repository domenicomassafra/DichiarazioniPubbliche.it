"""Direct, pinned Antigravity CLI quota transport for PRIVATE Passage candidates.

Unlike the OmniRoute auto-routing gateway this launches the native `agy` binary
with an exact observed model ID, without account-rotation or fallback flags.
This is NOT Gemini Developer API; quotas belong to the CLI/Google plan.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from dichiarazioni_pubbliche.candidate_extraction import (
    CandidateExtractionError, OmniRouteCandidateExtractionClient, ProviderExtractionRequest,
)


_CLI_ID = re.compile(r"gemini-[0-9]+\.[0-9]+-(?:flash|pro)-(?:low|medium|high)\Z")
_MAX_STDOUT = 262_144
_MAX_PROMPT_BYTES = 48_000


class AntigravityCliCandidateExtractionClient(OmniRouteCandidateExtractionClient):
    """No hidden credential or status requests; commands run in an empty workdir."""

    provider_id = "antigravity-cli-quota"

    def __init__(
        self, *, model_id: str, account_scope_sha256: str,
        quota_remaining_requests: int, quota_remaining_tokens: int,
        quota_receipt_id: str,
        quota_observed_at: str,
        cli_path: str | None = None,
        timeout_seconds: int = 40,
    ) -> None:
        if not isinstance(model_id, str) or not _CLI_ID.fullmatch(model_id):
            raise CandidateExtractionError("ANTIGRAVITY_CLI_MODEL_ID_INVALID")
        if not isinstance(account_scope_sha256, str) or not re.fullmatch(r"[a-f0-9]{64}", account_scope_sha256):
            raise CandidateExtractionError("ANTIGRAVITY_CLI_ACCOUNT_SCOPE_INVALID")
        if (type(quota_remaining_requests) is not int or quota_remaining_requests < 1
                or type(quota_remaining_tokens) is not int or quota_remaining_tokens < 40_000):
            raise CandidateExtractionError("ANTIGRAVITY_CLI_QUOTA_INSUFFICIENT")
        if not isinstance(quota_receipt_id, str) or not re.fullmatch(r"provider-plan:[a-f0-9]{64}", quota_receipt_id):
            raise CandidateExtractionError("ANTIGRAVITY_CLI_QUOTA_RECEIPT_INVALID")
        try:
            quota_time = datetime.fromisoformat(quota_observed_at)
            now = datetime.now(timezone.utc)
            if (quota_time.utcoffset() is None or quota_time > now
                    or now - quota_time > timedelta(minutes=15)):
                raise ValueError("stale")
        except (TypeError, ValueError) as exc:
            raise CandidateExtractionError("ANTIGRAVITY_CLI_QUOTA_SNAPSHOT_STALE") from exc
        if type(timeout_seconds) is not int or not 10 <= timeout_seconds <= 90:
            raise CandidateExtractionError("ANTIGRAVITY_CLI_TIMEOUT_INVALID")
        self.executable = cli_path or shutil.which("agy")
        if not self.executable or not Path(self.executable).is_absolute():
            raise CandidateExtractionError("ANTIGRAVITY_CLI_EXECUTABLE_MISSING")
        self.account_scope_sha256 = account_scope_sha256
        self.quota_receipt_id = quota_receipt_id
        self.quota_observed_at = quota_time
        self.quota_requests = quota_remaining_requests
        self.quota_tokens = quota_remaining_tokens
        self.timeout_seconds = timeout_seconds
        super().__init__(api_key="", model_id=model_id,
                         cost_rate_usd_per_1k_total_tokens=Decimal("0"))
        self.provider_version = "antigravity-cli-quota-v1:pinned-model:plan-sandbox"

    def cost_upper_bound_usd(self, request: ProviderExtractionRequest) -> Decimal:
        # Zero external API billing is admitted only after the operator
        # verified quota+NEVER overage in the SHA-pinned capability catalog.
        if self._quota_stale():
            raise CandidateExtractionError("ANTIGRAVITY_CLI_QUOTA_SNAPSHOT_STALE")
        if self.quota_requests <= 0 or self.quota_tokens < self._estimated_tokens(request) + 32_000:
            raise CandidateExtractionError("ANTIGRAVITY_CLI_QUOTA_INSUFFICIENT")
        return Decimal("0")

    def _quota_stale(self) -> bool:
        now = datetime.now(timezone.utc)
        return now < self.quota_observed_at or now - self.quota_observed_at > timedelta(minutes=15)

    @staticmethod
    def _safe_env() -> dict[str, str]:
        # Preserve only paths required to use the already-authenticated native
        # CLI; never pass OMNIROUTE_API_KEY or unrelated provider credentials.
        keys = ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR", "XDG_CONFIG_HOME", "XDG_DATA_HOME")
        return {key: os.environ[key] for key in keys if key in os.environ}

    def _run(self, argv: list[str], *, cwd: str, timeout: int,
             stdin_payload: str | None = None) -> str:
        try:
            options: dict[str, Any] = {
                "cwd": cwd, "env": self._safe_env(),
                "capture_output": True, "text": True,
                "timeout": timeout, "check": False,
            }
            if stdin_payload is None:
                options["stdin"] = subprocess.DEVNULL
            else:
                # Confidential Passage text must never appear in process argv.
                options["input"] = stdin_payload
            result = subprocess.run(
                [self.executable, *argv], **options,
            )
        except subprocess.TimeoutExpired as exc:
            raise CandidateExtractionError("ANTIGRAVITY_CLI_TIMEOUT") from exc
        except OSError as exc:
            raise CandidateExtractionError("ANTIGRAVITY_CLI_UNAVAILABLE") from exc
        if result.returncode != 0:
            # Do not leak stderr: it may contain paths, source text or auth data.
            raise CandidateExtractionError("ANTIGRAVITY_CLI_NONZERO_EXIT")
        if len(result.stdout.encode("utf-8")) > _MAX_STDOUT:
            raise CandidateExtractionError("ANTIGRAVITY_CLI_RESPONSE_TOO_LARGE")
        return result.stdout

    def _post(self, prompt: str) -> tuple[dict[str, Any], float]:
        if self._quota_stale():
            raise CandidateExtractionError("ANTIGRAVITY_CLI_QUOTA_SNAPSHOT_STALE")
        if not isinstance(prompt, str) or not 0 < len(prompt.encode("utf-8")) <= _MAX_PROMPT_BYTES:
            raise CandidateExtractionError("ANTIGRAVITY_CLI_PROMPT_INVALID")
        conservative = len(prompt.encode("utf-8")) + 32_000
        if self.quota_requests <= 0 or self.quota_tokens < conservative:
            raise CandidateExtractionError("ANTIGRAVITY_CLI_QUOTA_INSUFFICIENT")
        started = time.monotonic()
        with tempfile.TemporaryDirectory(prefix="dp-agy-private-") as tmp:
            catalog = self._run(["models"], cwd=tmp, timeout=12)
            found = {line.split("\t", 1)[0] for line in catalog.splitlines() if "\t" in line}
            if self.model_id not in found:
                raise CandidateExtractionError("ANTIGRAVITY_CLI_MODEL_NOT_ADVERTISED")
            self.quota_requests -= 1  # Count attempted usage even on API failure.
            try:
                output = self._run([
                    "--model", self.model_id,
                    "--mode", "plan", "--sandbox", "--disable-slash-commands",
                    "--input-format", "stream-json",
                    "--output-format", "stream-json",
                    "--print-timeout", f"{self.timeout_seconds}s",
                    "--log-file", str(Path(tmp) / "agy.log"),
                ], cwd=tmp, timeout=self.timeout_seconds + 6,
                    stdin_payload=json.dumps({
                        "event": "user", "message": {"content": prompt},
                    }, ensure_ascii=False) + "\n")
            except CandidateExtractionError:
                # Real quota burn is unknown after timeout/provider failure.
                # A retry requires a newly approved quota snapshot.
                self.quota_tokens = 0
                raise
        try:
            events = [json.loads(line) for line in output.splitlines() if line.strip()]
        except (UnicodeError, ValueError) as exc:
            self.quota_tokens = 0
            raise CandidateExtractionError("ANTIGRAVITY_CLI_RESPONSE_NOT_JSON") from exc
        results = [event["result"] for event in events
                   if isinstance(event, dict) and event.get("event") == "result"
                   and isinstance(event.get("result"), dict)]
        if len(results) != 1:
            self.quota_tokens = 0
            raise CandidateExtractionError("ANTIGRAVITY_CLI_RESULT_EVENT_INVALID")
        data = results[0]
        if (not isinstance(data, dict) or data.get("status") != "SUCCESS"
                or type(data.get("num_turns")) is not int or data["num_turns"] != 1):
            self.quota_tokens = 0
            raise CandidateExtractionError("ANTIGRAVITY_CLI_RESPONSE_NOT_SUCCESS")
        response = data.get("response")
        usage = data.get("usage")
        if not isinstance(response, str) or not response.strip() or len(response.encode("utf-8")) > 120_000:
            self.quota_tokens = 0
            raise CandidateExtractionError("ANTIGRAVITY_CLI_RESPONSE_TEXT_INVALID")
        if not isinstance(usage, dict) or type(usage.get("total_tokens")) is not int or usage["total_tokens"] < 0:
            self.quota_tokens = 0
            raise CandidateExtractionError("ANTIGRAVITY_CLI_USAGE_MISSING")
        self.quota_tokens -= usage["total_tokens"]
        if self.quota_tokens < 0:
            raise CandidateExtractionError("ANTIGRAVITY_CLI_QUOTA_OVERRUN")
        # The native CLI output does not report a signed served-model ID.
        # A changed model/served identity MUST NOT be silently accepted.
        reported = data.get("model") or data.get("served_model")
        if reported is not None and reported != self.model_id:
            self.quota_tokens = 0
            raise CandidateExtractionError("ANTIGRAVITY_CLI_SERVED_MODEL_DRIFT")
        return ({
            "id": "agy:" + hashlib.sha256(
                (self.model_id + prompt + response).encode("utf-8")
            ).hexdigest(),
            "choices": [{"message": {"content": response}}],
            "usage": {"total_tokens": usage["total_tokens"],
                      "input_tokens": usage.get("input_tokens"),
                      "output_tokens": usage.get("output_tokens")},
        }, time.monotonic() - started)

    def extract(self, request: ProviderExtractionRequest):
        result = super().extract(request)
        return type(result)(
            payload=result.payload, request_id=result.request_id,
            latency_seconds=result.latency_seconds, usage=result.usage,
            cost_usd=result.cost_usd,
            receipt={**result.receipt,
                     "quota_receipt_id": self.quota_receipt_id,
                     "account_scope_sha256": self.account_scope_sha256,
                     "requested_model_id": self.model_id,
                     "served_model_identity": "CLI_DOES_NOT_REPORT_SIGNED_SERVED_MODEL",
                     "billing_basis": "ANTIGRAVITY_CLI_QUOTA_OVERAGE_DISABLED",
                     "remaining_requests": self.quota_requests,
                     "remaining_tokens": self.quota_tokens,
                     "private_review_required": True},
        )
