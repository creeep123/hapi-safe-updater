import json
import os
import subprocess
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "bin" / "verify-runner-smoke.py"
SECRET = "must-not-appear-in-output"


class Handler(BaseHTTPRequestHandler):
    failed_stage = None
    session_reads = 0
    transient_machine_failures = 0

    def log_message(self, *_args):
        pass

    def reply(self, status, payload):
        raw = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(length) or b"{}")
        if self.path == "/api/auth":
            self.reply(401 if self.failed_stage == "auth" else 200, {"token": SECRET})
        elif self.path == "/api/machines/machine-1/spawn":
            if self.failed_stage == "spawn-rejected":
                self.reply(200, {"type": "error", "code": "runner_busy", "message": SECRET})
            else:
                self.reply(500 if self.failed_stage == "spawn" else 200, {"sessionId": "session-1", "debug": SECRET})
        elif self.path == "/api/sessions/session-1/messages":
            self.server.local_id = body.get("localId", "")
            self.reply(500 if self.failed_stage == "message" else 200, {"ok": True})
        elif self.path == "/api/sessions/session-1/archive":
            self.reply(200, {"ok": True})
        else:
            self.reply(404, {})

    def do_GET(self):
        if self.path == "/api/machines":
            if self.transient_machine_failures:
                Handler.transient_machine_failures -= 1
                self.reply(503, {"debug": SECRET})
                return
            active = self.failed_stage != "machine"
            self.reply(200, {"machines": [{"id": "machine-1", "active": active, "debug": SECRET}]})
        elif self.path == "/api/machines/machine-1/codex-models":
            models = [] if self.failed_stage == "models" else [{"id": "gpt-test"}]
            self.reply(200, {"success": True, "models": models, "debug": SECRET})
        elif self.path == "/api/sessions/session-1":
            self.reply(200, {"session": {"active": True, "thinking": False, "metadata": {"flavor": "codex"}}})
        elif self.path.startswith("/api/sessions/session-1/messages?"):
            messages = [{"localId": self.server.local_id, "seq": 1, "content": {"role": "user"}}]
            if self.failed_stage != "reply":
                messages.append({"seq": 2, "content": {"role": "agent"}})
            self.reply(200, {"messages": messages})
        else:
            self.reply(404, {})


class RunnerSmokeTest(unittest.TestCase):
    def setUp(self):
        Handler.failed_stage = None
        Handler.transient_machine_failures = 0
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.local_id = ""
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.log = root / "runner.log"
        self.log.write_text("[API MACHINE] Connected to bot\n")
        self.settings = root / "settings.json"
        self.settings.write_text(json.dumps({
            "apiUrl": f"http://127.0.0.1:{self.server.server_port}",
            "cliApiToken": SECRET,
            "machineId": "machine-1",
        }))
        self.state = root / "state.json"
        self.state.write_text(json.dumps({
            "pid": os.getpid(), "runnerLogPath": str(self.log), "startedWithCliVersion": "0.30.7"
        }))

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.tmp.cleanup()

    def run_smoke(self, failed_stage=None):
        Handler.failed_stage = failed_stage
        return subprocess.run([
            "python3", str(SCRIPT), "--settings", str(self.settings), "--runner-state", str(self.state),
            "--expected-version", "0.30.7", "--spawn", "--poll-seconds", "2",
        ], text=True, capture_output=True, timeout=10)

    def test_reports_all_successful_stages_without_secrets(self):
        result = self.run_smoke()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for stage in ("auth", "machine", "models", "spawn", "message", "reply"):
            self.assertIn(f"stage={stage} status=pass", result.stdout)
            self.assertNotIn(SECRET, result.stdout + result.stderr)

    def test_spawn_rejection_reports_only_safe_code(self):
        result = self.run_smoke("spawn-rejected")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("spawn_rejected_runner_busy", result.stdout)
        self.assertNotIn(SECRET, result.stdout + result.stderr)

    def test_reports_exact_failure_stage_without_response_body(self):
        for stage in ("auth", "machine", "models", "spawn", "message", "reply"):
            with self.subTest(stage=stage):
                result = self.run_smoke(stage)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(f"stage={stage} status=fail", result.stdout)
                self.assertNotIn(SECRET, result.stdout + result.stderr)

    def test_retries_a_transient_server_failure_without_leaking_body(self):
        Handler.transient_machine_failures = 1
        result = self.run_smoke()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("stage=machine status=pass", result.stdout)
        self.assertNotIn(SECRET, result.stdout + result.stderr)

if __name__ == "__main__":
    unittest.main()
