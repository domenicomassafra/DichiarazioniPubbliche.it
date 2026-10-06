#!/usr/bin/env python3
"""DP-431.7 acceptance: public HOLD cleanup preserves private DP-303 history."""

from __future__ import annotations

import json
import shutil
import socket
import subprocess
import sys
import tempfile
from pathlib import Path


WEB_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = WEB_ROOT.parent
sys.path.insert(0, str(WEB_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "poc"))

from check_dp431_rebuild import _build_seed, _hold_projection, _slug, _write_json  # noqa: E402
from dp431_rebuild import rebuild_static  # noqa: E402
from dichiarazioni_pubbliche.challenge_persistence import (  # noqa: E402
    ChallengeHoldDisposition,
    PrivateChallengeLedgerStore,
)
from dichiarazioni_pubbliche.policy.challenge_workflow import (  # noqa: E402
    ChallengeKind,
    ChallengeRole,
    ChallengeState,
)
from dichiarazioni_pubbliche.public_schema import validate_public_bundle  # noqa: E402


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _pg_bin(name: str) -> str:
    direct = shutil.which(name)
    if direct:
        return direct
    pg_config = shutil.which("pg_config")
    if pg_config:
        bindir = subprocess.run(
            [pg_config, "--bindir"],
            text=True,
            capture_output=True,
            check=True,
        ).stdout.strip()
        candidate = Path(bindir) / name
        if candidate.is_file():
            return str(candidate)
    raise RuntimeError(f"PostgreSQL tool unavailable: {name}")


def _run(args: list[str], *, input_text: str | None = None) -> str:
    result = subprocess.run(
        args,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"command failed ({result.returncode}): {' '.join(args)}\n{detail}")
    return result.stdout


def _psql(database_url: str, sql: str) -> str:
    return _run(
        [
            _pg_bin("psql"),
            "-X",
            "-qAt",
            "-v",
            "ON_ERROR_STOP=1",
            "--dbname",
            database_url,
        ],
        input_text=sql,
    ).strip()


def _event_chain(replay) -> tuple[tuple[object, ...], ...]:
    return tuple(
        (
            event.event_id,
            event.sequence,
            event.from_state.value if event.from_state else None,
            event.to_state.value,
            event.previous_event_id,
            event.previous_integrity_sha256,
            event.event_integrity_sha256,
            event.target_record_version,
        )
        for event in replay.events
    )


def main() -> int:
    old = json.loads(
        (WEB_ROOT / "src" / "data" / "demo-projection.json").read_text(encoding="utf-8")
    )
    validate_public_bundle(old)
    held_projection, removed_finding, _, _, _ = _hold_projection(old)
    assert old["dossiers"][0]["finding_id"] == removed_finding

    with tempfile.TemporaryDirectory(prefix="dp431-private-hold-pg-") as pg_raw:
        pg_root = Path(pg_raw)
        data_dir = pg_root / "data"
        port = _free_port()
        initdb = _pg_bin("initdb")
        pg_ctl = _pg_bin("pg_ctl")
        _run(
            [
                initdb,
                "-D",
                str(data_dir),
                "--username=postgres",
                "--auth=trust",
                "--encoding=UTF8",
                "--no-locale",
            ]
        )
        _run(
            [
                pg_ctl,
                "-D",
                str(data_dir),
                "-l",
                str(pg_root / "postgres.log"),
                "-o",
                f"-F -p {port} -h 127.0.0.1 -k {pg_root}",
                "-w",
                "start",
            ]
        )
        try:
            admin_url = f"postgresql://postgres@127.0.0.1:{port}/postgres"
            _psql(admin_url, "CREATE DATABASE dp431_private_hold;")
            database_url = f"postgresql://postgres@127.0.0.1:{port}/dp431_private_hold"
            _run(
                [
                    _pg_bin("psql"),
                    "-X",
                    "-v",
                    "ON_ERROR_STOP=1",
                    "--dbname",
                    database_url,
                    "-f",
                    str(REPO_ROOT / "db" / "schema.v1.sql"),
                ]
            )
            claim_id = "claim:dp431-private-hold"
            _psql(
                database_url,
                f"""
                INSERT INTO content_item(id, canonical_url)
                VALUES ('content:dp431-private-hold', 'https://example.test/dp431-private-hold');
                INSERT INTO atomic_claim(
                    id, content_id, normalized_claim, claim_type, temporal_scope,
                    check_worthy, metadata
                ) VALUES (
                    '{claim_id}', 'content:dp431-private-hold',
                    'DP-431 private hold fixture', 'CURRENT_POLICY', '{{}}'::jsonb,
                    true, '{{}}'::jsonb
                );
                INSERT INTO finding(
                    id, claim_id, assessment, rationale, publication_status,
                    policy_version, model_bundle
                ) VALUES (
                    '{removed_finding}', '{claim_id}', 'SUPPORTED',
                    'DP-431 private hold fixture rationale', 'PUBLISH',
                    'policy:dp431:private-hold:v1', '{{}}'::jsonb
                );
                """,
            )

            store = PrivateChallengeLedgerStore(database_url)
            root_event = store.initiate_request(
                kind=ChallengeKind.TAKEDOWN,
                target_finding_id=removed_finding,
                source_request_ref="challenge:dp431-private-hold",
                actor_ref="actor:dp431-intake",
                actor_role=ChallengeRole.INTAKE_ADAPTER,
                reason="Private DP-431 hold acceptance fixture",
            )
            triage = store.transition_request(
                root_event.request.request_id,
                actor_ref="actor:dp431-intake",
                actor_role=ChallengeRole.INTAKE_ADAPTER,
                reason="Private DP-431 hold acceptance fixture",
            )
            assert triage.event.to_state is ChallengeState.TRIAGE_PENDING
            approved = store.transition_request(
                root_event.request.request_id,
                actor_ref="reviewer:dp431-triage",
                actor_role=ChallengeRole.TRIAGE_REVIEWER,
                reason="Reviewed private DP-431 hold fixture",
                challenge_review_approved=True,
            )
            assert approved.event.to_state is ChallengeState.PUBLIC_HOLD_APPROVED
            hold_before = store.current_hold_for_finding(removed_finding)
            assert hold_before.disposition is ChallengeHoldDisposition.HOLD
            replay_before = store.replay_request(root_event.request.request_id)
            assert not replay_before.blockers
            chain_before = _event_chain(replay_before)
            assert len(chain_before) == 3

            with tempfile.TemporaryDirectory(
                prefix=".dp431-private-hold-web-",
                dir=WEB_ROOT,
            ) as web_raw:
                web_root = Path(web_raw)
                old_path = web_root / "old.json"
                held_path = web_root / "held.json"
                _write_json(old_path, old)
                _write_json(held_path, held_projection)
                seed = web_root / "seed"
                _build_seed(old_path, seed)
                publish = web_root / "publish"
                receipts = web_root / "receipts"
                shutil.copytree(seed, publish)
                receipt = rebuild_static(
                    old_projection_path=old_path,
                    new_projection_path=held_path,
                    publish_dir=publish,
                    receipt_dir=receipts,
                )
                assert receipt["status"] == "CONSISTENT"
                assert not (
                    publish / "dichiarazioni" / _slug(removed_finding)
                ).exists(), "held current Statement survived public rebuild"
                search = json.loads(
                    (publish / "search-index.v1.json").read_text(encoding="utf-8")
                )
                assert ("finding", removed_finding) not in {
                    (row["kind"], row["id"]) for row in search["records"]
                }
                assert search["projection_sha256"] == held_projection["dataset_sha256"]

            replay_after = store.replay_request(root_event.request.request_id)
            hold_after = store.current_hold_for_finding(removed_finding)
            assert not replay_after.blockers
            assert _event_chain(replay_after) == chain_before, "private challenge history changed during public rebuild"
            assert hold_after.disposition is ChallengeHoldDisposition.HOLD
            assert hold_after.request_id == hold_before.request_id
            assert hold_after.event_id == hold_before.event_id
            request_count = int(
                _psql(
                    database_url,
                    f"SELECT count(*) FROM private_challenge_request WHERE request_id='{root_event.request.request_id}';",
                )
            )
            event_count = int(
                _psql(
                    database_url,
                    f"SELECT count(*) FROM private_challenge_event WHERE request_id='{root_event.request.request_id}';",
                )
            )
            assert request_count == 1
            assert event_count == 3
            print(
                "dp431-private-hold checks PASS "
                f"(finding {removed_finding}; public fingerprint {held_projection['dataset_sha256'][:12]}; "
                f"private request 1/event chain {event_count} unchanged; authoritative HOLD preserved)"
            )
        finally:
            _run([pg_ctl, "-D", str(data_dir), "-m", "fast", "-w", "stop"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
