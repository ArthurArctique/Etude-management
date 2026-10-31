import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location("bridge_build", ROOT / "build_codex_zotero_bridge.py")
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


class PackageValidationTests(unittest.TestCase):
    def test_current_package_validates(self):
        build.validate(ROOT / "codex-zotero-bridge")

    def test_missing_or_insecure_update_url_is_rejected(self):
        for url in (None, "http://127.0.0.1/updates.json"):
            with self.subTest(url=url), tempfile.TemporaryDirectory() as directory:
                source = Path(directory) / "source"
                shutil.copytree(ROOT / "codex-zotero-bridge", source)
                path = source / "manifest.json"
                data = json.loads(path.read_text())
                settings = data["applications"]["zotero"]
                if url is None:
                    settings.pop("update_url", None)
                else:
                    settings["update_url"] = url
                path.write_text(json.dumps(data))
                with self.assertRaises(SystemExit):
                    build.validate(source)
