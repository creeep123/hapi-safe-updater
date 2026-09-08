import json, subprocess, sys, tempfile, unittest
from pathlib import Path

SCRIPT=Path(__file__).parents[1]/"bin/config-env.py"
class ConfigTests(unittest.TestCase):
    def test_unknown_key_is_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/"c.json"; p.write_text(json.dumps({"UPDATE_MOD":"source"}))
            self.assertNotEqual(subprocess.run([sys.executable,str(SCRIPT),str(p)],capture_output=True).returncode,0)
    def test_shell_metacharacters_are_quoted_data(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/"c.json"; p.write_text(json.dumps({"VERIFY_COMMAND":"echo ok; true"}))
            out=subprocess.check_output([sys.executable,str(SCRIPT),str(p)],text=True)
            self.assertIn("HSU_VERIFY_COMMAND='echo ok; true'",out)
    def test_companion_gate_keys_are_accepted_as_data(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/"c.json"
            p.write_text(json.dumps({
                "REQUIRED_PATCH_FILE":"/tmp/companion.patch",
                "REQUIRED_PATCH_SHA256":"a"*64,
                "REQUIRE_CANDIDATE_VERIFY":1,
                "CANDIDATE_VERIFY_COMMAND":"verify-candidate",
                "BINARY_INTEGRITY_PATH":"/opt/hapi/bin/hapi",
                "EXPECTED_CURRENT_BINARY_SHA256":"b"*64,
            }))
            out=subprocess.check_output([sys.executable,str(SCRIPT),str(p)],text=True)
            self.assertIn("HSU_REQUIRED_PATCH_SHA256="+"a"*64,out)
            self.assertIn("HSU_REQUIRE_CANDIDATE_VERIFY=1",out)
            self.assertIn("HSU_EXPECTED_CURRENT_BINARY_SHA256="+"b"*64,out)
if __name__=="__main__": unittest.main()
