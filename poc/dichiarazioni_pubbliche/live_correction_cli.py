"""Explicit opt-in server for authenticated public corrections and live HOLD."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from typing import Iterable

from .challenge_persistence import PrivateChallengeLedgerStore
from .cloudflare_correction_purge import CloudflareCorrectionPurge
from .live_correction_http import build_live_correction_server
from .public_account import (
    AccountService, AccountStore, GoogleOidcProvider, read_secret_file,
)
from .queue_runtime import QueueRuntimeStore
from .review_admin import enqueue_reanalysis_trigger


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Authenticated correction HOLD + edge readback listener.")
    parser.add_argument("--projection-path", type=Path, required=True)
    parser.add_argument("--static-dir", type=Path, required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=18090)
    parser.add_argument("--account-client-id", required=True)
    parser.add_argument("--account-client-secret-file", type=Path, required=True)
    parser.add_argument("--account-db", type=Path, required=True)
    parser.add_argument("--account-site-origin", required=True)
    parser.add_argument("--correction-cloudflare-zone", required=True)
    parser.add_argument("--correction-cloudflare-token-file", type=Path, required=True)
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.host not in {"127.0.0.1", "::1"}:
        parser.error("correction intake must bind loopback behind the authenticated public proxy")
    if args.account_site_origin != "https://dichiarazionipubbliche.it":
        parser.error("the registered canonical HTTPS account origin is required")
    if not args.static_dir.is_dir() or not args.projection_path.is_file():
        parser.error("the actual public static release and projection must exist")
    private_paths = (
        args.account_client_secret_file, args.account_db,
        args.correction_cloudflare_token_file,
    )
    static_root = args.static_dir.resolve()
    if any(path.resolve().is_relative_to(static_root) for path in private_paths):
        parser.error("correction private credentials must stay outside the public static root")
    try:
        client_secret = read_secret_file(args.account_client_secret_file)
        account_store = AccountStore(args.account_db)
        provider = GoogleOidcProvider(
            args.account_client_id, client_secret,
            args.account_site_origin + "/account/oauth/callback",
        )
        account_service = AccountService(
            args.account_client_id, args.account_site_origin,
            account_store, provider, visitor_key=client_secret,
        )
        purge = CloudflareCorrectionPurge(
            zone_id=args.correction_cloudflare_zone,
            token=read_secret_file(args.correction_cloudflare_token_file),
            site_origin=args.account_site_origin,
        )
    except (OSError, ValueError, UnicodeError) as exc:
        # No secret values appear in the error's input; keep diagnostics bounded.
        parser.error(f"correction private configuration refused: {type(exc).__name__}")

    ledger = PrivateChallengeLedgerStore()
    queue = QueueRuntimeStore()

    def enqueue(finding_id: str, request_id: str) -> bool:
        context = queue.finding_context(finding_id)
        job_id = enqueue_reanalysis_trigger(
            queue,
            claim_id=context["claim_id"],
            trigger_type="CORRECTION",
            source_type="PUBLIC_CORRECTION_CHALLENGE",
            source_id=request_id,
            source_hash=hashlib.sha256(request_id.encode()).hexdigest(),
        )
        return job_id.startswith("job:")

    server = build_live_correction_server(
        str(args.projection_path), host=args.host, port=args.port,
        static_dir=str(args.static_dir), account_service=account_service,
        account_private_secret_path=str(args.account_client_secret_file),
        correction_ledger=ledger, correction_enqueue=enqueue, correction_purge=purge,
    )
    print(f"Correction HOLD HTTP on http://{args.host}:{server.server_port}/intake/corrections")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
