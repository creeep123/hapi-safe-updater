#!/usr/bin/env python3
"""Verify the live Companion contract in an isolated synthetic namespace."""

import hashlib, json, secrets, sqlite3, time, urllib.error, urllib.request, uuid
from pathlib import Path

BASE = "http://127.0.0.1:8080"
DB = Path("/home/moses/.hapi/hapi.db")


def request(path, method="GET", headers=None, body=None, timeout=8):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(BASE + path, data=data, method=method, headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.status, response.headers, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.headers, error.read()


def need(value, stage):
    if not value:
        raise RuntimeError(f"production contract failed: {stage}")


def frames(headers, count):
    req = urllib.request.Request(BASE + "/companion/events", headers=headers)
    with urllib.request.urlopen(req, timeout=8) as stream:
        need(stream.headers.get_content_type() == "text/event-stream", "SSE content type")
        result, frame = [], []
        while len(result) < count:
            line = stream.readline().decode().rstrip("\r\n")
            if line:
                frame.append(line)
            elif frame:
                result.append(frame)
                frame = []
        return result


def main():
    need(request("/health")[0] == 200, "health")
    need(request("/companion/sessions")[0] == 401, "sessions unauthenticated 401")
    need(request("/companion/events")[0] == 401, "events unauthenticated 401")
    namespace = "hsu-gate-" + str(uuid.uuid4())
    device_id, installation_id = str(uuid.uuid4()), str(uuid.uuid4())
    foreign_device_id, foreign_installation_id = str(uuid.uuid4()), str(uuid.uuid4())
    token, foreign_token = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    event_id, foreign_id = str(uuid.uuid4()), str(uuid.uuid4())
    now = int(time.time() * 1000)
    payload = {"version": 1, "eventId": event_id, "createdAt": now, "kind": "session-completed", "title": "Maintenance gate", "body": "Isolated event", "severity": "success", "sessionId": str(uuid.uuid4()), "sessionName": "Maintenance", "url": "/sessions/" + str(uuid.uuid4()), "durationMs": 1234}
    con = sqlite3.connect(DB, timeout=30)
    try:
        need(con.execute("PRAGMA user_version").fetchone()[0] == 27, "schema v27")
        con.execute("INSERT INTO companion_devices(id,installation_id,namespace,name,token_hash,created_at,updated_at,last_ack_seq,enabled) VALUES(?,?,?,?,?,?,?,?,1)", (device_id, installation_id, namespace, "Updater gate", hashlib.sha256(token.encode()).hexdigest(), now, now, 0))
        con.execute("INSERT INTO companion_devices(id,installation_id,namespace,name,token_hash,created_at,updated_at,last_ack_seq,enabled) VALUES(?,?,?,?,?,?,?,?,1)", (foreign_device_id, foreign_installation_id, namespace + "-foreign", "Foreign gate", hashlib.sha256(foreign_token.encode()).hexdigest(), now, now, 0))
        seq = con.execute("INSERT INTO companion_notification_outbox(event_id,namespace,payload_json,created_at,expires_at) VALUES(?,?,?,?,?)", (event_id, namespace, json.dumps(payload), now, now + 60000)).lastrowid
        foreign_seq = con.execute("INSERT INTO companion_notification_outbox(event_id,namespace,payload_json,created_at,expires_at) VALUES(?,?,?,?,?)", (foreign_id, namespace + "-foreign", json.dumps({**payload, "eventId": foreign_id}), now, now + 60000)).lastrowid
        con.commit()
        device = {"Authorization": "Bearer " + token, "X-Hapi-Device-Id": device_id}
        foreign = {"Authorization": "Bearer " + foreign_token, "X-Hapi-Device-Id": foreign_device_id}
        status, _, raw = request("/companion/sessions", headers=device)
        catalog = json.loads(raw)
        need(status == 200 and isinstance(catalog.get("sessions"), list) and isinstance(catalog.get("capabilities", {}).get("turnDuration"), bool), "catalog")
        first = frames(device, 2)
        second = frames(device, 2)
        for observed in (first, second):
            need(any(line == "event: connected" for line in observed[0]), "connected first frame")
            need(any(line == f"id: {seq}" for line in observed[1]), "event and replay")
            need(not any(foreign_id in line for frame in observed for line in frame), "namespace isolation")
        need(request("/companion/ack", "POST", device, {"seq": foreign_seq, "eventId": foreign_id})[0] == 409, "cross-namespace ACK rejection")
        swapped = {"Authorization": "Bearer " + foreign_token, "X-Hapi-Device-Id": device_id}
        need(request("/companion/ack", "POST", swapped, {"seq": seq, "eventId": event_id})[0] == 401, "cross-device credential rejection")
        status, _, raw = request("/companion/ack", "POST", device, {"seq": seq, "eventId": event_id})
        need(status == 200 and json.loads(raw).get("ok") is True, "ACK")
        need(con.execute("SELECT last_ack_seq FROM companion_devices WHERE id=?", (device_id,)).fetchone()[0] == seq, "ACK cursor")
    finally:
        con.execute("DELETE FROM companion_notification_outbox WHERE event_id IN (?,?)", (event_id, foreign_id))
        con.execute("DELETE FROM companion_devices WHERE id IN (?,?)", (device_id, foreign_device_id))
        con.commit()
        con.close()
    print("production companion contract: PASS")


if __name__ == "__main__":
    main()
