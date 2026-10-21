"""DP-239 reproducible, non-authoritative DE->IT adversarial risk benchmark.

Frozen inputs and three independent AI judgments live in docs/ops/attestations.
All examples are invented. Output contains only risk codes and measurements.
"""
from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'poc'))

from dichiarazioni_pubbliche.multilingual_derivation import ActorAnchor, build_private_translation
from dichiarazioni_pubbliche.multilingual_gold import (
    TranslationGoldCase, TranslationGoldManifest, TranslationRiskPrediction,
    evaluate_translation_gold, manifest_hash,
)
from dichiarazioni_pubbliche.wording_contract import WordingType
from tests.test_dp239_multilingual_derivation import written_fixture

ATTEST = ROOT / 'docs/ops/attestations/dp239/2026-10-21'


def digest(value: bytes | str) -> str:
    return hashlib.sha256(value.encode('utf-8') if isinstance(value, str) else value).hexdigest()


def main() -> None:
    dataset_bytes = (ATTEST / 'gold-cases-v1.json').read_bytes()
    dataset = json.loads(dataset_bytes)
    assert dataset['schema'] == 'dp239-adjudicated-de-it-gold-v1'
    cases = dataset['cases']
    assert len(cases) == 8 and [r['case_id'] for r in cases] == [f'C{i}' for i in range(8)]
    receipts = {k: json.loads((ATTEST / f'{k}-final.json').read_text())
                for k in ('gold-sol', 'gold-gemini', 'adjudication')}
    for k in receipts:
        assert digest((ATTEST / f'{k}-final.json').read_bytes()) == dataset[
            {'gold-sol':'sol_receipt_sha256', 'gold-gemini':'gemini_receipt_sha256',
             'adjudication':'adjudicator_receipt_sha256'}[k]]
    observed = {(r['observed_provider'], r['observed_model']) for r in receipts.values()}
    assert len(observed) == 3 and {r['observed_model'] for r in receipts.values()} == {
        'gpt-6.1-sol', 'gemini-3.8-flash-tiered', 'claude-sonnet-4-6'}
    adjudicator = {row['id']: row for row in receipts['adjudication']['response']['verdicts']}
    assert len(adjudicator) == len(cases)
    assert all(adjudicator[row['case_id']]['semantic_state'] == row['semantic_state']
               and sorted(adjudicator[row['case_id']]['expected_alerts']) == row['expected_alerts']
               for row in cases)

    gold_rows, predictions = [], []
    source_rights_sha = digest((ATTEST / 'manifest.json').read_bytes())
    adjudication_sha = receipts['adjudication']['response_sha256']
    for case in cases:
        fixture = written_fixture(case['original_de'])
        fixture['translated_text'] = case['translation_it']
        fixture['actor_anchors'] = (
            ActorAnchor('person:anna', 'Anna'), ActorAnchor('person:bruno', 'Bruno')
        ) if case['case_id'] == 'C4' else ()
        draft = build_private_translation(**fixture)
        gold_rows.append(TranslationGoldCase(
            case_id=case['case_id'], passage_id=draft.original.passage_id,
            original_quote_sha256=draft.original.quote_sha256,
            source_version_sha256=draft.original.source_version_sha256,
            translation_sha256=draft.translated_text_sha256,
            original_language=draft.original.language,
            target_language=draft.target_language,
            original_wording_type=WordingType.VERBATIM_ORIGINAL,
            expected_alerts=tuple(case['expected_alerts']),
            semantic_state=case['semantic_state'], speaker_person_id=None,
            reported_author_id=None, endorsement='UNKNOWN',
            source_rights_receipt_sha256=source_rights_sha,
            adjudication_receipt_sha256=adjudication_sha,
            annotator_ids=('codex/gpt-6.1-sol', 'antigravity/gemini-3.8-flash-tiered'),
            adjudicator_id='antigravity/claude-sonnet-4-6',
            reference_version='dp239-adjudicated-de-it-gold-v1',
        ))
        predictions.append(TranslationRiskPrediction(case_id=case['case_id'], translation=draft))
        assert draft.method == 'MACHINE' and draft.status == 'HELD' and not draft.public_quote_eligible
    pending = TranslationGoldManifest(generator_id='chatgpt:translation-author', model_id='gpt-6',
                                     cases=tuple(gold_rows), manifest_sha256=digest('pending'))
    frozen = replace(pending, manifest_sha256=manifest_hash(pending))
    # Admission confirms the independent CLI receipts in this Git checkout,
    # not legal title, model correctness, digital signatures or public release.
    allowed = {case.case_id: case for case in gold_rows}
    report = evaluate_translation_gold(frozen, tuple(predictions),
        external_attestation_check=lambda row: allowed.get(row.case_id) == row)
    assert report.status == 'CONTRACT_ONLY_PRIVATE_HOLD'
    assert report.externally_admitted_cases == 8 and report.matched_predictions == 8
    assert not report.release_eligible and not report.publication_authority
    print(json.dumps({
        'status': report.status, 'source': dataset['source'],
        'dataset_sha256': digest(dataset_bytes), 'manifest_sha256': frozen.manifest_sha256,
        'cases': report.case_count, 'reviewed_cases': report.externally_admitted_cases,
        'disagreements_adjudicated': 2, 'held_cases': sum(
            p.translation.status == 'HELD' for p in predictions),
        'critical_alerts_detected_lexically': report.detected_critical_alerts,
        'critical_alerts_missed_lexically': report.missed_critical_alerts,
        'critical_alerts_unexpected_lexically': report.unexpected_critical_alerts,
        'risk_alert_recall': report.risk_alert_recall,
        'public_release_eligible': report.release_eligible,
        'publication_authority': report.publication_authority,
    }, sort_keys=True))


if __name__ == '__main__':
    main()
