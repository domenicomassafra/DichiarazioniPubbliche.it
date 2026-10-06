from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict
from pathlib import Path

from dichiarazioni_pubbliche.publication_review_control import PublicationReviewEvent
from dichiarazioni_pubbliche.reviewer_identity_authority import (
    LocalFileReviewerIdentityAuthority,
    provision_reviewer_credential,
)


def _event_from_file(path: str | Path) -> PublicationReviewEvent:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("REVIEWER_IDENTITY_EVENT_FILE_INVALID") from exc
    if not isinstance(payload, dict):
        raise ValueError("REVIEWER_IDENTITY_EVENT_FILE_INVALID")
    values = dict(payload)
    reason_codes = values.get("reason_codes") or ()
    if not isinstance(reason_codes, (list, tuple)):
        raise ValueError("REVIEWER_IDENTITY_EVENT_REASON_CODES_INVALID")
    values["reason_codes"] = tuple(str(value) for value in reason_codes)
    try:
        return PublicationReviewEvent(**values)
    except TypeError as exc:
        raise ValueError("REVIEWER_IDENTITY_EVENT_FILE_INVALID") from exc


def _safe_identity_payload(identity) -> dict[str, str]:
    return {
        "credential_id": identity.credential_id,
        "actor_ref": identity.actor_ref,
        "credential_fingerprint": identity.credential_fingerprint,
        "key_version": identity.key_version,
        "status": identity.status,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Local/off-DB reviewer identity authority administration."
    )
    parser.add_argument(
        "--root",
        default=os.environ.get("DICHIARAZIONI_PUBBLICHE_REVIEWER_AUTHORITY_ROOT"),
        required=os.environ.get("DICHIARAZIONI_PUBBLICHE_REVIEWER_AUTHORITY_ROOT") is None,
        help="Private 0700 authority directory outside PostgreSQL and the repository.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    provision = sub.add_parser("provision")
    provision.add_argument("--credential-id", required=True)
    provision.add_argument("--actor", required=True)
    provision.add_argument("--key-version", required=True)

    show = sub.add_parser("show")
    show.add_argument("--credential-id", required=True)

    revoke = sub.add_parser("revoke")
    revoke.add_argument("--credential-id", required=True)

    attest = sub.add_parser("attest-event")
    attest.add_argument("--credential-id", required=True)
    attest.add_argument("--event-json", required=True)
    attest.add_argument("--issued-at", required=True)

    resolve = sub.add_parser("resolve")
    resolve.add_argument("--receipt-id", required=True)

    args = parser.parse_args()
    if args.command == "provision":
        identity = provision_reviewer_credential(
            args.root,
            credential_id=args.credential_id,
            actor_ref=args.actor,
            key_version=args.key_version,
        )
        output = _safe_identity_payload(identity)
    else:
        authority = LocalFileReviewerIdentityAuthority(args.root)
        if args.command == "show":
            output = _safe_identity_payload(
                authority.identity(args.credential_id, require_active=False)
            )
        elif args.command == "revoke":
            output = _safe_identity_payload(authority.revoke(args.credential_id))
        elif args.command == "attest-event":
            event = _event_from_file(args.event_json)
            attestation = authority.issue(
                event,
                credential_id=args.credential_id,
                issued_at=args.issued_at,
            )
            output = asdict(attestation)
        elif args.command == "resolve":
            attestation = authority.resolve(args.receipt_id)
            if attestation is None:
                raise SystemExit("REVIEWER_IDENTITY_RECEIPT_NOT_VERIFIED")
            output = asdict(attestation)
        else:  # pragma: no cover - argparse makes this unreachable.
            raise SystemExit("REVIEWER_IDENTITY_COMMAND_INVALID")
    print(json.dumps(output, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
