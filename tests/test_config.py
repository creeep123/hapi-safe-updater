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
if __name__=="__main__": unittest.main()
