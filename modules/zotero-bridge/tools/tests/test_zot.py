from __future__ import annotations

import importlib.util
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from urllib import error


CLIENT = Path(__file__).parents[1] / "zot.py"
SPEC = importlib.util.spec_from_file_location("zot_client", CLIENT)
zot = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(zot)


class ZotClientTests(unittest.TestCase):
    def test_missing_endpoint_identifies_installation_failure(self):
        exc = zot.parse_server_error(None, 404)
        self.assertEqual(exc.code, "BRIDGE_NOT_LOADED")

    def test_invalid_json_is_structured(self):
        with self.assertRaises(zot.ClientError) as caught:
            zot.load_payload("{")
        self.assertEqual(caught.exception.code, "INVALID_JSON")

    def test_unknown_command_is_rejected_locally(self):
        with self.assertRaises(zot.ClientError) as caught:
            zot.validate_args("not_a_command", {})
        self.assertEqual(caught.exception.code, "UNKNOWN_COMMAND")

    def test_mutation_schema_rejects_relative_attachment(self):
        with self.assertRaises(zot.ClientError) as caught:
            zot.validate_args("link_file", {"absPath": "relative.pdf"})
        self.assertEqual(caught.exception.code, "INVALID_ARGS")

    def test_rename_collection_is_a_mutation_with_required_fields(self):
        self.assertIn("rename_collection", zot.MUTATING_COMMANDS)
        args = zot.validate_args("rename_collection", {"collectionKey": "ABCD1234", "name": "Génomique"})
        self.assertEqual(args["name"], "Génomique")
        for payload in ({"collectionKey": "ABCD1234"}, {"name": "Génomique"},
                        {"collectionKey": "ABCD1234", "name": "  "}):
            with self.subTest(payload=payload):
                with self.assertRaises(zot.ClientError) as caught:
                    zot.validate_args("rename_collection", payload)
                self.assertEqual(caught.exception.code, "INVALID_ARGS")

    def test_annotations_schema_accepts_bounded_read(self):
        args = zot.validate_args(
            "get_annotations",
            {
                "itemKey": "ABCD1234",
                "types": ["highlight", "note"],
                "colors": ["#ffd400"],
                "commentsOnly": True,
                "includePosition": False,
                "limit": 50,
                "offset": 10,
            },
        )
        self.assertEqual(args["itemKey"], "ABCD1234")

    def test_annotations_schema_rejects_unbounded_or_implicit_values(self):
        invalid_payloads = [
            {"itemKey": "ABCD1234", "limit": 501},
            {"itemKey": "ABCD1234", "limit": True},
            {"itemKey": "ABCD1234", "offset": -1},
            {"itemKey": "ABCD1234", "commentsOnly": "yes"},
            {"itemKey": "ABCD1234", "includePosition": 1},
            {"itemKey": "ABCD1234", "types": []},
        ]
        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                with self.assertRaises(zot.ClientError) as caught:
                    zot.validate_args("get_annotations", payload)
                self.assertEqual(caught.exception.code, "INVALID_ARGS")

    def test_http_error_body_is_preserved(self):
        payload = {"error": {"code": "ITEM_NOT_FOUND", "message": "Item absent", "details": {"key": "X"}}}
        exc = error.HTTPError(
            zot.DEFAULT_URL,
            400,
            "Bad Request",
            {},
            io.BytesIO(json.dumps(payload).encode()),
        )
        with tempfile.TemporaryDirectory() as directory:
            token = Path(directory) / "token"
            token.write_text("a" * 64, encoding="utf-8")
            with mock.patch.dict(os.environ, {"CODEX_ZOTERO_BRIDGE_TOKEN_FILE": str(token)}):
                with mock.patch.object(zot.request, "urlopen", side_effect=exc):
                    with self.assertRaises(zot.ClientError) as caught:
                        zot.call_bridge("ping", {}, None, 1)
        self.assertEqual(caught.exception.code, "ITEM_NOT_FOUND")
        self.assertEqual(caught.exception.details, {"key": "X"})

    def test_permission_error_has_dedicated_code(self):
        with tempfile.TemporaryDirectory() as directory:
            token = Path(directory) / "token"
            token.write_text("b" * 64, encoding="utf-8")
            denied = error.URLError(PermissionError(1, "Operation not permitted"))
            with mock.patch.dict(os.environ, {"CODEX_ZOTERO_BRIDGE_TOKEN_FILE": str(token)}):
                with mock.patch.object(zot.request, "urlopen", side_effect=denied):
                    with self.assertRaises(zot.ClientError) as caught:
                        zot.call_bridge("ping", {}, None, 1)
        self.assertEqual(caught.exception.code, "SANDBOX_DENIED")


if __name__ == "__main__":
    unittest.main()
