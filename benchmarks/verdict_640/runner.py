#!/usr/bin/env python3
"""DP#640: auditable verdict benchmark; stdlib-only, independent of DP#638."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import datetime as dt
import html
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import shlex
import statistics
import subprocess
import sys
import time
import unicodedata
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


LABELS = ("vero", "falso", "parzialmente vero", "non verificabile", "opinione")
HERE = Path(__file__).resolve().parent
GATEWAY = "http://100.94.144.48:20128/v1/chat/completions"
MODEL = "opencode-go/deepseek-v4.1-flash"


def load_rows(path):
    rows = []
    seen = set()
    for number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict) or any(k not in row for k in ("id", "quote", "person", "date", "source_url", "label", "evidence")):
            raise ValueError(f"row {number}: missing required fields")
        if row["id"] in seen or row["label"] not in LABELS or len(row["evidence"]) < 2:
            raise ValueError(f"row {number}: duplicate id, invalid label, or fewer than two evidences")
        seen.add(row["id"])
        dt.date.fromisoformat(row["date"])
        for item in row["evidence"]:
            if not item.get("url", "").startswith("https://") or not item.get("note"):
                raise ValueError(f"row {number}: evidence URL/note missing")
        rows.append(row)
    if not rows:
        raise ValueError("empty corpus")
    return rows


def post_json(url, payload, headers=None, timeout=60):
    request = Request(url, data=json.dumps(payload, ensure_ascii=False).encode(), headers={"Content-Type": "application/json", **(headers or {})}, method="POST")
    with urlopen(request, timeout=timeout) as response:
        return json.load(response)


def input_payload(row):
    # Reference label and evidence notes are deliberately withheld from the model.
    return {"statement": row["quote"], "person": row["person"], "date": row["date"], "source_url": row["source_url"]}


def baseline(row, timeout):
    key = os.environ.get("OMNIROUTE_API_KEY")
    if not key:
        raise ValueError("OMNIROUTE_API_KEY missing (run with: secret env OMNIROUTE_API_KEY -- ...)")
    context = input_payload(row)
    prompt = (
        "Sei un verificatore di dichiarazioni pubbliche italiane. Dai una sola etichetta: "
        "vero, falso, parzialmente vero, non verificabile, opinione. "
        "Le opinioni soggettive non sono fatti; se i dati essenziali non sono disponibili, scegli non verificabile. "
        "Non inventare fonti; l'assenza di ricerca live limita la tua certezza. "
        "Rispondi esclusivamente con JSON: {\"label\":\"...\",\"evidence\":[\"...\"]}."
    )
    data = post_json(GATEWAY, {"model": MODEL, "messages": [{"role": "system", "content": prompt}, {"role": "user", "content": json.dumps(context, ensure_ascii=False)}], "temperature": 0}, {"Authorization": "Bearer " + key}, timeout)
    choice = data["choices"][0]["message"]["content"]
    if isinstance(choice, list):
        choice = "".join(x.get("text", "") for x in choice if isinstance(x, dict))
    match = re.search(r"\{[\s\S]*\}", choice or "")
    if not match:
        raise ValueError("model response did not contain a JSON object")
    return json.loads(match.group())


def verdict(row, mode, target, timeout):
    payload = input_payload(row)
    if mode == "baseline":
        return baseline(row, timeout)
    if mode == "endpoint":
        return post_json(target, payload, timeout=timeout)
    process = subprocess.run(shlex.split(target), input=json.dumps(payload, ensure_ascii=False), text=True, capture_output=True, timeout=timeout, check=False)
    if process.returncode:
        raise RuntimeError(f"adapter exited {process.returncode}: {process.stderr[:200]}")
    return json.loads(process.stdout)


def benchmark(rows, predict):
    cases = []
    for row in rows:
        start = time.perf_counter()
        result = None
        error = None
        try:
            result = predict(row)
            if not isinstance(result, dict) or result.get("label") not in LABELS or not isinstance(result.get("evidence"), list):
                raise ValueError("adapter must return {label: valid label, evidence: list, model_calls?: int}")
            calls = result.get("model_calls", 1)
            if type(calls) is not int or calls < 0:
                raise ValueError("model_calls must be a nonnegative integer")
        except (ValueError, RuntimeError, OSError, TimeoutError, KeyError, json.JSONDecodeError, HTTPError, URLError, subprocess.TimeoutExpired) as exc:
            error = f"{type(exc).__name__}: {exc}"
            calls = 1  # One attempted adapter invocation; internal calls unknown on failure.
        elapsed = time.perf_counter() - start
        cases.append({"id": row["id"], "expected": row["label"], "actual": result["label"] if error is None else "ERRORE", "seconds": round(elapsed, 4), "model_calls": calls, "error": error, "evidence": result.get("evidence", []) if error is None else []})
    return cases


def report(cases):
    total = len(cases)
    correct = sum(x["actual"] == x["expected"] for x in cases)
    print(f"Casi: {total} | corretti: {correct} | accuracy: {correct / total:.1%}")
    for label in LABELS:
        group = [x for x in cases if x["expected"] == label]
        n = sum(x["actual"] == label for x in group)
        print(f"  {label:20} {n:3}/{len(group):3} = {n / len(group):.1%}" if group else f"  {label:20} 0/0 = n/d")
    print("Confusione (righe = atteso; colonne = predetto)")
    columns = (*LABELS, "ERRORE")
    print("atteso\\predetto\t" + "\t".join(columns))
    for label in LABELS:
        print(label + "\t" + "\t".join(str(sum(x["expected"] == label and x["actual"] == predicted for x in cases)) for predicted in columns))
    print("Errori:")
    for x in cases:
        if x["expected"] != x["actual"]:
            print(f"  {x['id']}: atteso={x['expected']}, ottenuto={x['actual']}" + (f", motivo={x['error']}" if x['error'] else ""))
    durations = [x["seconds"] for x in cases]
    print(f"Tempi: mediana={statistics.median(durations):.3f}s; peggiore={max(durations):.3f}s")
    print(f"Chiamate modello: totale={sum(x['model_calls'] for x in cases)}; media={statistics.mean(x['model_calls'] for x in cases):.2f} per dichiarazione")
    print("Chiamate per dichiarazione: " + ", ".join(f"{x['id']}={x['model_calls']}" for x in cases))
    return {"total": total, "correct": correct, "accuracy": correct / total, "per_label": {label: {"correct": sum(x["actual"] == label for x in cases if x["expected"] == label), "total": sum(x["expected"] == label for x in cases)} for label in LABELS}, "median_seconds": statistics.median(durations), "worst_seconds": max(durations), "model_calls_total": sum(x["model_calls"] for x in cases), "cases": cases}


class PageText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip = max(0, self.skip - 1)

    def handle_data(self, data):
        if not self.skip:
            self.text.append(data)


def normalize(text):
    return " ".join(unicodedata.normalize("NFC", html.unescape(text)).split()).replace("\u00a0", " ")


def check_sources(rows, timeout):
    urls = {row["source_url"] for row in rows}
    urls.update(item["url"] for row in rows for item in row["evidence"])
    texts = {}
    errors = []
    def fetch(url):
        if not url.startswith("https://"):
            return url, None, f"URL non HTTPS: {url}"
        try:
            req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urlopen(req, timeout=timeout) as response:
                if response.status != 200:
                    raise ValueError(f"HTTP {response.status}")
                data = response.read(2_000_000)
                if "text/html" in response.headers.get("Content-Type", ""):
                    parser = PageText()
                    parser.feed(data.decode("utf-8", "replace"))
                    return url, normalize(" ".join(parser.text)), None
                return url, None, None
        except Exception as exc:
            return url, None, f"{url}: {type(exc).__name__}: {exc}"
    with ThreadPoolExecutor(max_workers=6) as pool:
        for url, page, error in pool.map(fetch, sorted(urls)):
            if page is not None:
                texts[url] = page
            if error:
                errors.append(error)
    for row in rows:
        text = texts.get(row["source_url"])
        if text is None:
            errors.append(f"{row['id']}: impossibile confrontare citazione HTML con la fonte")
        elif normalize(row["quote"]) not in text:
            errors.append(f"{row['id']}: citazione non presente letteralmente nella fonte")
    print(f"Fonte/URL: {len(urls)} unici, {len(rows)} citazioni, {len(errors)} errori")
    for err in errors:
        print("  " + err)
    return not errors


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=HERE / "statements.jsonl")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--command", help="Executable that reads one JSON request on stdin and prints one JSON response")
    source.add_argument("--endpoint", help="HTTP URL accepting one JSON request per statement")
    source.add_argument("--baseline", action="store_true", help="Use one model via OmniRoute on MiniPC")
    source.add_argument("--check-sources", action="store_true", help="GET all sources/evidence and check quotes verbatim")
    parser.add_argument("--timeout", type=int, default=45)
    parser.add_argument("--limit", type=int, help="Diagnostic sample size")
    parser.add_argument("--report-json", type=Path, help="Save raw cases and summary")
    args = parser.parse_args(argv)
    rows = load_rows(args.data)
    if args.limit is not None:
        rows = rows[:args.limit]
    if args.check_sources:
        return 0 if check_sources(rows, args.timeout) else 1
    mode, target = ("baseline", None) if args.baseline else (("command", args.command) if args.command else ("endpoint", args.endpoint))
    cases = benchmark(rows, lambda row: verdict(row, mode, target, args.timeout))
    summary = report(cases)
    if args.report_json:
        args.report_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if all(case["actual"] != "ERRORE" for case in cases) else 1


if __name__ == "__main__":
    sys.exit(main())
