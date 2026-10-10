#!/usr/bin/env python3
"""One synthetic real loopback-only Ollama canary: no production text or secrets."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))

from dichiarazioni_pubbliche.local_claim_ollama import (  # noqa: E402
    LocalOllamaClaimClient, _request,
)


def main() -> int:
    try:
        catalog = _request("/api/tags")
        matches = [model for model in catalog.get("models", [])
                   if isinstance(model, dict) and model.get("name") == "qwen3:4b"]
        if len(matches) != 1:
            raise ValueError("LOCAL_MODEL_NOT_FOUND")
        pin = matches[0].get("digest", "")
        result = LocalOllamaClaimClient(expected_model_digest=pin).probe()
        print(json.dumps({
            "provider": "ollama-local", "model": "qwen3:4b",
            "synthetic_canary": "PASS" if result.healthy else "BLOCKED",
            "reason": result.reason, "latency_seconds": round(result.latency_seconds, 2),
            "external_cost_usd": 0,
            "external_calls": 0, "publication_approved": False,
        }, sort_keys=True))
        return 0 if result.healthy else 1
    except (RuntimeError, ValueError, OSError) as exc:
        code = str(exc).splitlines()[0][:120]
        print(json.dumps({"synthetic_canary": "BLOCKED", "reason": code}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
