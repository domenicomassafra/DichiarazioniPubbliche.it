"""Explicit opt-in, isolated private Studio Discovery annotations (DP-417).

The ordinary StudioLoopbackServer stays read-only.  This separate loopback
listener cannot write without BOTH its private operator token AND a matching,
already issued off-DB reviewer receipt for the exact intent. It never mints
attestations, claims provenance/rights approval or triggers jobs.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from dichiarazioni_pubbliche.reviewer_identity_authority import LocalFileReviewerIdentityAuthority
from dichiarazioni_pubbliche.studio_discovery_triage_store import StudioDiscoveryTriageStore
from dichiarazioni_pubbliche.studio_local_api import (
    STUDIO_LOCAL_MAX_BODY_BYTES,
    StudioLocalHandler, StudioLocalReaders, StudioLoopbackServer, _fields,
    _StudioCorpusReader, _StudioCaptureReader, _StudioCandidateReader,
    _StudioQueueReader, _StudioPromotionContextReader, _StudioDecisionReader,
    load_private_token,
)

TRIAGE_PATH = "/v1/discovery/triage-annotate"
TRIAGE_API_VERSION = "studio-private-annotation-api-v1"
_REQUIRED = frozenset({
    "collection_id", "hit_id", "request_key", "decision",
    "expected_revision", "actor_ref", "receipt_id", "confirm_private_annotation",
})


def _reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("STUDIO_TRIAGE_DUPLICATE_JSON_KEY")
        value[key] = item
    return value


class _TriageHandler(StudioLocalHandler):
    server: "StudioTriageMutationServer"

    def _process(self) -> None:
        if self.path != TRIAGE_PATH:
            super()._process()
            return
        if not self._allowed_client():
            self._reply(403, {"error": "STUDIO_LOCAL_ORIGIN_OR_HOST_REFUSED"})
            return
        if not self._authorized():
            self._reply(401, {"error": "STUDIO_LOCAL_AUTH_REQUIRED"})
            return
        if self.command != "POST":
            self._reply(405, {"error": "STUDIO_LOCAL_METHOD_NOT_ALLOWED"})
            return
        if self.headers.get_all("Content-Type", []) != ["application/json"]:
            self._reply(415, {"error": "STUDIO_LOCAL_JSON_REQUIRED"})
            return
        lengths = self.headers.get_all("Content-Length", [])
        if (len(lengths) != 1 or not lengths[0].isascii()
                or not lengths[0].isdigit() or len(lengths[0]) > 5):
            self._reply(400, {"error": "STUDIO_LOCAL_CONTENT_LENGTH_INVALID"})
            return
        size = int(lengths[0])
        if size < 1 or size > STUDIO_LOCAL_MAX_BODY_BYTES:
            self._reply(413, {"error": "STUDIO_LOCAL_BODY_LIMIT"})
            return
        try:
            data = json.loads(self.rfile.read(size).decode("utf-8"),
                              object_pairs_hook=_reject_duplicates)
            if not isinstance(data, dict):
                raise ValueError
            _fields(data, required=set(_REQUIRED))
            if data["confirm_private_annotation"] is not True:
                raise ValueError("STUDIO_TRIAGE_EXPLICIT_CONFIRMATION_REQUIRED")
            # Only one pre-issued authority receipt can authenticate the exact
            # payload. The HTTP bearer never substitutes for reviewer identity.
            receipt_id = data["receipt_id"]
            if not isinstance(receipt_id, str):
                raise ValueError("STUDIO_TRIAGE_RECEIPT_ID_INVALID")
            payload = {k: data[k] for k in _REQUIRED -
                       {"confirm_private_annotation", "receipt_id"}}
            result = self.server.triage_store.record_attested(
                authority=self.server.triage_authority, receipt_id=receipt_id,
                **payload,
            )
            code = result.get("result_code")
            if code not in {"CREATED", "REPLAY", "REVISION_CONFLICT",
                            "IDEMPOTENCY_CONFLICT", "SCOPE_NOT_FOUND"}:
                raise ValueError("STUDIO_TRIAGE_RESULT_INVALID")
            # Do not echo the actor, receipt ID, request key, proof or source
            # metadata. Clients separately read exact PG history after writes.
            response = {
                "contract_version": "studio-private-triage-annotation-v1",
                "private_only": True, "mutation_kind": "ANNOTATION_ONLY",
                "result_code": code, "collection_id": result["collection_id"],
                "hit_id": result["hit_id"], "decision": result["decision"],
                "revision": result["revision"],
                "payload_sha256": result["payload_sha256"],
                "actor_attested": code in {"CREATED", "REPLAY"} and
                    result.get("actor_attested") is True,
                "capture_authorized": False, "triage_action_authorized": False,
                "promotion_authority": False, "publication_authority": False,
            }
            self._reply(200 if code in {"CREATED", "REPLAY"} else 409,
                        {"contract_version": TRIAGE_API_VERSION, "data": response})
        except (ValueError, TypeError, UnicodeError, KeyError):
            self._reply(422, {"error": "STUDIO_TRIAGE_REQUEST_OR_ATTESTATION_REFUSED"})
        except Exception:
            self._reply(503, {"error": "STUDIO_TRIAGE_STORE_UNAVAILABLE"})

    do_POST = _process


class StudioTriageMutationServer(StudioLoopbackServer):
    """Never instantiated by the normal read-only Studio CLI."""

    def __init__(
        self, port: int, readers: StudioLocalReaders, token: str, *,
        store: StudioDiscoveryTriageStore,
        authority: LocalFileReviewerIdentityAuthority,
    ) -> None:
        if type(store) is not StudioDiscoveryTriageStore or \
                type(authority) is not LocalFileReviewerIdentityAuthority:
            raise ValueError("STUDIO_TRIAGE_EXPLICIT_STORE_AUTHORITY_REQUIRED")
        self.triage_store = store
        self.triage_authority = authority
        super().__init__(port, readers, token)
        # The inherited read-only handler remains the default elsewhere.
        self.RequestHandlerClass = _TriageHandler


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Explicit private signed Discovery annotation loopback; not a public API"
    )
    parser.add_argument("--token-file", required=True, type=Path)
    parser.add_argument("--authority-root", required=True, type=Path)
    parser.add_argument("--port", type=int, default=18778)
    parser.add_argument("--confirm-private-annotation-mode", action="store_true")
    options = parser.parse_args(argv)
    if not options.confirm_private_annotation_mode:
        parser.error("explicit --confirm-private-annotation-mode is required")
    try:
        token = load_private_token(options.token_file)
        authority = LocalFileReviewerIdentityAuthority(options.authority_root)
        # DB grants are operator-provided, not escalated or auto-provisioned.
        store = StudioDiscoveryTriageStore()
        readers = StudioLocalReaders(
            corpus=_StudioCorpusReader(), captures=_StudioCaptureReader(),
            candidates=_StudioCandidateReader(), queues=_StudioQueueReader(),
            promotion_context=_StudioPromotionContextReader(),
            decision_reader=_StudioDecisionReader(),
        )
        with StudioTriageMutationServer( options.port, readers, token,
              store=store, authority=authority) as server:
            print(f"Private Studio annotation listener 127.0.0.1:{server.server_port}; "
                  "separate signed reviewer receipt required", flush=True)
            server.serve_forever(poll_interval=0.2)
    except (OSError, ValueError, UnicodeError):
        print("STUDIO_PRIVATE_MUTATION_STARTUP_REFUSED", flush=True)
        return 2
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
