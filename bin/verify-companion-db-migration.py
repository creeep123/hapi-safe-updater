#!/usr/bin/env python3
"""Drill v26->v27 migration and v26 rollback using only database copies."""

import argparse
import hashlib
import os
import secrets
import shutil
import signal
import socket
import sqlite3
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path


def require(ok, stage):
    if not ok:
        raise RuntimeError(f"database migration gate failed: {stage}")


def backup(source: Path, destination: Path):
    src = sqlite3.connect(f"file:{source}?mode=ro", uri=True, timeout=60)
    dst = sqlite3.connect(destination)
    try:
        with dst:
            src.backup(dst, pages=4096, sleep=0.05)
    finally:
        dst.close()
        src.close()
    os.chmod(destination, 0o600)


def scalar(db: Path, sql: str):
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=60)
    try:
        return con.execute(sql).fetchone()[0]
    finally:
        con.close()


def table_exists(con, name):
    return con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None


def companion_digest(db: Path):
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=60)
    digest = hashlib.sha256()
    try:
        for table, order in (
            ("companion_devices", "id"),
            ("companion_notification_outbox", "seq"),
        ):
            require(table_exists(con, table), f"{table} exists")
            columns = [row[1] for row in con.execute(f"PRAGMA table_info({table})")]
            digest.update(table.encode() + b"\0")
            for row in con.execute(f"SELECT * FROM {table} ORDER BY {order}"):
                for value in row:
                    digest.update(repr(value).encode() + b"\0")
        return digest.hexdigest()
    finally:
        con.close()


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def run_hub(binary: Path, db: Path, expected_version: int, root: Path):
    port = free_port()
    home = root / f"home-{expected_version}"
    home.mkdir(mode=0o700)
    log_path = root / f"hub-v{expected_version}.log"
    env = {
        **os.environ,
        "HOME": str(home),
        "HAPI_HOME": str(home / ".hapi"),
        "DB_PATH": str(db),
        "CLI_API_TOKEN": secrets.token_urlsafe(32),
        "HAPI_LISTEN_HOST": "127.0.0.1",
        "HAPI_LISTEN_PORT": str(port),
        "HAPI_PUBLIC_URL": f"http://127.0.0.1:{port}",
        "HAPI_IOS_PUSH": "off",
        "TELEGRAM_NOTIFICATION": "false",
        "SERVERCHAN_NOTIFICATION": "false",
    }
    with open(log_path, "w", opener=lambda p, f: os.open(p, f, 0o600)) as log:
        proc = subprocess.Popen([str(binary), "hub"], env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            deadline = time.time() + 60
            while time.time() < deadline:
                require(proc.poll() is None, f"v{expected_version} Hub startup")
                try:
                    with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1) as response:
                        if response.status == 200:
                            break
                except Exception:
                    pass
                time.sleep(0.25)
            else:
                raise RuntimeError(f"database migration gate failed: v{expected_version} health timeout")
            require(scalar(db, "PRAGMA user_version") == expected_version, f"schema v{expected_version}")
        finally:
            if proc.poll() is None:
                os.killpg(proc.pid, signal.SIGTERM)
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid, signal.SIGKILL)
                    proc.wait()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-db", required=True, type=Path)
    parser.add_argument("--new-bin", required=True, type=Path)
    parser.add_argument("--old-bin", required=True, type=Path)
    parser.add_argument("--work-dir", required=True, type=Path)
    args = parser.parse_args()
    for path, label in ((args.source_db, "source database"), (args.new_bin, "new binary"), (args.old_bin, "old binary")):
        require(path.is_file(), label)
    args.work_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
    source = args.work_dir / "production-v26.snapshot.db"
    migrated = args.work_dir / "candidate-v27.db"
    restored = args.work_dir / "restored-v26.db"

    backup(args.source_db, source)
    require(scalar(source, "PRAGMA quick_check") == "ok", "v26 snapshot quick_check")
    require(scalar(source, "PRAGMA user_version") == 26, "source schema v26")
    before = companion_digest(source)

    backup(source, migrated)
    run_hub(args.new_bin, migrated, 27, args.work_dir)
    require(scalar(migrated, "PRAGMA quick_check") == "ok", "migrated v27 quick_check")
    require(companion_digest(migrated) == before, "Companion rows and ACK cursors preserved")
    indexes = sqlite3.connect(f"file:{migrated}?mode=ro", uri=True).execute(
        "SELECT name FROM sqlite_master WHERE type='index'"
    ).fetchall()
    names = {row[0] for row in indexes}
    require("idx_messages_immediate_queued" in names, "upstream v26 index reconciled")

    backup(source, restored)
    run_hub(args.old_bin, restored, 26, args.work_dir)
    require(scalar(restored, "PRAGMA quick_check") == "ok", "restored v26 quick_check")
    require(companion_digest(restored) == before, "restored v26 data matches snapshot")
    print("companion database migration and rollback gate: PASS")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(str(exc), file=os.sys.stderr)
        raise SystemExit(1)
