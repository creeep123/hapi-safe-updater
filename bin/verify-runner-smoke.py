#!/usr/bin/env python3
"""Verify a running HAPI Runner without ever logging credentials or bodies."""

import argparse
import json
import os
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path


class SmokeFailure(Exception):
    def __init__(self, stage, reason):
        super().__init__(reason)
        self.stage = stage
        self.reason = reason


def report(stage, status, **fields):
    suffix = "".join(f" {key}={json.dumps(value, separators=(',', ':'))}" for key, value in fields.items())
    print(f"[smoke] stage={stage} status={status}{suffix}", flush=True)


def require(condition, stage, reason):
    if not condition:
        raise SmokeFailure(stage, reason)


def request_json(url, method="GET", headers=None, body=None, timeout=30):
    data = None if body is None else json.dumps(body, separators=(",", ":")).encode()
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Accept", "application/json")
    req.add_header("User-Agent", "HAPI-Safe-Updater/1")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    for key, value in (headers or {}).items():
        req.add_header(key, value)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            status = response.status
            raw = response.read()
    except urllib.error.HTTPError as error:
        status = error.code
        raw = error.read()
    try:
        payload = json.loads(raw) if raw else {}
    except (UnicodeDecodeError, json.JSONDecodeError):
        payload = None
    return status, payload


def checked_request(stage, *args, **kwargs):
    try:
        return request_json(*args, **kwargs)
    except (OSError, TimeoutError, urllib.error.URLError):
        raise SmokeFailure(stage, "request_failed") from None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--settings", default="~/.hapi/settings.json")
    parser.add_argument("--runner-state", default="~/.hapi/runner.state.json")
    parser.add_argument("--expected-version", default="")
    parser.add_argument("--spawn", action="store_true")
    parser.add_argument("--directory", default=os.environ.get("HAPI_SMOKE_DIRECTORY", "~/develop/ananlyse-sth"))
    parser.add_argument("--poll-seconds", type=int, default=90)
    args = parser.parse_args()

    stage = "preflight"
    session_id = ""
    jwt = ""
    api_url = ""
    try:
        settings = json.loads(Path(args.settings).expanduser().read_text())
        runner = json.loads(Path(args.runner_state).expanduser().read_text())
        api_url = (settings.get("apiUrl") or settings.get("serverUrl") or "").rstrip("/")
        access_token = settings.get("cliApiToken") or ""
        machine_id = settings.get("machineId") or ""
        runner_pid = runner.get("pid")
        runner_log = runner.get("runnerLogPath") or ""
        runner_version = runner.get("startedWithCliVersion") or ""
        require(api_url and access_token and machine_id and runner_pid and runner_log, stage, "settings_or_state_incomplete")
        try:
            os.kill(int(runner_pid), 0)
        except (ValueError, OSError):
            raise SmokeFailure(stage, "runner_not_alive") from None
        require(not args.expected_version or runner_version == args.expected_version, stage, "runner_version_mismatch")
        require("[API MACHINE] Connected to bot" in Path(runner_log).read_text(errors="replace"), stage, "runner_not_connected")
        report(stage, "pass", runnerVersion=runner_version)

        stage = "auth"
        status, payload = checked_request(stage, api_url + "/api/auth", "POST", body={"accessToken": access_token})
        require(status == 200, stage, f"unexpected_http_{status}")
        require(isinstance(payload, dict) and payload.get("token"), stage, "invalid_auth_payload")
        jwt = payload["token"]
        auth = {"Authorization": "Bearer " + jwt}
        report(stage, "pass", httpStatus=status)

        stage = "machine"
        status, payload = checked_request(stage, api_url + "/api/machines", headers=auth)
        machines = payload.get("machines", []) if isinstance(payload, dict) else []
        active = any(item.get("id") == machine_id and item.get("active") is True for item in machines if isinstance(item, dict))
        require(status == 200, stage, f"unexpected_http_{status}")
        require(active, stage, "machine_not_active")
        report(stage, "pass", httpStatus=status)

        stage = "models"
        status, payload = checked_request(stage, f"{api_url}/api/machines/{machine_id}/codex-models", headers=auth, timeout=60)
        models = payload.get("models", []) if isinstance(payload, dict) else []
        require(status == 200, stage, f"unexpected_http_{status}")
        require(isinstance(payload, dict) and payload.get("success") is True and models, stage, "no_codex_models")
        model_id = models[0].get("id") if isinstance(models[0], dict) else None
        require(model_id, stage, "invalid_model_payload")
        report(stage, "pass", httpStatus=status, modelCount=len(models))

        if not args.spawn:
            return 0

        stage = "spawn"
        status, payload = checked_request(
            stage,
            f"{api_url}/api/machines/{machine_id}/spawn",
            "POST",
            auth,
            {"directory": str(Path(args.directory).expanduser()), "agent": "codex", "model": model_id,
             "permissionMode": "default", "sessionType": "simple", "serviceTier": "standard", "startingMode": "remote"},
            60,
        )
        session_id = (payload.get("sessionId") or payload.get("id") or "") if isinstance(payload, dict) else ""
        require(status == 200, stage, f"unexpected_http_{status}")
        require(session_id, stage, "invalid_spawn_payload")
        deadline = time.monotonic() + 30
        ready = False
        while time.monotonic() < deadline:
            session_status, session = checked_request(stage, f"{api_url}/api/sessions/{session_id}", headers=auth, timeout=10)
            if session_status == 200 and isinstance(session, dict) and session.get("active") is True and session.get("metadata", {}).get("flavor") == "codex":
                ready = True
                break
            time.sleep(1)
        require(ready, stage, "session_not_ready")
        report(stage, "pass", httpStatus=status)

        stage = "message"
        local_id = f"hapi-auto-update-smoke-{int(time.time())}-{os.getpid()}-{uuid.uuid4().hex[:8]}"
        status, payload = checked_request(
            stage, f"{api_url}/api/sessions/{session_id}/messages", "POST", auth,
            {"text": "这是 Hapi 自动更新烟测。请只回复 HAPI_SMOKE_OK。", "localId": local_id}, 20,
        )
        require(status == 200, stage, f"unexpected_http_{status}")
        require(isinstance(payload, dict) and payload.get("ok") is True, stage, "invalid_message_payload")
        report(stage, "pass", httpStatus=status)

        stage = "reply"
        deadline = time.monotonic() + args.poll_seconds
        replied = False
        complete = False
        while time.monotonic() < deadline:
            _, session = checked_request(stage, f"{api_url}/api/sessions/{session_id}", headers=auth, timeout=10)
            _, message_page = checked_request(stage, f"{api_url}/api/sessions/{session_id}/messages?limit=50", headers=auth, timeout=10)
            messages = message_page.get("messages", []) if isinstance(message_page, dict) else []
            user_seqs = [m.get("seq") for m in messages if isinstance(m, dict) and m.get("localId") == local_id and m.get("content", {}).get("role") == "user" and isinstance(m.get("seq"), int)]
            if user_seqs:
                user_seq = max(user_seqs)
                replied = any(isinstance(m, dict) and m.get("content", {}).get("role") == "agent" and isinstance(m.get("seq"), int) and m["seq"] > user_seq for m in messages)
            if replied and isinstance(session, dict) and session.get("thinking") is not True:
                complete = True
                break
            time.sleep(1)
        require(complete, stage, "agent_reply_timeout")
        report(stage, "pass")
        print(json.dumps({"ok": True, "runnerVersion": runner_version, "modelCount": len(models), "spawned": True}, separators=(",", ":")))
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as error:
        report(stage, "fail", reason="invalid_local_input", errorType=type(error).__name__)
        return 1
    except SmokeFailure as error:
        report(error.stage, "fail", reason=error.reason)
        return 1
    finally:
        if session_id and jwt and api_url:
            try:
                request_json(api_url + f"/api/sessions/{session_id}/archive", "POST", {"Authorization": "Bearer " + jwt}, timeout=20)
            except Exception:
                report("cleanup", "warn", reason="archive_failed")


if __name__ == "__main__":
    raise SystemExit(main())
