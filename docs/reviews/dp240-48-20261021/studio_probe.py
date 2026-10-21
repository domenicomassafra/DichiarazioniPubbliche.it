"""DP-240 #48 real-source private source/rights/Studio preview, disposable SQLite.

Execute under MiniPC native heavy lock with PYTHONPATH=poc. No production writes.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import hashlib
from html import unescape
from html.parser import HTMLParser
import json
from pathlib import Path
import sqlite3
import tempfile
import urllib.request

from dichiarazioni_pubbliche.private_candidate_batch import CandidateBatch, CandidateBatchItem, _batch_digest
from dichiarazioni_pubbliche.multi_person_batch_v1 import (
    PrivateBatchResult, ReviewedPassageContext, build_private_batch_receipt_index,
    plan_isolated_candidate_batch, reconcile_isolated_private_results,
)
from dichiarazioni_pubbliche.multi_person_batch_store_v1 import PrivateBatchSQLiteStore
from dichiarazioni_pubbliche.studio_machine_candidate_handoff_v1 import (
    LocalPersistedBatchMachineHandoff, preview_private_batch_machine_handoff,
)

DATA = json.loads((Path(__file__).parent / "material.json").read_text())
ORIGINALS = json.loads((Path(__file__).parent / "original-passages.json").read_text())["items"]
COLLECTION = "collection:dp240:48:20261021"


class SourceText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def normalized_text(value: str) -> str:
    return " ".join(unescape(value).split())


def sha(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "DichiarazioniPubbliche DP-240 private test"})
    with urllib.request.urlopen(request, timeout=12) as response:
        if response.status != 200:
            raise RuntimeError("SOURCE_HTTP_NON_200")
        return response.read(1_000_001)


def run() -> dict:
    manifest_items = []
    contexts = {}
    rights_digests = {}
    source_span_matches = {}
    for material in DATA["items"]:
        original = fetch(material["url"])
        if sha(original) != material["sha256_html"]:
            raise RuntimeError(f"SOURCE_VERSION_CHANGED:{material['id']}")
        parser = SourceText()
        parser.feed(original.decode("utf-8", "replace"))
        source_text = normalized_text(" ".join(parser.parts))
        original_passage = ORIGINALS[material["id"]]["original_passage"]
        expected_excerpt = normalized_text(original_passage)
        model_excerpt = normalized_text(material["passage"])
        source_span_matches[material["id"]] = {
            "exact_after_whitespace_normalization": expected_excerpt in source_text,
            "prefix_50_found": expected_excerpt[:50] in source_text,
            "model_text_is_source_exact": model_excerpt == expected_excerpt,
            "original_passage_sha256": sha(original_passage.encode("utf-8")),
            "model_passage_sha256": sha(material["passage"].encode("utf-8")),
        }
        if expected_excerpt not in source_text:
            raise RuntimeError(f"SOURCE_PASSAGE_EXACT_MISMATCH:{material['id']}")
        rights = fetch(material["rights_url"])
        if "cc-by 3.0" not in rights.decode("utf-8", "replace").lower():
            raise RuntimeError(f"RIGHTS_TERM_MISSING:{material['id']}")
        rights_digests[material["id"]] = sha(rights)
        pid = f"passage:dp240:{material['id']}"
        cid = f"capture:dp240:{material['id']}"
        passage_hash = sha(original_passage.encode("utf-8"))
        row = CandidateBatchItem(
            passage_id=pid, content_id=material["content_id"],
            capture_id=cid, passage_sha256=passage_hash,
            canonical_url=material["url"],
            source_family=material["url"].split("/")[2],
            rights_record_id=f"rights:dp240:{material['id']}",
        )
        manifest_items.append(row)
        contexts[pid] = ReviewedPassageContext(
            passage_id=pid, capture_id=cid,
            source_sha256=material["sha256_html"],
            passage_sha256=passage_hash,
            selector_fingerprint="sha256:" + passage_hash,
            content_id=material["content_id"],
            source_family=row.source_family, language_tag="it",
            speaker_candidate_id=f"person-candidate:{material['id'].split('-20')[0]}",
            identity_review_status="CANDIDATE_MATCH",
            speech_role="QUOTED_SPEAKER", speech_act="REPORTED_QUOTE",
            context_version="source-excerpt-v1",
            context_review_id=f"ai-review:dp240:48:{material['id']}",
            rights_status="CLEARED", estimated_tokens=400,
        )

    unsigned = CandidateBatch(COLLECTION, tuple(manifest_items), "")
    manifest = replace(unsigned, sha256=_batch_digest(unsigned))
    plan = plan_isolated_candidate_batch(
        manifest, contexts, total_token_cap=900, provider_capability_ready=True
    )
    if len(plan.items) != 2 or len({i.partition_id for i in plan.items}) != 2:
        raise RuntimeError("PARTITION_ISOLATION_FAILED")
    if any(i.reason_code != "MULTIPERSON_QUOTATION_NOT_ENDORSEMENT" for i in plan.items):
        raise RuntimeError("UNEXPECTED_PROPOSAL_OR_HOLD")
    swapped = PrivateBatchResult(
        plan.items[0].passage_id, plan.items[1].content_id,
        plan.items[0].capture_id, plan.items[0].passage_sha256, "HELD", None, None
    )
    try:
        reconcile_isolated_private_results(plan, (swapped,))
    except ValueError as exc:
        if str(exc) != "MULTIPERSON_RESULT_SOURCE_MISMATCH":
            raise
        wrong_source_refused = True
    else:
        raise RuntimeError("WRONG_SOURCE_NOT_REFUSED")

    with tempfile.TemporaryDirectory(prefix="dp240-48-") as folder:
        root = Path(folder)
        store = PrivateBatchSQLiteStore(root / "batch.sqlite3")
        initial = store.register(plan)
        replay = store.register(plan)
        index = build_private_batch_receipt_index(plan, ())
        recovered = PrivateBatchSQLiteStore(root / "batch.sqlite3").resume(plan.plan_sha256)
        if not (initial == replay == recovered and recovered.index == index):
            raise RuntimeError("PERSISTENCE_REPLAY_FAILED")

        with sqlite3.connect(root / "studio.sqlite3") as connection:
            studio = LocalPersistedBatchMachineHandoff(connection)
            studio.init_isolated_fixture_schema()
            for material in DATA["items"]:
                row = next(x for x in plan.items if x.content_id == material["content_id"])
                source_id = "source:" + material["id"]
                connection.execute(
                    "INSERT INTO dp242_source VALUES (?,?,?,?)",
                    (source_id, COLLECTION, row.source_sha256, 1),
                )
                connection.execute(
                    "INSERT INTO dp242_capture VALUES (?,?,?,?,?,?,?)",
                    (row.capture_id, source_id, row.content_id, row.source_sha256, "CAPTURED", "NONE", 1),
                )
                connection.execute(
                    "INSERT INTO dp242_passage "
                    "(id,capture_id,content_id,passage_sha256,selector_fingerprint,"
                    "speaker_candidate_id,identity_review_status,speech_role,speech_act,"
                    "context_version,context_review_id,identity_revision,revision,handoff_revision) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (row.passage_id,row.capture_id,row.content_id,row.passage_sha256,
                     row.selector_fingerprint,row.speaker_candidate_id,row.identity_review_status,
                     row.speech_role,row.speech_act,row.context_version,row.context_review_id,1,1,0),
                )
                connection.execute(
                    "INSERT INTO dp242_rights VALUES (?,?,?,?)",
                    (row.capture_id,"CLEARED",rights_digests[material["id"]],1),
                )
            connection.commit()
            current = {row.passage_id: studio._load_snapshot(row.passage_id)[0] for row in plan.items}
            operator = preview_private_batch_machine_handoff(
                plan, index, current_items=current,
                expected_receipt_sha256=index.receipt_sha256,
                request_key="operator:dp240:48:20261021",
            )
            if any(v["status"] != "HELD_SOURCE_OR_ATTRIBUTION" for v in operator["items"]):
                raise RuntimeError("STUDIO_OPERATOR_STATUS_UNSAFE")
            if operator["publication_authority"] or operator["enqueued"]:
                raise RuntimeError("STUDIO_UNAUTHORIZED_PUBLISH")
            sources = [
                {
                    "passage_id": v["source"]["passage_id"],
                    "content_id": v["source"]["content_id"],
                    "speaker_candidate_id": v["source"]["speaker_candidate_id"],
                    "operator_status": v["status"],
                    "reason_code": next(z.reason_code for z in plan.items if z.passage_id == v["source"]["passage_id"]),
                }
                for v in operator["items"]
            ]
    return {
        "date_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "private disposable SQLite; no production corpus, Studio DB or publication changes",
        "collection": COLLECTION, "plan_sha256": plan.plan_sha256,
        "manifest_sha256": manifest.sha256, "batch_receipt_sha256": index.receipt_sha256,
        "wrong_cross_source_refused": wrong_source_refused,
        "plan_items": len(plan.items), "isolated_partitions": len({i.partition_id for i in plan.items}),
        "store_revision": recovered.revision, "replay_idempotent": True,
        "studio_operator_status": operator["status"], "studio_items": sources,
        "source_span_matches": source_span_matches,
        "rights_html_sha256_by_id": rights_digests,
        "publication_authority": False,
    }


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
