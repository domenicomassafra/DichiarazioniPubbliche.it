import json
import re
import sys
import unittest
import unicodedata
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

import dichiarazioni_pubbliche.correction_propagation as propagation  # noqa: E402
from dichiarazioni_pubbliche.correction_propagation import (  # noqa: E402
    ROUTE_STATIC_MANIFEST_VERSION,
    check_correction_propagation,
)


FIXTURE = ROOT / "tests" / "fixtures" / "correction-propagation-v1.json"


def scenarios():
    cases = json.loads(FIXTURE.read_text())["scenarios"]
    # Legacy compact scenarios predate DP-409's full v1 record fields. Fill
    # synthetic public-contract fields in the input fixtures, not in the
    # checker, so missing fields in an actual search index ALWAYS fail closed.
    for case in cases:
        for key in ("old_projection", "new_projection"):
            projection = case[key]
            for dossier in projection["dossiers"]:
                dossier.setdefault("claim_type", "QUOTE_ATTRIBUTION")
                dossier["speaker"].setdefault("public_roles", [])
                dossier["source"].setdefault("published_at", None)
                dossier["finding"].setdefault("assessment", "SUPPORTED")
                dossier["finding"].setdefault("published_at", None)
                dossier.setdefault("corrections", [])
                dossier.setdefault("rights_of_reply", [])
            for topic in projection["topics"]:
                topic.setdefault("slug", _slug(topic["topic_id"]))
                topic.setdefault("scope_text", None)
            for content in projection["contents"]:
                content.setdefault("slug", _slug(content["content_id"]))
                content.setdefault("content_kind", "WRITTEN")
                content.setdefault("published_at", None)
    return cases


def _slug(value):
    normalized = unicodedata.normalize("NFKD", value.lower())
    unmarked = "".join(ch for ch in normalized if not unicodedata.category(ch).startswith("M"))
    return re.sub(r"[^a-z0-9]+", "-", unmarked).strip("-")


def _terms(values):
    out = []
    for raw in values:
        term = str(raw).strip() if raw is not None else ""
        if term and term not in out:
            out.append(term)
    return out


def _record(kind, identifier, title, subtitle, published_at, assessment,
            route, primary, secondary, *, corrections=False, replies=False,
            wording=None, source_wording=None, **facets):
    return {
        "id": identifier, "kind": kind, "title": title, "subtitle": subtitle,
        "published_at": published_at, "assessment": assessment, "route": route,
        "has_corrections": corrections, "has_rights_of_reply": replies,
        "wording_type": wording, "source_wording_type": source_wording,
        "direct_quote_eligible": False,
        "primary_terms": _terms(primary), "secondary_terms": _terms(secondary),
        **facets,
    }


def search_index(projection):
    """Faithful synthetic DP-409 v1 records; independent of the DP-431 checker."""
    state = propagation._projection_state(projection)
    records = []
    people = set()
    fallback_contents = set()
    topics_by_finding = {}
    for topic in projection.get("topics", []):
        for membership in topic["memberships"]:
            for fid in membership["finding_ids"]:
                topics_by_finding.setdefault(fid, set()).add(topic["topic_id"])
    for dossier in projection["dossiers"]:
        fid, speaker, source, finding = (
            dossier["finding_id"], dossier["speaker"], dossier["source"], dossier["finding"]
        )
        roles = [
            value for role in speaker.get("public_roles", [])
            for value in (role["role"], role.get("organization_name"))
        ]
        records.append(_record(
            "finding", fid, dossier["claim"], f'{speaker["name"]} · {source["title"]}',
            finding.get("published_at") if finding.get("published_at") is not None
            else source.get("published_at"),
            finding["assessment"], f'/dichiarazioni/{_slug(fid)}/',
            [dossier["claim"]],
            [speaker["name"], source["title"], dossier["claim_type"], finding["assessment"], *roles],
            corrections=bool(dossier.get("corrections")), replies=bool(dossier.get("rights_of_reply")),
            wording="PARAPHRASE",
            source_wording=(dossier.get("wording") or {}).get("source_occurrence", {}).get("wording_type"),
            person_id=speaker["id"], topic_ids=sorted(topics_by_finding.get(fid, ())),
        ))
        if speaker["id"] not in people:
            people.add(speaker["id"])
            records.append(_record(
                "person", speaker["id"], speaker["name"], " · ".join(_terms(roles)),
                None, None, f'/persone/{_slug(speaker["id"])}/',
                [speaker["name"]], roles,
            ))
        if "contents" not in projection and source["content_id"] not in fallback_contents:
            fallback_contents.add(source["content_id"])
            records.append(_record(
                "content", source["content_id"], source["title"], "Fonte pubblica",
                source.get("published_at"), None,
                f'/contenuti/{_slug(source["content_id"])}/',
                [source["title"]], [],
            ))
    for topic in projection.get("topics", []):
        records.append(_record(
            "topic", topic["topic_id"], topic["canonical_name"],
            topic.get("scope_text") if topic.get("scope_text") is not None else "Tema pubblico revisionato",
            None, None, f'/temi/{topic["slug"]}/',
            [topic["canonical_name"]], [topic.get("scope_text")],
        ))
    for content in projection.get("contents", []):
        records.append(_record(
            "content", content["content_id"], content["title"],
            content["content_kind"].lower(), content.get("published_at"),
            None, f'/contenuti/{content["slug"]}/',
            [content["title"]], [content["content_kind"]],
        ))
    records.sort(key=lambda row: (row["kind"], row["id"]))
    return {
        "schema_version": "dichiarazioni-pubbliche-search-index-v1",
        "projection_sha256": state.fingerprint,
        "records": records,
    }


def linked_data_receipt(projection):
    return {
        "linked_data_version": "linked-data-v1",
        "projection_fingerprint": projection["dataset_sha256"],
        "ntriples_sha256": "9" * 64,
    }


def route_manifest(old_projection, new_projection, *, include_historical=True):
    old = propagation._projection_state(old_projection)
    new = propagation._projection_state(new_projection)
    entries = []
    for kind in propagation._ENTITY_KINDS:
        rows = getattr(new, "people" if kind == "person" else f"{kind}s")
        for identifier in sorted(rows):
            entries.append(
                {
                    "artifact_id": f"current:{kind}:{identifier}",
                    "entity_kind": kind,
                    "entity_id": identifier,
                    "view": "CURRENT",
                    "projection_fingerprint": new.fingerprint,
                    "entity_sha256": new.entity_sha256[(kind, identifier)],
                }
            )
    if include_historical:
        historical = set(old.findings) - set(new.findings)
        for dossier in new.findings.values():
            finding = dossier.get("finding") or {}
            supersedes_id = finding.get("supersedes_id")
            if supersedes_id and supersedes_id not in new.findings:
                historical.add(str(supersedes_id))
        for identifier in sorted(historical):
            if identifier not in old.findings:
                continue
            entries.append(
                {
                    "artifact_id": f"historical:finding:{identifier}",
                    "entity_kind": "finding",
                    "entity_id": identifier,
                    "view": "HISTORICAL",
                    "projection_fingerprint": new.fingerprint,
                    "entity_sha256": old.entity_sha256[("finding", identifier)],
                }
            )
    return {
        "manifest_version": ROUTE_STATIC_MANIFEST_VERSION,
        "projection_fingerprint": new.fingerprint,
        "entries": entries,
    }


def check(scenario, **overrides):
    values = {
        "old_projection": scenario["old_projection"],
        "new_projection": scenario["new_projection"],
        "search_index": search_index(scenario["new_projection"]),
        "linked_data_receipt": linked_data_receipt(scenario["new_projection"]),
        "route_static_manifest": route_manifest(
            scenario["old_projection"], scenario["new_projection"]
        ),
    }
    values.update(overrides)
    return check_correction_propagation(**values)


class CorrectionPropagationTests(unittest.TestCase):
    def test_fixture_scenarios_compute_affected_and_history_sets(self):
        for scenario in scenarios():
            with self.subTest(scenario=scenario["id"]):
                receipt = check(scenario)
                self.assertTrue(receipt.consistent, receipt.blockers)
                expected = scenario["expected"]
                for field in (
                    "affected_finding_ids",
                    "affected_content_ids",
                    "affected_person_ids",
                    "affected_topic_ids",
                    "current_finding_ids",
                    "historical_finding_ids",
                ):
                    self.assertEqual(list(getattr(receipt, field)), expected[field])
                self.assertEqual(
                    receipt.observed_projection_fingerprints,
                    (scenario["new_projection"]["dataset_sha256"],),
                )
                self.assertRegex(receipt.receipt_sha256, r"^[0-9a-f]{64}$")

    def test_receipt_preserves_historical_ids_even_when_no_historical_route_is_exposed(self):
        scenario = scenarios()[1]
        manifest = route_manifest(
            scenario["old_projection"],
            scenario["new_projection"],
            include_historical=False,
        )
        receipt = check(scenario, route_static_manifest=manifest)
        self.assertTrue(receipt.consistent, receipt.blockers)
        self.assertEqual(receipt.current_finding_ids, ())
        self.assertEqual(receipt.historical_finding_ids, ("finding:hold:v1",))

    def test_stale_search_entry_for_removed_current_identity_fails_closed(self):
        for scenario in scenarios():
            with self.subTest(scenario=scenario["id"]):
                index = search_index(scenario["new_projection"])
                index["records"].append(deepcopy(scenario["stale_search_record"]))
                receipt = check(scenario, search_index=index)
                self.assertFalse(receipt.consistent)
                self.assertIn("SEARCH_INDEX_ORPHAN_ENTRY", receipt.blockers)
                stale = scenario["stale_search_record"]
                self.assertIn(
                    f"search:{stale['kind']}:{stale['id']}",
                    receipt.orphan_artifacts,
                )

    def test_search_entry_with_current_id_but_old_text_is_stale(self):
        scenario = scenarios()[0]
        index = search_index(scenario["new_projection"])
        finding = next(row for row in index["records"] if row["kind"] == "finding")
        finding["title"] = "Versione errata attribuita a Persona Uno"
        receipt = check(scenario, search_index=index)
        self.assertFalse(receipt.consistent)
        self.assertIn("SEARCH_INDEX_STALE_ENTRY", receipt.blockers)
        self.assertIn("search:finding:finding:v2", receipt.stale_artifacts)

    def test_stale_content_membership_hash_in_static_manifest_is_detected(self):
        scenario = scenarios()[0]
        manifest = route_manifest(scenario["old_projection"], scenario["new_projection"])
        old = propagation._projection_state(scenario["old_projection"])
        content = next(
            row
            for row in manifest["entries"]
            if row.get("entity_kind") == "content" and row.get("view") == "CURRENT"
        )
        content["entity_sha256"] = old.entity_sha256[("content", "content:1")]
        receipt = check(scenario, route_static_manifest=manifest)
        self.assertFalse(receipt.consistent)
        self.assertIn("ROUTE_STATIC_STALE_ENTITY", receipt.blockers)
        self.assertIn("route:current:content:content:1", receipt.stale_artifacts)

    def test_partial_route_build_is_a_hold_with_missing_artifact_receipt(self):
        scenario = scenarios()[0]
        manifest = route_manifest(scenario["old_projection"], scenario["new_projection"])
        manifest["entries"] = [
            row
            for row in manifest["entries"]
            if not (
                row.get("entity_kind") == "topic" and row.get("view") == "CURRENT"
            )
        ]
        receipt = check(scenario, route_static_manifest=manifest)
        self.assertFalse(receipt.consistent)
        self.assertIn("ROUTE_STATIC_PARTIAL", receipt.blockers)
        self.assertIn("route:topic:topic:1", receipt.missing_artifacts)

    def test_missing_derived_manifest_is_a_hold(self):
        scenario = scenarios()[0]
        receipt = check(scenario, linked_data_receipt=None)
        self.assertFalse(receipt.consistent)
        self.assertIn("DERIVED_ARTIFACT_MISSING:linked-data", receipt.blockers)
        self.assertIn("linked-data", receipt.missing_artifacts)

    def test_mixed_top_level_fingerprints_fail_closed(self):
        scenario = scenarios()[0]
        linked = linked_data_receipt(scenario["new_projection"])
        linked["projection_fingerprint"] = scenario["old_projection"]["dataset_sha256"]
        receipt = check(scenario, linked_data_receipt=linked)
        self.assertFalse(receipt.consistent)
        self.assertIn("MIXED_OR_STALE_PROJECTION_FINGERPRINT", receipt.blockers)
        self.assertIn("MULTIPLE_DERIVED_PROJECTION_FINGERPRINTS", receipt.blockers)
        self.assertEqual(len(receipt.observed_projection_fingerprints), 2)

    def test_mixed_route_entry_fingerprint_fails_closed(self):
        scenario = scenarios()[0]
        manifest = route_manifest(scenario["old_projection"], scenario["new_projection"])
        manifest["entries"][0]["projection_fingerprint"] = scenario["old_projection"][
            "dataset_sha256"
        ]
        receipt = check(scenario, route_static_manifest=manifest)
        self.assertFalse(receipt.consistent)
        self.assertIn("MULTIPLE_DERIVED_PROJECTION_FINGERPRINTS", receipt.blockers)

    def test_historical_finding_cannot_masquerade_as_current_route(self):
        scenario = scenarios()[0]
        manifest = route_manifest(scenario["old_projection"], scenario["new_projection"])
        historical = next(row for row in manifest["entries"] if row["view"] == "HISTORICAL")
        historical["view"] = "CURRENT"
        receipt = check(scenario, route_static_manifest=manifest)
        self.assertFalse(receipt.consistent)
        self.assertIn("ROUTE_STATIC_ORPHAN_CURRENT_ENTRY", receipt.blockers)

    def test_in_place_finding_mutation_is_not_accepted_as_version_history(self):
        scenario = deepcopy(scenarios()[0])
        scenario["new_projection"]["dossiers"][0]["finding_id"] = "finding:v1"
        scenario["new_projection"]["dossiers"][0]["finding"]["supersedes_id"] = None
        scenario["new_projection"]["contents"][0]["finding_ids"] = ["finding:v1"]
        scenario["new_projection"]["topics"][0]["memberships"][0]["finding_ids"] = [
            "finding:v1"
        ]
        receipt = check(scenario)
        self.assertFalse(receipt.consistent)
        self.assertIn("FINDING_VERSION_MUTATED_IN_PLACE", receipt.blockers)
        self.assertEqual(receipt.current_finding_ids, ("finding:v1",))

    def test_receipt_is_deterministic_for_same_inputs(self):
        scenario = scenarios()[0]
        first = check(scenario)
        second = check(scenario)
        self.assertEqual(first, second)
        self.assertEqual(first.receipt_sha256, second.receipt_sha256)


if __name__ == "__main__":
    unittest.main()
