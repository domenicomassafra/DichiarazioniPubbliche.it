"""DP-638 — the daily machine: sources in, published statements with a verdict out.

One bounded run does the whole chain, once a day, without a human:

    config/daily-sources.v1.json
        -> discovery (per source RSS/Atom feed)            daily_capture
        -> capture (article, captions, or transcription)   daily_capture
        -> statements (exact quote, person, moment)        daily_statements
        -> verdict (model pass + independent check)        daily_verdict
        -> publication (public projection records)         daily_publication
        -> evening summary (existing Hermes delivery)

What it deliberately does not do: acquisition permits, relevance authorities,
review chains, witnesses, receipt matching. The relevance decision is taken
automatically here and recorded with its reason on the content item; the
accuracy rules (exact words, right person, source link and date, evidence links
on a verdict) are enforced in code.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import date
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

from dichiarazioni_pubbliche.daily_capture import (
    Capture,
    DiscoveredItem,
    capture_item,
    capture_youtube,
    discover,
)
from dichiarazioni_pubbliche.daily_config import DailyConfig, SourceSpec, load_config
from dichiarazioni_pubbliche.daily_model import ModelClient
from dichiarazioni_pubbliche.daily_statements import (
    ExtractedStatement,
    extract_statements,
    moment_selection,
    resolve_speaker,
)
from dichiarazioni_pubbliche.daily_store import (
    HELD_DUPLICATE,
    HELD_NO_SPEAKER,
    HELD_NO_VERDICT,
    PUBLISHED,
    DailyStore,
)
from dichiarazioni_pubbliche.daily_text import (
    DailyMachineError,
    _search_form,
    bounded_text,
    find_verbatim,
    html_to_text,
    parse_model_json,
    sha256_text,
    utc_now,
)
from dichiarazioni_pubbliche.daily_model import fetch_text
from dichiarazioni_pubbliche.daily_summary import deliver_evening_summary, evening_summary
from dichiarazioni_pubbliche.daily_verdict import (
    _claim_tokens,
    decide_verdict,
    verify_evidence,
)
from dichiarazioni_pubbliche.scheduler import deterministic_content_id

# --------------------------------------------------------------------------
# run
# --------------------------------------------------------------------------


def _statement_id(source_id: str, content_id: str, offset: int, quote: str) -> str:
    material = "\0".join((source_id, content_id, str(offset), sha256_text(quote)[:16]))
    return "statement:" + hashlib.sha256(material.encode()).hexdigest()[:32]


def _capture_id(content_id: str, kind: str) -> str:
    return "capture:" + hashlib.sha256(f"{content_id}\0{kind}".encode()).hexdigest()[:32]


def _flush_calls(
    store: DailyStore,
    client: ModelClient,
    *,
    content_id: str,
    reference: str,
    dry_run: bool,
    report: dict[str, Any],
) -> None:
    """Write one provider receipt per real model call and count them."""

    for reply in client.calls:
        report["model_calls"] += 1
        if dry_run:
            continue
        store.write_receipt(
            content_id=content_id,
            provider_id="omniroute",
            model_id=reply.model,
            operation=reply.operation,
            request_key=f"{reference}:{reply.model}:{reply.operation}",
            latency_seconds=reply.latency_seconds,
            usage=reply.usage,
        )
    client.calls.clear()


def _corroborating_sources(
    quote: str,
    source_url: str,
    pool: Sequence[dict[str, str]],
    *,
    limit: int = 2,
) -> list[dict[str, str]]:
    """Pick other same-run captures that share vocabulary with the statement.

    They are real pages this run already downloaded, so the verdict pass can
    ground its reasoning and cite a link that exists.
    """

    tokens = _claim_tokens(quote)
    if not tokens:
        return []
    scored: list[tuple[int, dict[str, str]]] = []
    for entry in pool:
        if entry["url"].rstrip("/") == source_url.rstrip("/"):
            continue
        text, _ = _search_form(entry["text"][:20000])
        score = sum(1 for token in tokens if token in text)
        if score >= 2:
            scored.append((score, entry))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [entry for _, entry in scored[:limit]]


def _relevance_decision(config: DailyConfig, item: DiscoveredItem) -> dict[str, Any]:
    rule = config.relevance_rule
    return {
        "decision": "RELEVANT",
        "rule": str(rule.get("id") or "PUBLIC_FIGURE_SPEAKING_IN_PUBLIC_ON_PUBLIC_INTEREST"),
        "reason": str(rule.get("reason") or ""),
        "source_id": item.source.id,
        "decided_at": utc_now(),
    }


def run_daily(
    config: DailyConfig,
    store: DailyStore,
    client: ModelClient,
    *,
    run_date: str | None = None,
    dry_run: bool = False,
    reprocess: bool = False,
    skip_sources: Iterable[str] = (),
    max_seconds: float = 3000.0,
    discovery_fetcher: Callable[[str], str] | None = None,
    article_fetcher: Callable[..., tuple[int, str]] = fetch_text,
    evidence_fetcher: Callable[..., tuple[int, str]] = fetch_text,
    youtube_capture: Callable[..., Capture] = capture_youtube,
    log: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    day = run_date or date.today().isoformat()
    say = log or (lambda message: print(message, file=sys.stderr))
    started_at = utc_now()
    deadline = time.monotonic() + max(float(max_seconds), 60.0)
    report: dict[str, Any] = {
        "run_date": day,
        "started_at": started_at,
        "items": 0,
        "captures": 0,
        "statements": 0,
        "verdicts": 0,
        "published": 0,
        "held": {},
        "sources": {},
        "failures": [],
        "model_calls": 0,
        "statement_seconds": 0.0,
    }
    statement_model = config.model("statements", "opencode-go/deepseek-v4.1-flash")
    verdict_model = config.model("verdict", "antigravity/gemini-3.8-flash-tiered")
    check_model = config.model("check", "opencode-go/deepseek-v4.1-flash")
    asr_model = config.model("asr", "whisper")
    max_statements = config.limit("max_statements_per_capture", 8) or 8

    items, failures = discover(config, fetcher=discovery_fetcher, skip_sources=skip_sources)
    report["failures"].extend(failures)
    report["items"] = len(items)
    say(f"discovery: {len(items)} items from {len(config.sources)} sources")
    if not items:
        report["finished_at"] = utc_now()
        if not dry_run:
            store.record_run(day, report, finished=True)
        return report

    for source in {item.source.id: item.source for item in items}.values():
        if not dry_run:
            store.upsert_source(source)

    rows = []
    for item in items:
        content = item.content
        rows.append(
            {
                "content_id": deterministic_content_id(
                    "\0".join((content.source_id, content.external_id))
                ),
                "source_id": content.source_id,
                "external_id": content.external_id,
                "title": bounded_text(content.title, 500),
                "description": bounded_text(content.description or "", 2000),
                "canonical_url": content.canonical_url,
                "published_at": content.published_at or "",
                "duration_ms": (content.duration_seconds or 0) * 1000 or None,
                "metadata": {
                    "platform": content.platform,
                    "publisher": item.source.publisher,
                    "ingestion_relevance": _relevance_decision(config, item),
                    "daily_machine": "DP-638",
                },
            }
        )
    persisted = store.save_items(rows) if not dry_run else [row["content_id"] for row in rows]
    content_ids = {row["content_id"]: cid for row, cid in zip(rows, persisted)}

    captured_today = store.capture_ids_today(day) if not dry_run else set()
    capture_pool: list[dict[str, str]] = []
    for item in items:
        if time.monotonic() > deadline:
            report["budget_exhausted"] = True
            say("budget exhausted: stopping before the remaining items")
            break
        content_id = content_ids.get(
            deterministic_content_id(
                "\0".join((item.content.source_id, item.content.external_id))
            )
        )
        if not content_id:
            continue
        if content_id in captured_today and not dry_run and not reprocess:
            continue
        capture_started = time.monotonic()
        try:
            capture = capture_item(
                item,
                article_fetcher=article_fetcher,
                youtube_capture=lambda row: youtube_capture(
                    row,
                    transcriber=lambda path: client.transcribe(path, model=asr_model),
                ),
            )
        except Exception as exc:
            report["failures"].append(
                {"source_id": item.source.id, "error": f"CAPTURE:{type(exc).__name__}"}
            )
            continue
        report["sources"].setdefault(item.source.id, 0)
        report["sources"][item.source.id] += 1
        capture_pool.append(
            {
                "url": capture.url,
                "title": item.content.title,
                "publisher": item.source.publisher,
                "text": capture.body,
            }
        )
        report["captures"] += 1
        say(f"captured {item.source.id}: {len(capture.body)} chars ({capture.kind})")
        capture_id = _capture_id(content_id, capture.kind)
        if not dry_run:
            store.save_capture(
                capture_id=capture_id,
                content_id=content_id,
                source_id=item.source.id,
                capture=capture,
            )
        calls_before_extraction = len(client.calls)
        try:
            statements = extract_statements(
                client, statement_model, capture, item, limit=max_statements
            )
        except Exception as exc:  # a model outage must not stop the day
            report["failures"].append(
                {"source_id": item.source.id, "error": f"EXTRACTION:{type(exc).__name__}"}
            )
            client.calls.clear()
            continue
        report["model_calls"] += len(client.calls) - calls_before_extraction
        _flush_calls(
            store,
            client,
            content_id=content_id,
            reference=f"extract:{content_id}",
            dry_run=dry_run,
            report=report,
        )
        for statement in statements:
            if time.monotonic() > deadline:
                report["budget_exhausted"] = True
                break
            statement_started = time.monotonic()
            found = find_verbatim(capture.body, statement.quote)
            if found is None:
                report["held"]["NO_VERBATIM_QUOTE"] = report["held"].get("NO_VERBATIM_QUOTE", 0) + 1
                continue
            exact_quote = capture.body[found[0] : found[1]]
            speaker_key = resolve_speaker(statement, capture, item)
            status = PUBLISHED if speaker_key else HELD_NO_SPEAKER
            reason = "" if speaker_key else "SPEAKER_NOT_RESOLVED_IN_SOURCE"
            moment = moment_selection(found[0], found[1], capture, statement.moment)
            statement_id = _statement_id(item.source.id, content_id, found[0], exact_quote)
            row = {
                "id": statement_id,
                "content_id": content_id,
                "capture_id": capture_id,
                "source_id": item.source.id,
                "source_url": item.content.canonical_url,
                "source_title": bounded_text(item.content.title, 500),
                "source_publisher": item.source.publisher,
                "source_published_at": item.content.published_at or "",
                "statement_date": item.published_day,
                "quote": exact_quote,
                "quote_offset": found[0],
                "moment_label": moment["moment_label"],
                "speaker_name": statement.speaker if speaker_key else "",
                "speaker_role": statement.speaker_role if speaker_key else "",
                "speaker_key": speaker_key,
                "topic": statement.topic,
                "claim_nature": statement.nature,
                "status": status,
                "status_reason": reason,
                "extraction_model": statement_model,
                "metadata": json.dumps(moment, ensure_ascii=False),
            }
            report["statements"] += 1
            verdict: dict[str, Any] | None = None
            if status == PUBLISHED:
                context = capture.body[max(found[0] - 2500, 0) : found[1] + 2500]
                others = _corroborating_sources(exact_quote, capture.url, capture_pool)
                try:
                    verdict = decide_verdict(
                        client,
                        verdict_model=verdict_model,
                        check_model=check_model,
                        statement=statement,
                        statement_date=item.published_day,
                        source_url=item.content.canonical_url,
                        speaker=statement.speaker,
                        speaker_role=statement.speaker_role,
                        context=context,
                        other_sources=others,
                        fetcher=evidence_fetcher,
                    )
                except Exception as exc:  # a model outage must not stop the day
                    report["failures"].append(
                        {"source_id": item.source.id, "error": f"VERDICT:{type(exc).__name__}"}
                    )
                    row["status"] = HELD_NO_VERDICT
                    row["status_reason"] = "VERDICT_PASS_FAILED"
                else:
                    report["verdicts"] += 1
                    row["claim_nature"] = (
                        "OPINION" if verdict["verdict"] == "OPINION" else "FACTUAL"
                    )
            statement_seconds = round(time.monotonic() - statement_started, 3)
            report["statement_seconds"] += statement_seconds
            if row["status"] == PUBLISHED:
                report["published"] += 1
            else:
                report["held"][row["status"]] = report["held"].get(row["status"], 0) + 1

            for reply in client.calls:
                report["model_calls"] += 1
                if not dry_run:
                    store.write_receipt(
                        content_id=content_id,
                        provider_id="omniroute",
                        model_id=reply.model,
                        operation=reply.operation,
                        request_key=f"{statement_id}:{reply.model}:{reply.operation}",
                        latency_seconds=reply.latency_seconds,
                        usage=reply.usage,
                    )
            client.calls.clear()
            if not dry_run:
                store.save_statement(row)
                if verdict is not None:
                    store.save_verdict(statement_id, verdict)
    report["finished_at"] = utc_now()
    if not dry_run:
        store.record_run(day, report, finished=True)
    return report



def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="DP-638 daily machine: sources to published verdicts.")
    parser.add_argument("--config", default=os.environ.get("DICHIARAZIONI_PUBBLICHE_DAILY_SOURCES", ""))
    parser.add_argument("--database-url", default=os.environ.get("DICHIARAZIONI_PUBBLICHE_DATABASE_URL"))
    parser.add_argument("--run-date", default=date.today().isoformat())
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--reprocess", action="store_true", help="recapture items already captured today")
    parser.add_argument("--skip-source", action="append", default=[])
    parser.add_argument("--skip-kind", action="append", default=[])
    parser.add_argument("--report", default="")
    parser.add_argument("--max-seconds", type=float, default=3000.0)
    parser.add_argument("--summary", action="store_true", help="print the evening summary for --run-date")
    parser.add_argument("--print-summary-only", action="store_true")
    parser.add_argument("--evening-summary", action="store_true", help="compose the evening summary")
    parser.add_argument("--deliver", action="store_true", help="actually send the summary to the owner")
    parser.add_argument("--summary-file", default="")
    args = parser.parse_args(argv)

    config = load_config(args.config or None)
    skip_sources = list(args.skip_source)
    if args.skip_kind:
        skip_sources.extend(
            source.id for source in config.sources if source.kind in set(args.skip_kind)
        )
    store = DailyStore(args.database_url)
    if args.evening_summary:
        text = evening_summary(store, args.run_date)
        result = deliver_evening_summary(
            text,
            config=config,
            summary_file=Path(args.summary_file) if args.summary_file else None,
            deliver=bool(args.deliver),
        )
        print(text)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    if args.summary or args.print_summary_only:
        print(evening_summary(store, args.run_date))
        return 0
    api_key = os.environ.get("OMNIROUTE_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("OMNIROUTE_API_KEY_MISSING")
    client = ModelClient(api_key, config.model("base_url", "http://100.94.144.48:20128/v1"))
    report = run_daily(
        config,
        store,
        client,
        run_date=args.run_date,
        dry_run=args.dry_run,
        reprocess=args.reprocess,
        skip_sources=skip_sources,
        max_seconds=args.max_seconds,
    )
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.report:
        Path(args.report).write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
