"""DP-438 isolated Person v3 approval/chronology boundary; synthetic data only."""

from __future__ import annotations

import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))

from dichiarazioni_pubbliche.public_person_v3 import (  # noqa: E402
    PUBLIC_PERSON_SCHEMA_VERSION,
    build_public_people_v3,
    get_public_person_v3,
    person_snapshot_sha256,
    role_snapshot_sha256,
)
from dichiarazioni_pubbliche.public_schema import (  # noqa: E402
    PUBLIC_SCHEMA_VERSION,
    PUBLIC_STATEMENT_SCHEMA_VERSION,
    PublicSchemaValidationError,
    projection_dataset_sha256,
    validate_public_bundle,
)


def sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def person(person_id: str = "person:one", *, slug: str = "persona-uno", name: str = "Alex Demo") -> dict:
    return {
        "person_id": person_id, "slug": slug, "display_name": name,
        "disambiguator": None, "entity_version": "person-version:1",
        "profile_scope": "PUBLIC_ROLE", "privacy_policy_ref": "privacy-policy-v1",
        "sensitive_policy_ref": "sensitive-policy-v1",
    }


def identity(p: dict, *, revision: int = 1, status: str = "APPROVED") -> dict:
    return {
        "person_id": p["person_id"], "revision": revision, "status": status,
        "person_sha256": person_snapshot_sha256(p),
        "identity_review_id": f"identity:{p['person_id']}:{revision}",
        "publication_review_id": f"publication:{p['person_id']}:{revision}",
        "privacy_review_status": "APPROVED", "sensitive_review_status": "APPROVED",
        "privacy_policy_ref": p["privacy_policy_ref"],
        "sensitive_policy_ref": p["sensitive_policy_ref"],
    }


def role(role_id: str = "role:one", *, from_date: str = "2023-01-01", to_date: str | None = "2024-12-31") -> dict:
    return {
        "role_id": role_id, "person_id": "person:one", "role_version": "role-version:1",
        "label": "Delegato", "organization": "Ente dimostrativo",
        "valid_from": from_date, "valid_to": to_date,
        "source_ref": f"source:{role_id}",
        "source_url": "https://example.test/registro",
    }


def role_review(r: dict, *, revision: int = 1, status: str = "APPROVED") -> dict:
    return {
        "role_id": r["role_id"], "person_id": r["person_id"], "revision": revision,
        "status": status, "role_sha256": role_snapshot_sha256(r),
        "review_event_id": f"role-review:{r['role_id']}:{revision}",
    }


def statement(*, person_id: str = "person:one", statement_id: str = "statement:one", when: str = "2024-02-01", speech_act: str = "OPINION", endorsed: bool = True) -> dict:
    quote = "Una frase dimostrativa."
    return {
        "statement_id": statement_id, "version_id": f"version:{statement_id}",
        "person_id": person_id, "speaker_name": "Alex Demo",
        "content_id": f"content:{statement_id}", "source_title": "Documento di Alex Demo",
        "source_url": "https://example.test/dichiarazione",
        "source_version": f"source-version:{statement_id}",
        "source_sha256": sha("Sorgente dimostrativa"), "original_text": quote,
        "quote_sha256": sha(quote), "language": "it", "statement_date": when,
        "source_kind": "WRITTEN", "locator": {"start_char": 10, "end_char": 10 + len(quote)},
        "speech_act": speech_act, "endorsed": endorsed,
        "review_provenance": {
            key: f"review:{key}:{statement_id}"
            for key in ("rights", "attribution", "context", "wording", "publication")
        },
        "finding_id": None, "summary": None, "translation": None,
    }


def bundle(statements: list[dict] | None = None, *, v2: bool = False) -> dict:
    b = {
        "schema_version": PUBLIC_SCHEMA_VERSION if v2 else PUBLIC_STATEMENT_SCHEMA_VERSION,
        "generated_at": "2026-10-11T00:00:00+00:00",
        "dataset_sha256": "", "dossier_count": 0, "omitted_count": 0,
        "dossiers": [], "topics": [], "contents": [],
        "methodology": {
            "claim_level_only": True, "aggregate_person_score": False,
            **({} if v2 else {"statement_publication_requires_independent_gates": True}),
        },
    }
    if not v2:
        b["statements"] = statements or []
    b["dataset_sha256"] = projection_dataset_sha256(b)
    validate_public_bundle(b, allow_statement_v3=not v2)
    return b


def project(
    people: list[dict] | None = None, identities: list[dict] | None = None,
    roles: list[dict] | None = None, reviews: list[dict] | None = None,
    *, statements: list[dict] | None = None, public_bundle: dict | None = None,
) -> dict:
    p = person()
    return build_public_people_v3(
        [p] if people is None else people,
        [identity(p)] if identities is None else identities,
        [] if roles is None else roles,
        [] if reviews is None else reviews,
        public_bundle=bundle(statements) if public_bundle is None else public_bundle,
        allow_public_person_v3=True,
    )


class PublicPersonV3Tests(unittest.TestCase):
    def test_zero_statements_only_after_independent_identity_and_publication_review(self):
        built = project()
        self.assertEqual(built["schema_version"], PUBLIC_PERSON_SCHEMA_VERSION)
        record = get_public_person_v3(built, "person:one")
        self.assertEqual(record["route"], "/persone/persona-uno/")
        self.assertEqual(record["slug"], "persona-uno")
        self.assertEqual(record["status"], "PUBLISHED")
        self.assertEqual(record["statements"], [])
        self.assertEqual(record["roles"], [])
        self.assertIs(get_public_person_v3(built, "persona-uno"), record)
        self.assertEqual(built, project())
        self.assertEqual(built["dataset_sha256"], sha(json.dumps(
            built["people"], ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        )))
        for text in ("identity:1", "publication:1", "privacy-policy-v1", "sensitive-policy-v1"):
            self.assertNotIn(text, json.dumps(built))

    def test_opinion_without_finding_has_literal_and_source_with_emission_date(self):
        public_statement = statement()
        built = project(statements=[public_statement])
        row = built["people"][0]["statements"][0]
        self.assertEqual(row["statement_id"], "statement:one")
        self.assertEqual(row["statement_date"], "2024-02-01")
        self.assertEqual(row["original_text"], public_statement["original_text"])
        self.assertEqual(row["source_url"], public_statement["source_url"])
        self.assertIsNone(row["finding_id"])
        self.assertNotIn("verified_at", row)
        self.assertNotIn("publication_date", row)
        self.assertNotIn("verdict", json.dumps(built))

    def test_name_in_source_title_or_reported_quote_never_creates_endorsed_membership(self):
        other_person = statement(person_id="person:other")
        reported = statement(statement_id="statement:reported", speech_act="REPORTED_QUOTE", endorsed=False)
        not_endorsed = statement(statement_id="statement:critical", speech_act="CRITICISM", endorsed=False)
        built = project(statements=[other_person, reported, not_endorsed])
        self.assertEqual(built["people"][0]["statements"], [])

    def test_source_time_roles_and_ambiguous_overlap_never_become_current_office(self):
        first = role()
        later = role("role:second", from_date="2025-01-01", to_date=None)
        later["label"] = "Portavoce"
        early_statement = statement(when="2024-02-01")
        late_statement = statement(statement_id="statement:two", when="2025-05-01")
        outside_statement = statement(statement_id="statement:three", when="2022-12-01")
        built = project(roles=[first, later], reviews=[role_review(first), role_review(later)],
                        statements=[early_statement, late_statement, outside_statement])
        memberships = {s["statement_id"]: s for s in built["people"][0]["statements"]}
        self.assertEqual(memberships["statement:one"]["role_at_statement"]["label"], "Delegato")
        self.assertEqual(memberships["statement:two"]["role_at_statement"]["label"], "Portavoce")
        self.assertIsNone(memberships["statement:three"]["role_at_statement"])
        self.assertNotIn("current_role", json.dumps(built))

        overlapping = role("role:overlap", from_date="2024-01-01", to_date="2024-05-01")
        overlapping["label"] = "Altro incarico"
        ambiguous = project(roles=[first, overlapping],
                            reviews=[role_review(first), role_review(overlapping)],
                            statements=[early_statement])
        self.assertIsNone(ambiguous["people"][0]["statements"][0]["role_at_statement"])

    def test_revocation_wrong_digest_and_policy_hold_do_not_leak_person(self):
        p = person()
        cases = [
            [],
            [identity(p, status="HELD")],
            [identity(p), identity(p, revision=2, status="REVOKED")],
            [identity(p), identity(p, revision=2, status="HELD")],
        ]
        mismatched = identity(p)
        mismatched["person_sha256"] = sha("modified")
        cases.append([mismatched])
        privacy = identity(p)
        privacy["privacy_review_status"] = "HELD"
        cases.append([privacy])
        invalid_review = identity(p)
        invalid_review["publication_review_id"] = invalid_review["identity_review_id"]
        cases.append([invalid_review])
        for decisions in cases:
            with self.subTest(decisions=decisions):
                result = project(identities=decisions, statements=[statement()])
                self.assertEqual(result["people"], [])
                self.assertIsNone(get_public_person_v3(result, p["person_id"]))
                self.assertIsNone(get_public_person_v3(result, "unknown:person"))

    def test_role_revocation_or_changed_source_cannot_retain_stale_role(self):
        r = role()
        revoked = [role_review(r), role_review(r, revision=2, status="REVOKED")]
        result = project(roles=[r], reviews=revoked, statements=[statement()])
        self.assertEqual(result["people"][0]["roles"], [])
        self.assertIsNone(result["people"][0]["statements"][0]["role_at_statement"])
        damaged = copy.deepcopy(r)
        damaged["source_url"] = "https://example.test/changed"
        result = project(roles=[damaged], reviews=[role_review(r)])
        self.assertEqual(result["people"][0]["roles"], [])
        unproven = copy.deepcopy(r)
        unproven["source_url"] = "http://example.test/insecure"
        result = project(roles=[unproven], reviews=[role_review(r)])
        self.assertEqual(result["people"][0]["roles"], [])

    def test_two_same_name_identities_multilingual_statements_and_route_collision(self):
        one = person()
        one["disambiguator"] = "Organizzazione A"
        two = person("person:two", slug="persona-due")
        two["disambiguator"] = "Organizzazione B"
        translated = statement(person_id="person:two", statement_id="statement:two")
        translated["language"] = "en"
        built = project(people=[one, two], identities=[identity(one), identity(two)],
                        statements=[statement(), translated])
        self.assertEqual(len(built["people"]), 2)
        self.assertEqual({p["person_id"] for p in built["people"]}, {"person:one", "person:two"})
        self.assertEqual(get_public_person_v3(built, "persona-due")["statements"][0]["language"], "en")

        two["slug"] = one["slug"]
        collision = project(people=[one, two], identities=[identity(one), identity(two)])
        self.assertEqual(collision["people"], [])
        two["slug"] = "persona-due"
        two["disambiguator"] = None
        no_disambiguator = project(people=[one, two], identities=[identity(one), identity(two)])
        self.assertEqual(no_disambiguator["people"], [])

    def test_duplicate_review_event_is_not_independent_approval(self):
        first = person()
        second = person("person:two", slug="persona-due", name="Persona Due")
        reused = identity(second)
        reused["identity_review_id"] = identity(first)["identity_review_id"]
        result = project(people=[first, second], identities=[identity(first), reused])
        self.assertEqual(result["people"], [])
        a = role()
        b = role("role:second", from_date="2025-01-01", to_date=None)
        approval_b = role_review(b)
        approval_b["review_event_id"] = role_review(a)["review_event_id"]
        result = project(roles=[a, b], reviews=[role_review(a), approval_b])
        self.assertEqual(result["people"][0]["roles"], [])
        colliding_older = identity(first, revision=2)
        colliding_older["identity_review_id"] = identity(first)["identity_review_id"]
        held = project(people=[first], identities=[identity(first), colliding_older])
        self.assertEqual(held["people"], [])
        cross_domain = role_review(a)
        cross_domain["review_event_id"] = identity(first)["publication_review_id"]
        held_role = project(roles=[a], reviews=[cross_domain])
        self.assertEqual(held_role["people"][0]["roles"], [])

    def test_private_changes_without_new_approved_decision_are_observably_ignored(self):
        p = person()
        accepted = identity(p)
        baseline = project(people=[p], identities=[accepted])
        private = person("person:secret", slug="persona-segreta", name="Anonimo segreto")
        changed_private = copy.deepcopy(private)
        changed_private["display_name"] = "Privato aggiornato"
        self.assertEqual(baseline, project(people=[p, private], identities=[accepted]))
        self.assertEqual(baseline, project(people=[p, changed_private], identities=[accepted]))
        self.assertEqual(baseline, project(people=[p, private], identities=[accepted, identity(private, status="HELD")]))
        modified = copy.deepcopy(p)
        modified["display_name"] = "Alterazione senza nuova revisione"
        self.assertEqual(project(people=[modified], identities=[accepted])["people"], [])
        self.assertEqual(project(people=[p, p], identities=[accepted])["people"], [])

    def test_v3_is_explicit_and_requires_current_validated_bundle(self):
        with self.assertRaisesRegex(ValueError, "explicit opt-in"):
            build_public_people_v3([], [], [], [], public_bundle=bundle())
        with self.assertRaisesRegex(ValueError, "Statement v3"):
            project(public_bundle=bundle(v2=True))
        invalid = bundle([statement()])
        invalid["statements"][0]["original_text"] = "Manomesso"
        with self.assertRaises(PublicSchemaValidationError):
            project(public_bundle=invalid)
        invalid = bundle([statement()])
        invalid["dataset_sha256"] = sha("invalid")
        with self.assertRaises(PublicSchemaValidationError):
            project(public_bundle=invalid)


if __name__ == "__main__":
    unittest.main()
