import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGIN = ROOT / ".claude-plugin" / "plugin.json"
MARKETPLACE = ROOT / ".claude-plugin" / "marketplace.json"
VERSION = (ROOT / "tools" / "specs" / "VERSION").read_text(encoding="utf-8").strip()


class PluginManifestTest(unittest.TestCase):
    def setUp(self):
        self.plugin = json.loads(PLUGIN.read_text(encoding="utf-8"))

    def test_identity(self):
        self.assertEqual(self.plugin["name"], "sdlc")
        self.assertEqual(self.plugin["license"], "MIT")
        self.assertTrue(self.plugin["description"].strip())
        self.assertTrue(self.plugin["author"]["name"].strip())

    def test_one_version_number(self):
        # tools/specs/VERSION is the source; the manifest must follow it.
        self.assertEqual(self.plugin["version"], VERSION)


class MarketplaceTest(unittest.TestCase):
    def setUp(self):
        self.marketplace = json.loads(MARKETPLACE.read_text(encoding="utf-8"))

    def test_lists_this_repo_as_the_sdlc_plugin(self):
        self.assertEqual(self.marketplace["name"], "sdlc")
        entries = [p for p in self.marketplace["plugins"] if p["name"] == "sdlc"]
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["source"], "./")
        self.assertEqual(entries[0]["version"], VERSION)


class ReadmeTest(unittest.TestCase):
    def test_states_what_does_not_ship(self):
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        for phrase in ("no CI integration", "no credentials", "never copied into"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_license_file(self):
        self.assertIn("MIT License", (ROOT / "LICENSE").read_text(encoding="utf-8"))
