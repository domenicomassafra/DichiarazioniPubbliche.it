"""DP-240 #48: bounded, no-tools Pi CLI attestations; run from the Mac Studio.

Outputs are private experimental receipts, never publication authority.
Requires SSH access to the already-provisioned matebooklinux and Pi models.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess
import time

ROOT = Path(__file__).resolve().parent
MATERIAL = json.loads((ROOT / "material.json").read_text())
MODELS = {
    "sol": "codex/gpt-6.1-sol",
    "gemini": "antigravity/gemini-3.8-flash-tiered",
}


def invoke(model: str, prompt: str, output_name: str) -> dict:
    # No tools, no MCP, no session persistence, no instructions from remote cwd.
    # Public source snippets only. Exactly one run, no paid API fallback.
    cmd = (
        "pi -p --model " + shlex.quote(model)
        + " --thinking high --no-tools --no-mcp --no-session"
        + " --no-context-files --mode json " + shlex.quote(prompt)
    )
    started = datetime.now(timezone.utc).isoformat()
    before = time.perf_counter()
    result = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", "matebooklinux", cmd],
        capture_output=True, text=True, timeout=240, check=False,
    )
    elapsed = round(time.perf_counter() - before, 3)
    usage, messages, events, settled, errors = [], [], [], False, []
    for line in result.stdout.splitlines():
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        events.append(obj.get("type"))
        if obj.get("type") == "message_end":
            msg = obj.get("message", {})
            if msg.get("role") == "assistant":
                if msg.get("stopReason") == "error":
                    errors.append(str(msg.get("errorMessage") or msg.get("error") or "provider_error"))
                messages.extend(
                    p.get("text", "")
                    for p in msg.get("content", [])
                    if p.get("type") == "text"
                )
                usage.append({
                    "model": msg.get("model"), "provider": msg.get("provider"),
                    "usage": msg.get("usage"), "stopReason": msg.get("stopReason"),
                    "responseModel": msg.get("responseModel"),
                })
        if obj.get("type") == "agent_settled":
            settled = not obj.get("aborted", False)
    remote_metrics = re.search(
        r"REMOTE_PEAK_RSS_KB=(\d+) REMOTE_ELAPSED_S=([0-9.]+)", result.stderr
    )
    receipt = {
        "date_utc": started, "host": "matebooklinux",
        "model_requested": model,
        "command": "pi -p --model <model> --thinking high --no-tools --no-mcp --no-session --no-context-files --mode json",
        "prompt": prompt,
        "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
        "exit_code": result.returncode, "agent_settled": settled,
        "elapsed_ssh_seconds": elapsed,
        "remote_peak_rss_kb": int(remote_metrics.group(1)) if remote_metrics else None,
        "remote_elapsed_seconds": float(remote_metrics.group(2)) if remote_metrics else None,
        "usage_events": usage,
        "provider_errors": errors,
        "answer": "\n".join(messages),
        "stderr_tail": result.stderr[-600:],
        "event_kinds": sorted(set(events)),
        "scope": "private model observation only; no public attribution or publication",
    }
    path = ROOT / output_name
    path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({
        "file": str(path), "returncode": result.returncode,
        "settled": settled, "answer_characters": len(receipt["answer"]),
        "elapsed_seconds": elapsed, "model": model,
    }))
    return receipt


def reviewer(model: str, name: str) -> dict:
    prompt = (ROOT / "review-prompt.md").read_text() + "\n" + json.dumps(
        MATERIAL, ensure_ascii=False, indent=2
    )
    return invoke(model, prompt, f"review-{name}.json")


def blind_reviewer(model: str, name: str) -> dict:
    # Independent held-out attribution: neither expected labels nor other
    # reviewers' conclusions are supplied to the challenger.
    prompt = (ROOT / "review-prompt.md").read_text().replace(
        "I valori expected_speaker e expected_role sono ipotesi dell'operatore: "
        "giudicali indipendentemente dal contesto e dalle parole introduttive, "
        "non assumerli veri per definizione.",
        "Non ricevi un gold o etichette dell'operatore. Valuta in modo "
        "indipendente solo le prove testuali fornite.",
    )
    hidden = {
        **MATERIAL,
        "items": [
            {k: v for k, v in item.items() if not k.startswith("expected_")}
            for item in MATERIAL["items"]
        ],
    }
    prompt += "\n" + json.dumps(hidden, ensure_ascii=False, indent=2)
    return invoke(model, prompt, f"review-blind-{name}.json")


def benchmark(mode: str) -> dict:
    items = MATERIAL["items"]
    if mode == "single-meloni":
        selected = [items[0]]
    elif mode == "single-mattarella":
        selected = [items[1]]
    elif mode == "mixed":
        selected = items
    else:
        raise ValueError(mode)
    # Hold out expected speaker/role as evaluation gold.
    fields = ("id", "content_id", "url", "date", "context", "passage")
    sanitized = [{k: item[k] for k in fields} for item in selected]
    prompt = (
        "Esperimento DP-240 #48, record pubblico, analisi esclusivamente privata. "
        "Per OGNI item indica il parlante del SOLO passaggio virgolettato, il ruolo, "
        "la fonte originale e l'ID. Non confondere narratore, altra persona citata "
        "e parlante. Se l'attribuzione non e' sostenuta scrivi speaker=null e HELD. "
        "Rispondi SOLO con JSON object, campo items array: "
        "{id,content_id,speaker,role,attribution_status,source_url,reason}. "
        "Non attribuire un passaggio a un'altra fonte. Non inventare verifiche, "
        "costs, o authority. Input:\n"
        + json.dumps(sanitized, ensure_ascii=False, sort_keys=True)
    )
    return invoke(MODELS["gemini"], prompt, f"benchmark-{mode}.json")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("task", choices=(
        "review-sol", "review-gemini", "review-blind-sol", "review-blind-gemini",
        "single-meloni", "single-mattarella", "mixed",
    ))
    args = parser.parse_args()
    if args.task.startswith("review-blind-"):
        model_name = args.task.removeprefix("review-blind-")
        blind_reviewer(MODELS[model_name], model_name)
    elif args.task.startswith("review-"):
        model_name = args.task.removeprefix("review-")
        reviewer(MODELS[model_name], model_name)
    else:
        benchmark(args.task)
