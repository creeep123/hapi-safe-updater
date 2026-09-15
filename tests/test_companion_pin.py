import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIN_PATH = ROOT / "docs" / "pins" / "companion-patched-hub.json"


class CompanionPinTests(unittest.TestCase):
    def test_pin_is_complete_and_documented(self):
        pin = json.loads(PIN_PATH.read_text())
        self.assertEqual(pin["schemaVersion"], 1)
        self.assertRegex(pin["companionCommit"], r"^[0-9a-f]{40}$")
        self.assertRegex(pin["hapiBaselineCommit"], r"^[0-9a-f]{40}$")
        self.assertRegex(pin["patchSha256"], r"^[0-9a-f]{64}$")
        self.assertRegex(pin["previousPatchSha256"], r"^[0-9a-f]{64}$")
        self.assertNotEqual(pin["patchSha256"], pin["previousPatchSha256"])
        self.assertEqual(pin["patchPath"], "integrations/hapi/hapi-companion.patch")
        self.assertIn("input-request", pin["contractChanges"])
        self.assertIn("v26 to v27", pin["databaseSchemaChanges"])
        self.assertEqual(pin["bunInstallMode"], "frozen")

        panel = (ROOT / "docs" / "management" / "CONTROL_PANEL.md").read_text()
        spec = (ROOT / "docs" / "specs" / "COMPANION_PATCHED_HUB_UPGRADE_SPEC.md").read_text()
        self.assertIn(pin["patchSha256"], panel)
        self.assertIn(pin["hapiBaselineCommit"], panel)
        self.assertIn("docs/pins/companion-patched-hub.json", spec)


if __name__ == "__main__":
    unittest.main()
