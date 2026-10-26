#!/usr/bin/env python3
"""DP-458: real persisted source through DP-413B v3; always fail closed.

A live capture/rights reader rechecks PostgreSQL and original bytes. The
challenge and independent review authorities are intentionally unavailable
until authenticated real services exist; no fake agents or publication.
"""
from __future__ import annotations
import argparse, json, os, sys, urllib.request
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"poc"))
import dp458_real_source_packet as packet
from dichiarazioni_pubbliche.autonomous_publication import (
    AutonomousCandidate, SpeakerSignal, evaluate_autonomous_publication,
)
from dichiarazioni_pubbliche.autonomous_operations import AutonomousOperations
from dichiarazioni_pubbliche.autonomous_runner_v3 import PersistentRunner, SQLiteRunJournal
from dichiarazioni_pubbliche.capture_pipeline import CapturePipelineStore
from dichiarazioni_pubbliche.rights_registry import PrivateRightsRegistryStore, RightsSubject

class RealSource:
    def __init__(self, db, root):
        self.db=db; self.root=root
    def current(self, record_id):
        if record_id!=packet.CANDIDATE: return None
        packet.verify(self.db,self.root)   # exact live rights, body SHA, passage, HOLD
        cap=self.db.find_capture(packet.CONTENT,packet.ORIGINAL_SHA)
        subject=RightsSubject(packet.FAMILY,"URL",packet.URL,content_id=packet.CONTENT)
        rights=PrivateRightsRegistryStore(database_url=self.db.database_url).read_current(subject)
        if rights is None: return None
        row=self.db.run("""SELECT count(*) FROM statement_candidate
             WHERE id=:'id' AND status='HELD' AND statement_text_hash=:'sha'
             AND speaker_person_id=:'person';""",
             id=packet.CANDIDATE,sha=packet.sha(packet.QUOTE),person=packet.PERSON)
        if row!="1": return None
        return AutonomousCandidate(
            record_id=packet.CANDIDATE,
            record_version_id=packet.VERSION+":"+packet.sha(packet.QUOTE),
            source_version=packet.ORIGINAL_SHA,
            rights_attestation_sha256=packet.sha(rights.id+":"+rights.policy_version),
            source_url=packet.PAGE,source_kind="TIMED",
            snapshot_url=packet.URL,snapshot_sha256=cap["content_sha256"],
            source_text_sha256=packet.sha(packet.QUOTE),
            captured_at=cap["observed_at"],
            segment_start=packet.START/1000,
            segment_end=packet.END/1000,
            quote=packet.QUOTE,transcript_segment=packet.QUOTE,
            alignment_confidence=0.0,  # No independent acoustic validation
            speaker_id=packet.PERSON,
            speaker_signals=(
                SpeakerSignal("official_channel",packet.PAGE),
                SpeakerSignal("public_record",packet.ROLE)),
            public_role_source_url=packet.ROLE,
            public_context_source_url=packet.PAGE,
            person_is_minor=False,sensitive_third_party_data=False,
            privacy_cleared=False,
            privacy_citation_url="https://audiovisual.ec.europa.eu/en/data-protection",
            rights_cleared=False,rights_citation_url=packet.PAGE,
            source_length_chars=5483,contains_editorial_judgment=False,
        )

class UnverifiedChallenge:
    def current(self, record_id):
        raise RuntimeError("DP458_LIVE_CHALLENGE_AUTHORITY_NOT_CONNECTED")

class NoAttestedModel:
    model_id="antigravity/gemini-3.8-flash-tiered"
    def __init__(self, agent_id): self.agent_id=agent_id
    def review(self, candidate, fingerprint):
        raise RuntimeError("DP458_SECOND_INDEPENDENT_MODEL_NOT_AVAILABLE")

class LiveReadOnlySurface:
    def __init__(self): self.reads=0
    def _read(self):
        request=urllib.request.Request(
            "http://127.0.0.1:18090/api/v1/health",
            headers={"Accept":"application/json"})
        with urllib.request.urlopen(request,timeout=5) as response:
            value=json.load(response)
        if (value["data"].get("status")!="ok"
            or value["data"].get("dossier_count")!=0
            or value["meta"].get("contract_status")!="DRAFT"
            or value["data"].get("public_schema_version")!="dichiarazioni-pubbliche-public-v2"):
            raise RuntimeError("DP458_PUBLIC_V2_READBACK_UNVERIFIED")
        self.reads+=1
    def current_evidence_sha256(self, record_id):
        self._read()
        return None
    def withdraw(self, record_id):
        # v2 with zero dossiers has no live v3 identity to withdraw;
        # this is *not* a production v3 write/withdraw adapter.
        self._read()
    def publish(self, packet):
        raise RuntimeError("DP458_PUBLICATION_FORBIDDEN")

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root",type=Path,default=Path(
        "~/.local/share/dichiarazioni-pubbliche/dp458").expanduser())
    args=parser.parse_args()
    dsn=os.environ.get("DICHIARAZIONI_PUBBLICHE_DATABASE_URL")
    if not dsn: parser.error("DICHIARAZIONI_PUBBLICHE_DATABASE_URL missing")
    try:
        db=CapturePipelineStore(database_url=dsn)
        capture=RealSource(db,args.root)
        actual=capture.current(packet.CANDIDATE)
        if actual is None: raise RuntimeError("DP458_ORIGINAL_UNAVAILABLE")
        direct=evaluate_autonomous_publication(actual,None,None)
        journal=SQLiteRunJournal(args.root/"dp413b-v3-actual.sqlite3")
        surface=LiveReadOnlySurface()
        ops=AutonomousOperations(
            capture=capture,challenge=UnverifiedChallenge(),
            first=NoAttestedModel("agent:dp458-first"),
            second=NoAttestedModel("agent:dp458-second"),
            public_surface=surface,journal=journal)
        receipt=PersistentRunner(ops,journal).run(
            packet.CANDIDATE,now=datetime.now(timezone.utc),
            provider_revision="approved-only-single-model-no-challenge-adapter")
        if receipt.disposition!="HOLD" or direct.disposition!="HOLD":
            raise RuntimeError("DP458_UNEXPECTED_PUBLICATION")
        result=dict(status="V3_REAL_CANDIDATE_HOLD",
            source_id=packet.CONTENT,statement_id=packet.CANDIDATE,
            policy_disposition=direct.disposition,
            policy_reasons=list(direct.reason_codes),
            policy_version=direct.policy_version,
            policy_fingerprint=direct.evidence_sha256,
            runner_disposition=receipt.disposition,
            runner_reasons=list(receipt.reason_codes),
            runner_fingerprint=receipt.evidence_sha256,
            journal_events=len(journal.events(packet.CANDIDATE)),
            public_v2_readbacks=surface.reads,
            publication_authorized=False)
        print(json.dumps(result,sort_keys=True)); return 0
    except Exception as e:
        reason=str(e)
        if not reason.startswith(("DP458_","SOURCE_USE_","PRIVATE_CAPTURE_")):
            reason="DP458_V3_OPERATOR_FAILURE"
        print(json.dumps(dict(status="HOLD",reason=reason,publication_authorized=False)))
        return 2
if __name__=="__main__": raise SystemExit(main())
