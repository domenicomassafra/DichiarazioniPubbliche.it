#!/usr/bin/env python3
"""DP-458 source-specific private EU audiovisual packet. Never authorizes publication."""
import argparse, hashlib, json, os, sys
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"poc"))
from dichiarazioni_pubbliche.capture_authorization import private_capture_rights_guard
from dichiarazioni_pubbliche.capture_pipeline import CaptureBodyStore, CaptureEnrichmentPolicy, CapturePipelineStore, ParseResult, capture_content
from dichiarazioni_pubbliche.corpus_repository import INSERT_STATEMENT_CANDIDATE_SQL_V1
from dichiarazioni_pubbliche.ingestion_relevance import append_ingestion_relevance_authority, replay_current_ingestion_relevance
from dichiarazioni_pubbliche.private_capture_rights import SourceFamilyUseGuard, evaluate_source_use
from dichiarazioni_pubbliche.rights_registry import PrivateRightsRegistryStore, RightsSubject
from dichiarazioni_pubbliche.source_watcher import fetch_bytes

PAGE="https://audiovisual.ec.europa.eu/en/media/video/I-293056"
URL="https://vod.prd.commavservices.eu/16/293056/01a0a916-e603-7622-aa35-8ac303177665/qaa.mp4?filename=I-293056_INT-AUDIO.aac"
VTT="https://s3.eu-west-1.amazonaws.com/avs-media-prd-jobs/I-293056/I293056-INT-REV1.vtt?filename=I-293056_INT-SUBTITLE.vtt"
ROLE="https://ec.europa.eu/commission/presscorner/detail/ov/SPEECH_26_1868"
ORIGINAL_SHA="225b145412687af1ac0fa7a5f03a010541fcf8cd81be3494418f59614ec57593"
VTT_SHA="2de8e201c68ede5735330bfa9f48b87da0ebdddca679f71ffd6be3d0aa58c2de"
TERMS_SHA="1cc14d28ad34c001ac8c1274e903fbffd36cfaebab3551e641b70580fbe32f01"
QUOTE="A stronger, more independent Europe is now emerging."
CONTENT="content:dp458:euavs:I-293056"; SOURCE="source:dp458:euavs"; PERSON="person:dp458:ursula-von-der-leyen"
VARIANT="variant:dp458:I-293056:int-vtt"; SEGMENT="transcript:dp458:I-293056:cue12"
CANONICAL="canonical:dp458:I-293056:cue12"; PASSAGE="passage:dp458:I-293056:cue12"; CANDIDATE="statement:dp458:I-293056:cue12"
FAMILY="EU_AVS_OFFICIAL_SPEECH"; POLICY="dp458-eu-avs-private-media-20261026-v1"; VERSION="dp458-original-source-v2"
USES=("DISCOVER_METADATA","FETCH","STORE_BODY","ASR_MEDIA","PLAYBACK","PARSE_TEXT","RESEARCH_CAPTURE_PRIVATE")
def vtt_timestamp_ms(stamp):
    """Parse original hour:minute:second.millisecond cue without losing minutes."""
    import re
    match=re.fullmatch(r"(\d\d):(\d\d):(\d\d)\.(\d{3})",stamp)
    if not match: raise ValueError("DP458_VTT_TIMECODE_INVALID")
    h,m,sec,ms=map(int,match.groups())
    if m>=60 or sec>=60: raise ValueError("DP458_VTT_TIMECODE_INVALID")
    return ((h*60+m)*60+sec)*1000+ms
START,END,DURATION=vtt_timestamp_ms("00:01:14.669"),vtt_timestamp_ms("00:01:18.940"),332101
def sha(x): return hashlib.sha256(x.encode("utf-8")).hexdigest()
def require(ok,code):
    if not ok: raise RuntimeError("DP458_"+code)
def readjson(store,sql,**kw):
    x=store.run(sql,**kw); return json.loads(x) if x else None
class AudioOnlyParser:
    parser_method="DP458_ORIGINAL_AUDIO_ONLY"; parser_version=VERSION
    def parse(self,fetched):
        return ParseResult(status="FAILED",parser_method=self.parser_method,
                           parser_version=self.parser_version,error_category="INDEPENDENT_TRANSCRIPT_MISSING")
def identities(db):
    db.run("""INSERT INTO source(id,canonical_name,source_type,canonical_url,language,country_code,metadata)
       VALUES (:'id','European Commission Audiovisual Service','OFFICIAL_RECORD',:'url','en','EU',:'meta'::jsonb)
       ON CONFLICT(id) DO NOTHING;""",id=SOURCE,url=PAGE,meta=json.dumps({"producer":"European Parliament","rights":"EU © 2026","private":True}))
    db.run("""INSERT INTO person(id,canonical_name,public_role,country_code,is_public_figure,metadata)
       VALUES (:'id','Ursula von der Leyen','President of the European Commission','EU',true,:'meta'::jsonb)
       ON CONFLICT(id) DO NOTHING;""",id=PERSON,meta=json.dumps({"official_role_url":ROLE}))
    db.run("""INSERT INTO content_item(id,source_id,source_external_id,canonical_url,title,language,
       published_at,duration_ms,content_sha256,rights_status,metadata)
       VALUES (:'id',:'source','I-293056',:'url','SOTEU 2026 — Statement by Ursula von der Leyen',
       'en','2026-09-16T00:00:00Z',:'duration'::bigint,:'sha','UNKNOWN',:'meta'::jsonb)
       ON CONFLICT(id) DO NOTHING;""",id=CONTENT,source=SOURCE,url=URL,duration=DURATION,sha=ORIGINAL_SHA,
       meta=json.dumps({"media_page":PAGE,"vtt_url":VTT,"vtt_sha256":VTT_SHA,"terms_sha256":TERMS_SHA,"private_only":True}))
    obj=readjson(db,"""SELECT json_build_object('content',c.id,'url',c.canonical_url,'sha',c.content_sha256,
       'duration',c.duration_ms,'source',s.canonical_url,'person',p.canonical_name)::text
       FROM content_item c JOIN source s ON c.source_id=s.id CROSS JOIN person p
       WHERE c.id=:'id' AND p.id=:'person';""",id=CONTENT,person=PERSON)
    require(obj and obj["url"]==URL and obj["sha"]==ORIGINAL_SHA and obj["duration"]==DURATION
            and obj["source"]==PAGE and obj["person"]=="Ursula von der Leyen","IDENTITY_CONFLICT")
def rights(db,apply):
    registry=PrivateRightsRegistryStore(database_url=db.database_url)
    subject=RightsSubject(FAMILY,"URL",URL,content_id=CONTENT); current=registry.read_current(subject)
    if current is None and apply:
        now=datetime.now(timezone.utc)
        current=registry.record_rights(subject=subject,policy_version=POLICY,rights_status="CLEARED",
            rights_receipt_ref="eu-avs:I-293056:terms-20261026:"+TERMS_SHA,permitted_uses=USES,
            attribution_requirements=("CC_BY_4_ATTRIBUTION","NO_PUBLIC_MEDIA","PUBLIC_QUOTE_REVIEW_REQUIRED"),
            reviewed_at=now.isoformat(),expires_at=(now+timedelta(days=7)).isoformat(),
            reviewer_ref="agent:dp458-primary-source-rights-review")
    require(current is not None,"RIGHTS_MISSING")
    require(current.rights_status=="CLEARED" and current.version_state=="CURRENT"
            and current.policy_version==POLICY and set(current.permitted_uses)==set(USES),"RIGHTS_CHANGED")
    for use in (item for item in USES if item != "RESEARCH_CAPTURE_PRIVATE"):
        x=evaluate_source_use(current,subject=subject,rights_record_id=current.id,
                              policy_version=POLICY,use=use,now=datetime.now(timezone.utc))
        require(x.permitted,"RIGHTS_"+x.reason_code)
    pub=evaluate_source_use(current,subject=subject,rights_record_id=current.id,
                            policy_version=POLICY,use="EXCERPT_PUBLIC",now=datetime.now(timezone.utc))
    require(not pub.permitted,"UNEXPECTED_PUBLIC_GRANT")
    return registry,subject,current
def capture(db,root,reg,subject,record):
    updated=db.run("""UPDATE content_item SET rights_status='CLEARED'
        WHERE id=:'id' AND canonical_url=:'url' AND rights_status IN ('UNKNOWN','CLEARED')
        RETURNING id;""",id=CONTENT,url=URL)
    require(updated==CONTENT,"CONTENT_RIGHTS_CHANGED")
    replay=replay_current_ingestion_relevance(db.run,content_ref=CONTENT,canonical_url=URL)
    if not replay.allowed:
        require(replay.blocker=="INGESTION_RELEVANCE_MISSING","INGESTION_RELEVANCE_CONFLICT")
        append_ingestion_relevance_authority(db.run,content_ref=CONTENT,canonical_url=URL,
            relevance_reason="OFFICIAL_RECORD",reviewer_ref="agent:dp458-public-statement",
            audit_ref="dp458:"+ORIGINAL_SHA,reviewed_at=datetime.now(timezone.utc).isoformat())
    guard=private_capture_rights_guard(read_current=reg.read_current,rights_record_id=record.id,
        content_id=CONTENT,canonical_url=URL,source_family=FAMILY,
        read_content_state=db.read_operator_capture_content_state)
    use=SourceFamilyUseGuard(read_current=reg.read_current,subject=subject,
        rights_record_id=record.id,policy_version=POLICY,
        expected_sha256=ORIGINAL_SHA,expected_media_type="audio/mp4")
    guard(); use.require("FETCH")
    def fetch_pinned(url,*,max_response_bytes):
        require(url==URL,"FETCH_URL_CHANGED"); guard()
        got=fetch_bytes(url,max_response_bytes=max_response_bytes)
        require(got.final_url==URL and got.status_code==200 and len(got.body)==2985951
                and hashlib.sha256(got.body).hexdigest()==ORIGINAL_SHA,"FETCH_VERSION_CHANGED")
        # Origin labels its verified mono AAC/MP4 as content-type "file".
        return replace(got,media_type="audio/mp4")
    receipt=capture_content(content_id=CONTENT,url=URL,store=db,
        body_store=CaptureBodyStore(root/"capture-bodies"),parser=AudioOnlyParser(),
        fetcher=fetch_pinned,rights_guard=guard,source_use_guard=use,language="en",
        rights_status="CLEARED",retention_class="DURABLE_PRIVATE",
        actor_ref="agent:dp458-primary-media-acquisition",
        enrichment_policy=CaptureEnrichmentPolicy(metadata_enabled=False,archive_enabled=False),
        max_response_bytes=4_000_000)
    require(receipt.primary_capture_id,"CAPTURE_FAILED")
def statements(db):
    meta=json.dumps({"source_vtt":VTT,"vtt_sha256":VTT_SHA,"cue_index":12,
                     "independent_audio_alignment":False,"public_rights":"HOLD"})
    db.run("""INSERT INTO transcript_variant(id,content_id,provider_id,source_kind,
       language,raw_text_sha256,raw_text,is_platform_caption,is_manual_caption,metadata)
       VALUES (:'id',:'content','EU_AVS_OFFICIAL_VTT','PLATFORM_CAPTION',
       'en',:'sha',:'text',true,false,:'meta'::jsonb) ON CONFLICT(id) DO NOTHING;""",
       id=VARIANT,content=CONTENT,sha=sha(QUOTE),text=QUOTE,meta=meta)
    db.run("""INSERT INTO transcript_segment(id,variant_id,segment_index,start_ms,end_ms,text,metadata)
       VALUES (:'id',:'variant',12,:'start'::bigint,:'end'::bigint,:'text',:'meta'::jsonb)
       ON CONFLICT(id) DO NOTHING;""",
       id=SEGMENT,variant=VARIANT,start=START,end=END,text=QUOTE,meta=meta)
    db.run("""INSERT INTO canonical_transcript_segment(id,content_id,segment_index,start_ms,end_ms,
       speaker_person_id,speaker_label,canonical_text,transcript_status,publication_blocked)
       VALUES (:'id',:'content',12,:'start'::bigint,:'end'::bigint,:'person',
       'Ursula von der Leyen',:'text','TRANSCRIPT_UNCERTAIN',true) ON CONFLICT(id) DO NOTHING;""",
       id=CANONICAL,content=CONTENT,start=START,end=END,person=PERSON,text=QUOTE)
    db.run("""INSERT INTO canonical_segment_candidate(canonical_segment_id,transcript_segment_id)
       VALUES (:'canonical',:'segment') ON CONFLICT DO NOTHING;""",canonical=CANONICAL,segment=SEGMENT)
    db.run("""INSERT INTO passage(id,content_id,canonical_segment_id,selector_type,text_sha256,
       private_text,language,extraction_method,extraction_version,metadata)
       VALUES (:'id',:'content',:'canonical','MEDIA_SEGMENT_REF',:'sha',:'text',
       'en','EU_AVS_OFFICIAL_VTT',:'version',:'meta'::jsonb) ON CONFLICT(id) DO NOTHING;""",
       id=PASSAGE,content=CONTENT,canonical=CANONICAL,sha=sha(QUOTE),text=QUOTE,version=VERSION,meta=meta)
    result=db.run(INSERT_STATEMENT_CANDIDATE_SQL_V1,id=CANDIDATE,content_id=CONTENT,
       speaker_person_id=PERSON,statement_text_hash=sha(QUOTE),normalized_statement=QUOTE,
       statement_at="2026-09-16T00:00:00+00:00",attribution_method="OFFICIAL_EUAVS_AND_EC",
       extraction_model="",extraction_version=VERSION,status="HELD",
       metadata=json.dumps({"publication_authorized":False,"acoustic_alignment_verified":False,
                            "public_quote_rights":"HOLD"}),
       passage_ids=json.dumps([PASSAGE]))
    require(result in ("INSERTED","EXISTING"),"STATEMENT_INSERT_FAILED")
def correct_persisted_cue(db):
    """Guarded 00:14->01:14 repair of HELD rows, with explicit v2 audit metadata.

    PostgreSQL permits only one canonical (content_id, segment_index). Since
    neither this segment nor candidate was approved or bound, correct the
    existing private HOLD revision in place while preserving old/new timecodes
    in metadata. Never mutate an ATTESTED binding or APPROVED candidate.
    """
    state=readjson(db,"""SELECT json_build_object(
        'start',c.start_ms,'end',c.end_ms,'transcript',c.transcript_status,
        'blocked',c.publication_blocked,'raw_start',t.start_ms,'raw_end',t.end_ms,
        'candidate_status',s.status,'hash',s.statement_text_hash,
        'binding_count',(SELECT count(*) FROM media_capture_segment_binding b
            WHERE b.canonical_segment_id=c.id))::text
        FROM canonical_transcript_segment c
        JOIN canonical_segment_candidate link ON link.canonical_segment_id=c.id
        JOIN transcript_segment t ON t.id=link.transcript_segment_id
        JOIN statement_candidate s ON s.content_id=c.content_id
        WHERE c.id=:'canonical' AND t.id=:'segment' AND s.id=:'candidate';""",
        canonical=CANONICAL,segment=SEGMENT,candidate=CANDIDATE)
    require(state and state["hash"]==sha(QUOTE)
            and state["candidate_status"]=="HELD"
            and state["transcript"]=="TRANSCRIPT_UNCERTAIN"
            and state["blocked"] is True and state["binding_count"]==0,
            "CORRECTION_NOT_PRIVATE_HELD")
    current=(state["start"],state["end"],state["raw_start"],state["raw_end"])
    require(current in ((14669,18940,14669,18940),
                        (START,END,START,END)), "TIMING_STATE_CONFLICT")
    if current==(14669,18940,14669,18940):
        # No truth change: original VTT cue #12 is 00:01:14, not 00:00:14.
        updated=db.run("""UPDATE canonical_transcript_segment
           SET start_ms=:'start'::bigint,end_ms=:'end'::bigint
           WHERE id=:'id' AND start_ms=14669 AND end_ms=18940
             AND transcript_status='TRANSCRIPT_UNCERTAIN'
             AND publication_blocked=true AND NOT EXISTS (
               SELECT 1 FROM media_capture_segment_binding b
               WHERE b.canonical_segment_id=:'id') RETURNING id;""",
           id=CANONICAL,start=START,end=END)
        require(updated==CANONICAL,"CANONICAL_TIMING_CAS_FAILED")
        updated=db.run("""UPDATE transcript_segment SET
            start_ms=:'start'::bigint,end_ms=:'end'::bigint
            WHERE id=:'id' AND start_ms=14669 AND end_ms=18940
            AND segment_index=12 RETURNING id;""",
            id=SEGMENT,start=START,end=END)
        require(updated==SEGMENT,"VTT_TIMING_CAS_FAILED")
    audit=json.dumps({"reason":"DP458_VTT_CUE12_MINUTE_CORRECTION",
       "original_start_ms":14669,"original_end_ms":18940,
       "corrected_start_ms":START,"corrected_end_ms":END,
       "vtt_sha256":VTT_SHA,
       "independent_acoustic_alignment":"HOLD"})
    # This updates the versioned metadata, not public approval or status.
    db.run("""UPDATE statement_candidate SET extraction_version=:'version',
        metadata=coalesce(metadata,'{}'::jsonb) ||
          jsonb_build_object('timing_correction_v2',:'audit'::jsonb)
        WHERE id=:'id' AND status='HELD' AND statement_text_hash=:'sha';""",
        version=VERSION,audit=audit,id=CANDIDATE,sha=sha(QUOTE))
    db.run("""UPDATE passage SET extraction_version=:'version',
        metadata=coalesce(metadata,'{}'::jsonb) ||
          jsonb_build_object('timing_correction_v2',:'audit'::jsonb)
        WHERE id=:'id' AND text_sha256=:'sha';""",
        version=VERSION,audit=audit,id=PASSAGE,sha=sha(QUOTE))
    db.run("""UPDATE transcript_segment SET
        metadata=coalesce(metadata,'{}'::jsonb) ||
          jsonb_build_object('timing_correction_v2',:'audit'::jsonb)
        WHERE id=:'id' AND start_ms=:'start'::bigint AND end_ms=:'end'::bigint;""",
        audit=audit,id=SEGMENT,start=START,end=END)

def verify(db,root):
    reg,subject,record=rights(db,False)
    captured=db.find_capture(CONTENT,ORIGINAL_SHA)
    require(captured and captured.get("body_ref"),"CAPTURE_READBACK_MISSING")
    body=CaptureBodyStore.open_existing_readonly(root/"capture-bodies").read(
         captured["body_ref"],expected_sha256=ORIGINAL_SHA)
    require(hashlib.sha256(body).hexdigest()==ORIGINAL_SHA,"ORIGINAL_BODY_CHANGED")
    row=readjson(db,"""SELECT json_build_object('quote',p.private_text,'sha',p.text_sha256,
       'start',cs.start_ms,'end',cs.end_ms,'status',cs.transcript_status,
       'blocked',cs.publication_blocked,'candidate',s.id,'candidate_status',s.status,\n       'candidate_version',s.extraction_version,'raw_start',t.start_ms,'raw_end',t.end_ms)::text
       FROM passage p JOIN canonical_transcript_segment cs ON cs.id=p.canonical_segment_id
       JOIN canonical_segment_candidate cc ON cc.canonical_segment_id=cs.id
       JOIN transcript_segment t ON t.id=cc.transcript_segment_id AND t.id=:'segment'
       JOIN statement_candidate_passage link ON link.passage_id=p.id
       JOIN statement_candidate s ON s.id=link.statement_candidate_id
       WHERE p.id=:'passage' AND s.id=:'candidate';""",passage=PASSAGE,candidate=CANDIDATE,segment=SEGMENT)
    require(row and row["quote"]==QUOTE and row["sha"]==sha(QUOTE)
           and row["start"]==START and row["end"]==END
           and row["raw_start"]==START and row["raw_end"]==END
           and row["candidate_version"]==VERSION
           and row["status"]=="TRANSCRIPT_UNCERTAIN" and row["blocked"]
           and row["candidate_status"]=="HELD","STATEMENT_READBACK_FAILED")
    count=db.run("""SELECT count(*) FROM media_capture_segment_binding
        WHERE content_id=:'content' AND canonical_segment_id=:'segment';""",
        content=CONTENT,segment=CANONICAL)
    require(count=="0","UNVERIFIED_BINDING_PRESENT")
    return dict(status="VERIFIED_PRIVATE_HOLD",source_id=SOURCE,content_id=CONTENT,
        capture_id=captured["id"],rights_id=record.id,rights_expires_at=record.expires_at,
        source_sha256=ORIGINAL_SHA,vtt_sha256=VTT_SHA,statement_id=CANDIDATE,
        statement_sha256=sha(QUOTE),segment_id=CANONICAL,passage_id=PASSAGE,
        start_ms=START,end_ms=END,binding_count=int(count),
        private_uses=sorted(record.permitted_uses),public_quote_rights="HOLD",
        independent_alignment="HOLD",publication_authorized=False)
def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("--apply",action="store_true"); p.add_argument("--correct-timing",action="store_true")
    p.add_argument("--root",type=Path,default=Path("~/.local/share/dichiarazioni-pubbliche/dp458").expanduser())
    a=p.parse_args(); dsn=os.environ.get("DICHIARAZIONI_PUBBLICHE_DATABASE_URL")
    if not dsn: p.error("DICHIARAZIONI_PUBBLICHE_DATABASE_URL missing")
    try:
        db=CapturePipelineStore(database_url=dsn)
        if a.apply:
            a.root.mkdir(mode=0o700,parents=True,exist_ok=True)
            require(not a.root.is_symlink() and a.root.stat().st_mode & 0o077==0,"UNSAFE_ROOT")
            identities(db); reg,subject,record=rights(db,True)
            capture(db,a.root,reg,subject,record); statements(db)
            correct_persisted_cue(db)
        if a.correct_timing:
            # No fetch, no new Capture or rights: append corrected cue revision.
            rights(db,False)
            original=db.find_capture(CONTENT,ORIGINAL_SHA)
            require(original and original.get("body_ref"),"ORIGINAL_NOT_PERSISTED")
            CaptureBodyStore.open_existing_readonly(a.root/"capture-bodies").read(
                original["body_ref"],expected_sha256=ORIGINAL_SHA)
            correct_persisted_cue(db)
        print(json.dumps(verify(db,a.root),sort_keys=True)); return 0
    except Exception as e:
        code=str(e)
        if not code.startswith(("DP458_","SOURCE_USE_","PRIVATE_CAPTURE_",
                                "INGESTION_","CAPTURE_")): code="DP458_OPERATOR_FAILURE"
        print(json.dumps({"status":"HOLD","reason":code,"publication_authorized":False}))
        return 2
if __name__=="__main__": raise SystemExit(main())
