"""Offline synthetic DP-233 parliamentary source fixture.

Authored for repository tests only; no network/provider data is embedded here.
"""

from __future__ import annotations

import copy


_RECORDS = [
    {
        "chamber": "CAMERA",
        "sitting": {
            "id": "camera:sitting:2026-10-05:101",
            "date": "2026-10-05",
            "agenda_item_id": "camera:agenda:2026-10-05:tax",
            "agenda_label": "Interrogazioni a risposta immediata",
        },
        "speaker": {
            "id": "camera:deputy:123",
            "name": "Mario Rossi",
            "role": "Deputato",
        },
        "statement": {
            "id": "camera:statement:2026-10-05:101:1",
            "speaker_id": "camera:deputy:123",
            "date": "2026-10-05",
            "text": "Non aumenteremo le tasse.",
            "start_char": 13,
            "end_char": 38,
        },
        "transcript": {
            "url": "https://www.camera.it/leg19/resoconto/101",
            "source_version": "camera-resoconto-101-v1",
            "text": "Mario Rossi: Non aumenteremo le tasse. Anna Bianchi: Chiedo la parola.",
        },
        "video": {
            "url": "https://webtv.camera.it/evento/101",
            "source_version": "camera-webtv-101-v1",
            "start_ms": 120000,
            "end_ms": 127500,
        },
        "transcript_variant_refs": [
            "platform-caption:camera-101",
            "asr:camera-101:whisper",
        ],
        "platform_author": "Account Camera Deputati",
    },
    {
        "chamber": "CAMERA",
        "sitting": {
            "id": "camera:sitting:2026-10-05:101",
            "date": "2026-10-05",
            "agenda_item_id": "camera:agenda:2026-10-05:tax",
            "agenda_label": "Interrogazioni a risposta immediata",
        },
        "speaker": {
            "id": "camera:deputy:456",
            "name": "Anna Bianchi",
            "role": "Deputata",
        },
        "statement": {
            "id": "camera:statement:2026-10-05:101:2",
            "speaker_id": "camera:deputy:456",
            "date": "2026-10-05",
            "text": "Chiedo la parola.",
            "start_char": 53,
            "end_char": 70,
        },
        "transcript": {
            "url": "https://www.camera.it/leg19/resoconto/101",
            "source_version": "camera-resoconto-101-v1",
            "text": "Mario Rossi: Non aumenteremo le tasse. Anna Bianchi: Chiedo la parola.",
        },
        "video": {
            "url": "https://webtv.camera.it/evento/101",
            "source_version": "camera-webtv-101-v1",
            "start_ms": 128000,
            "end_ms": 132000,
        },
        "transcript_variant_refs": ["platform-caption:camera-101"],
        "platform_author": "Mario Rossi Fan Channel",
    },
]


def parliamentary_official_fixture_records():
    return copy.deepcopy(_RECORDS)
