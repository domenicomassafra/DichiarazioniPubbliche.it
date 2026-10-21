"""DP-239 isolated MiniPC canary: a real licensed excerpt, never public output.

Usage: PYTHONPATH=poc python3 tools/dp239_private_canary.py
Full HTML stays private. SQLite is a disposable replay witness, not the live corpus.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import sqlite3
import sys
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'poc'))
from dichiarazioni_pubbliche.corpus_repository import ContentCaptureRecord, PassageRecord
from dichiarazioni_pubbliche.multilingual_derivation import ImmutableOriginalReadback, build_private_translation
from dichiarazioni_pubbliche.multilingual_ai_review import AITranslationReview
from dichiarazioni_pubbliche.multilingual_ai_review import AITranslationReview
from dichiarazioni_pubbliche.original_source_resolver import ExactSourceLocator
from dichiarazioni_pubbliche.private_capture_rights import SourceFamilyUseGuard
from dichiarazioni_pubbliche.private_multilingual_view import read_private_multilingual_view
from dichiarazioni_pubbliche.rights_registry import PrivateRightsRecord, RightsSubject, rights_subject_fingerprint
from dichiarazioni_pubbliche.wording_contract import WordingType

ATTEST = ROOT / 'docs/ops/attestations/dp239/2026-10-21'
PRIVATE = Path('/tmp/dp239-eu-canary-20261021')
HTML = PRIVATE / 'eu-commission-legal-notice-de.html'


def digest(data: bytes | str) -> str:
    return hashlib.sha256(data.encode('utf-8') if isinstance(data, str) else data).hexdigest()


def source_paragraph(raw: bytes) -> str:
    markup = raw.decode('utf-8', errors='strict')
    start = markup.index('Sofern nicht anders')
    end = markup.index('</p>', start)
    # Versioned parser: remove HTML tags, decode entities, fold NBSP/whitespace.
    return ' '.join(html.unescape(re.sub(r'<[^>]+>', '', markup[start:end])).split())


def italian_from_review_prompt(prompt: str) -> str:
    return prompt.split('draft into Italian, generated independently of the review models; do not improve it while judging fidelity:\n"', 1)[1].split('"\n\nOther', 1)[0]


def durable_insert(db: sqlite3.Connection, key: str, body: bytes) -> None:
    db.execute('INSERT OR IGNORE INTO immutable_blobs(id, data, sha256) VALUES (?, ?, ?)',
               (key, body, digest(body)))
    row = db.execute('SELECT data,sha256 FROM immutable_blobs WHERE id=?', (key,)).fetchone()
    assert row == (body, digest(body)), f'IMMUTABLE_REPLAY_CONFLICT:{key}'


def main() -> None:
    manifest_bytes = (ATTEST / 'manifest.json').read_bytes()
    manifest = json.loads(manifest_bytes)
    db_path = PRIVATE / ('private_canary_' + digest(manifest_bytes)[:16] + '.sqlite3')
    source = HTML.read_bytes()
    assert len(source) == manifest['inputs']['fetched_html_bytes']
    assert digest(source) == manifest['inputs']['fetched_html_sha256']
    original = source_paragraph(source)
    assert digest(original) == manifest['inputs']['source_paragraph_sha256']
    translated = italian_from_review_prompt((ATTEST / 'review-prompt.txt').read_text())
    assert digest(translated) == manifest['inputs']['italian_derivative_sha256']
    assert all(json.loads((ATTEST / (key+'-final.json')).read_text())['response']['translated_meaning_verdict'] == 'FAITHFUL'
               for key in ('rights-sol', 'rights-gemini'))
    assert manifest['gold']['certified'] is False
    assert manifest['source_rights']['public_product_publication'] is False
    db_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as db:
        db.executescript('''
          CREATE TABLE IF NOT EXISTS immutable_blobs (
            id TEXT PRIMARY KEY, data BLOB NOT NULL, sha256 TEXT NOT NULL);
          CREATE TRIGGER IF NOT EXISTS no_update BEFORE UPDATE ON immutable_blobs
          BEGIN SELECT RAISE(ABORT, 'immutable'); END;
          CREATE TRIGGER IF NOT EXISTS no_delete BEFORE DELETE ON immutable_blobs
          BEGIN SELECT RAISE(ABORT, 'immutable'); END;
        ''')
        durable_insert(db, 'html:2026-10-21', source)
        durable_insert(db, 'original:de:1', original.encode('utf-8'))
        durable_insert(db, 'derivative:it:1', translated.encode('utf-8'))
        durable_insert(db, 'rights:private:1', (ATTEST / 'manifest.json').read_bytes())
        durable_insert(db, 'passage:selector:1', json.dumps({
            'encoding':'UTF-8','script':'Latn','language':'de-Latn-DE',
            'start_char':0,'end_char':len(original),'source_html_sha256':digest(source),
            'parser':'html-strip-tags-unescape-fold-spaces-v1'
        },sort_keys=True).encode())
        db.commit()
    with sqlite3.connect(db_path) as db:
        blobs = {k:(v,sha) for k,v,sha in db.execute('SELECT id,data,sha256 FROM immutable_blobs')}
    assert len(blobs)==5
    assert all(digest(payload)==sha for payload,sha in blobs.values())
    assert digest(blobs['html:2026-10-21'][0])==digest(source)
    text=blobs['original:de:1'][0].decode('utf-8')
    it=blobs['derivative:it:1'][0].decode('utf-8')
    pmeta=json.loads(blobs['passage:selector:1'][0])
    assert text==original and it==translated and pmeta['end_char']==len(text)
    body=text.encode('utf-8')
    capture=ContentCaptureRecord(
        id='capture:eu-de:dp239:20261021',content_id='content:eu-de:dp239',
        observed_at='2026-10-21T00:00:00+00:00',
        final_url=manifest['inputs']['source_url'],media_type='text/plain',
        content_sha256=digest(body),retrieval_method='HTML_TEXT_EXTRACT',
        retrieval_version='eu-de:html:'+digest(source),parser_method='NATIVE_DOCUMENT_TEXT',
        parser_version=pmeta['parser'],body_ref='private:sqlite:dp239:original:de:1',
        rights_status='CLEARED',metadata={'parse_status':'SUCCEEDED'},
    )
    passage=PassageRecord(
        id='passage:eu-de:dp239',content_id=capture.content_id,capture_id=capture.id,
        selector_type='TEXT_POSITION',start_char=0,end_char=len(text),private_text=text,
        text_sha256=digest(text),extraction_method=capture.parser_method,
        extraction_version=capture.parser_version,language='de-Latn-DE',
    )
    locator=ExactSourceLocator(
        content_id=capture.content_id,capture_id=capture.id,passage_id=passage.id,
        selector_type=passage.selector_type,quote_start=0,quote_end=len(text),
        quote_sha256=digest(text),capture_sha256=digest(body),
    )
    args=dict(
        locator=locator,passage=passage,capture=capture,source_body=body,
        canonical_text=text,source_text=text,source_language='de-Latn-DE',
        target_language='it-IT',language_origin='SOURCE_DECLARED',
        translated_text=it,source_wording_type=WordingType.VERBATIM_ORIGINAL,
        actor_anchors=(),provider_id='CHATGPT',model_id='gpt-6',
        model_version='2026-10-21',prompt_sha256=digest('dp239-italian-draft-20261021'),
        config_sha256=digest('dp239-draft-config-v1'),derivation_version='eu-private-v1',
    )
    draft=build_private_translation(**args)
    reread=ImmutableOriginalReadback(locator=locator,passage=passage,capture=capture,
                                      source_body=body,canonical_text=text)
    originals={passage.id:reread}
    current={capture.content_id:capture.content_sha256}
    subject=RightsSubject(source_family='EU_COMMISSION_LEGAL_NOTICE',locator_kind='URL',
                          locator_value=capture.final_url,content_id=capture.content_id)
    record=PrivateRightsRecord(
        id='rights:dp239:eu:20261021',subject_fingerprint=rights_subject_fingerprint(subject),
        source_family=subject.source_family,locator_kind=subject.locator_kind,
        locator_value=subject.locator_value,content_id=subject.content_id,
        evidence_id=None,transcript_segment_id=None,canonical_segment_id=None,passage_id=None,
        rights_status='CLEARED',rights_receipt_ref='private:manifest:'+digest(blobs['rights:private:1'][0]),
        permitted_uses=('FETCH','STORE_BODY','PARSE_TEXT','TRANSLATE'),
        attribution_requirements=('CREDIT_EUROPEAN_COMMISSION','LINK_CC_BY_4_0','MARK_MACHINE_TRANSLATION'),
        reviewed_at='2026-10-21T00:00:00+00:00',expires_at='2026-11-20T00:00:00+00:00',
        reviewer_ref='ai:sol6.1+gemini3.8',policy_version='dp239-private-canary-v1',
        record_visibility='PRIVATE',supersedes_id=None,version_state='CURRENT',
    )
    guard=SourceFamilyUseGuard(read_current=lambda _:record,subject=subject,
        rights_record_id=record.id,policy_version=record.policy_version,
        expected_sha256=capture.content_sha256,clock=lambda:datetime.now(timezone.utc))
    common=dict(originals_by_passage=originals,current_versions_by_content=current,
                rights_guard=guard)
    bare=read_private_multilingual_view(passage.id,**common)
    rendered=read_private_multilingual_view(passage.id,translation=draft,**common)
    assert bare.status=='CURRENT_ORIGINAL' and bare.original_text==text
    assert bare.translated_text is None and not bare.public_quote_eligible
    assert rendered.status=='CURRENT_HELD' and rendered.original_text==text
    assert rendered.translated_text==it and rendered.translation_id==draft.id
    assert not rendered.translation_reviewed and not rendered.public_quote_eligible
    # Review identity is read from two independent Pi CLI receipts, not inferred
    # from their self-described model names. Receipt hashes are not signatures.
    results = {key: json.loads((ATTEST / f'{key}-final.json').read_text())
               for key in ('rights-sol', 'rights-gemini')}
    reviews = []
    for key, receipt in results.items():
        reviews.append(AITranslationReview(
            reviewer_id=key, provider_id=receipt['observed_provider'],
            model_id=receipt['observed_model'], model_version='2026-10-21-cli-run',
            prompt_sha256=digest((ATTEST / 'review-prompt.txt').read_bytes()),
            config_sha256=digest('pi-cli:high:'+receipt['requested_model']),
            response_sha256=receipt['response_sha256'], translation_id=draft.id,
            original_quote_sha256=draft.original.quote_sha256,
            source_version_sha256=draft.original.source_version_sha256,
            translated_text_sha256=draft.translated_text_sha256,
            source_language=draft.original.language, target_language=draft.target_language,
            rights_receipt_sha256=digest(manifest_bytes),
            license_ref=manifest['source_rights']['license_url'],
            observed_at=receipt['observed_at'],
            retention_until='2026-11-20T00:00:00+00:00',
            verdict=receipt['response']['translated_meaning_verdict'],
            meaning_risks=tuple(receipt['response']['meaning_risks']),
        ))
    def check_receipt(row: AITranslationReview) -> bool:
        return any(row.reviewer_id == key
                   and row.provider_id == receipt['observed_provider']
                   and row.model_id == receipt['observed_model']
                   and row.response_sha256 == receipt['response_sha256']
                   for key, receipt in results.items())
    def check_rights(row: AITranslationReview) -> bool:
        return (row.rights_receipt_sha256 == digest(manifest_bytes)
                and manifest['source_rights']['status'] == 'CLEARED_FOR_PRIVATE_CANARY_CONDITIONAL'
                and not manifest['source_rights']['public_product_publication'])
    audited = read_private_multilingual_view(
        passage.id, translation=draft, ai_reviews=tuple(reviews),
        ai_review_clock=datetime.now(timezone.utc),
        independent_receipt_check=check_receipt, rights_receipt_check=check_rights,
        **common)
    assert audited.status == 'CURRENT_HELD' and audited.translated_text == it
    assert audited.ai_meaning_assurance_status in ('CONTRACT_ONLY_PRIVATE_HOLD', 'HELD_MEANING_RISK')
    assert not audited.translation_reviewed and not audited.public_quote_eligible
    assert build_private_translation(**args).id==draft.id
    other=build_private_translation(**{**args,'translated_text':it.replace('correttamente', 'in modo corretto')})
    assert other.id!=draft.id and other.original.quote_sha256==draft.original.quote_sha256
    guard.read_current=lambda _:replace(record,rights_status='REVOKED')
    revoked=read_private_multilingual_view(passage.id,translation=draft,**common)
    assert revoked.status=='BLOCKED' and revoked.original_text is None and revoked.translated_text is None
    guard.read_current=lambda _:record
    stale=read_private_multilingual_view(passage.id,translation=draft,
        originals_by_passage=originals,current_versions_by_content={capture.content_id:digest('new')},
        rights_guard=guard)
    assert stale.status=='STALE' and stale.translated_text is None
    guard.clock=lambda:datetime(2026,11,21,tzinfo=timezone.utc)
    expired=read_private_multilingual_view(passage.id,translation=draft,**common)
    assert expired.status=='BLOCKED' and expired.translated_text is None
    print(json.dumps({'status':'PASS_PRIVATE_HELD','database':'PRIVATE_SQLITE_CANARY',
        'raw_html_sha256':digest(source),'original_quote_sha256':digest(text),
        'translated_text_sha256':digest(it),'translation_id':draft.id,
        'passage_id':passage.id,'immutable_rows':len(blobs),
        'original_status':bare.status,'derivative_status':rendered.status,
        'revocation_status':revoked.status,'stale_status':stale.status,
        'expiry_status':expired.status,'translation_reviewed':False,
        'public_quote_eligible':False,'publish_authority':False,
        'ai_meaning_assurance_status':audited.ai_meaning_assurance_status,
        'review_models':sorted([r.model_id for r in reviews])},sort_keys=True))


if __name__=='__main__':
    main()
