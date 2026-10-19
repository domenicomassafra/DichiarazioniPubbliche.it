"""DP #175: upstream OpenAPI 3.1 validation in the opt-in developer profile.

The production API is stdlib-only. The dedicated CI job installs the dev extra;
ordinary checkout/runtime tests may run without these optional packages.
"""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from dichiarazioni_pubbliche.openapi import build_openapi_document
from dichiarazioni_pubbliche.public_api import build_index, dispatch

try:
    from openapi_schema_validator import OAS31Validator
    from openapi_spec_validator import validate
    from openapi_spec_validator.validation.exceptions import OpenAPIValidationError
    from referencing import Registry, Resource
    from referencing.exceptions import PointerToNowhere
    from referencing.jsonschema import DRAFT202012
except ImportError:
    validate = None


ROOT = Path(__file__).resolve().parents[1]
DEMO_PROJECTION = ROOT / "web" / "src" / "data" / "demo-projection.json"
SPEC_URI = "https://example.test/openapi.json"


def _pointer(value: str) -> str:
    """JSON Pointer escaping for paths and application/json media types."""
    return value.replace("~", "~0").replace("/", "~1")


@unittest.skipUnless(validate is not None, "dev-only openapi-spec-validator is not installed")
class UpstreamOpenApiValidationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bundle = json.loads(DEMO_PROJECTION.read_text(encoding="utf-8"))
        cls.demo_index = build_index(cls.bundle)
        empty = copy.deepcopy(cls.bundle)
        empty["dossiers"] = []
        empty["dossier_count"] = 0
        cls.empty_index = build_index(empty)

    def test_official_openapi_3_1_validator_accepts_all_projections(self) -> None:
        for name, index in (("without index", None), ("empty", self.empty_index), ("demo", self.demo_index)):
            with self.subTest(projection=name):
                document = build_openapi_document(index)
                self.assertEqual(document["openapi"], "3.1.0")
                validate(document)

    def test_upstream_rejects_invalid_schema_and_unresolved_component(self) -> None:
        document = build_openapi_document(self.demo_index)
        data_schema = document["paths"]["/api/v1/findings"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]["allOf"][0]["properties"]["data"]
        self.assertIn("items", data_schema)

        bad_reference_type = copy.deepcopy(document)
        bad_reference_type["paths"]["/api/v1/findings"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]["allOf"][0]["properties"]["data"]["items"]["$ref"] = {"type": "string"}
        with self.assertRaises(OpenAPIValidationError):
            validate(bad_reference_type)

        missing_reference = copy.deepcopy(document)
        missing_reference["paths"]["/api/v1/findings"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]["allOf"][0]["properties"]["data"]["items"]["$ref"] = "#/components/schemas/NotPresent"
        with self.assertRaises(PointerToNowhere):
            validate(missing_reference)

    def test_all_documented_response_examples_match_openapi_schemas(self) -> None:
        for name, index in (("empty", self.empty_index), ("demo", self.demo_index)):
            document = build_openapi_document(index)
            validate(document)
            registry = Registry().with_resource(
                SPEC_URI, Resource.from_contents(document, default_specification=DRAFT202012)
            )
            checked = 0
            for path, methods in document["paths"].items():
                for method, operation in methods.items():
                    for status, response in operation["responses"].items():
                        if "$ref" in response:
                            component = response["$ref"].rsplit("/", 1)[-1]
                            response = document["components"]["responses"][component]
                            prefix = f"/components/responses/{_pointer(component)}"
                        else:
                            prefix = f"/paths/{_pointer(path)}/{method}/responses/{status}"
                        for media_type, media in response.get("content", {}).items():
                            if "schema" not in media:
                                continue
                            reference = SPEC_URI + "#" + prefix + f"/content/{_pointer(media_type)}/schema"
                            schema_validator = OAS31Validator({"$ref": reference}, registry=registry)
                            examples = [media["example"]] if "example" in media else []
                            examples.extend(item["value"] for item in media.get("examples", {}).values() if "value" in item)
                            for example in examples:
                                with self.subTest(projection=name, path=path, method=method, status=status):
                                    schema_validator.validate(example)
                                checked += 1
            self.assertGreaterEqual(checked, 90)

    def test_get_openapi_bytes_remain_the_generated_document(self) -> None:
        document = build_openapi_document(self.demo_index)
        response = dispatch("GET", "/api/v1/openapi.json", projection_path=str(DEMO_PROJECTION))
        self.assertEqual(response.status, 200)
        self.assertEqual(json.loads(response.body), document)


if __name__ == "__main__":
    unittest.main()
