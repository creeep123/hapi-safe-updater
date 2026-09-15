#!/usr/bin/env python3
"""Render a JSON object as safely shell-quoted HSU_* variables."""
import json, os, shlex, sys
ALLOWED={"PACKAGE","CHANNEL","HAPI_BIN","NPM_BIN","BUN_BIN","BUN_INSTALL_MODE","HAPI_HOME","ROLE","UPDATE_MODE","SOURCE_REPO","PATCH_DIR","REQUIRED_PATCH_FILE","REQUIRED_PATCH_SHA256","REQUIRE_CANDIDATE_VERIFY","CANDIDATE_VERIFY_COMMAND","BINARY_INTEGRITY_PATH","EXPECTED_CURRENT_BINARY_SHA256","REQUIRE_DATABASE_ROLLBACK","DATABASE_SNAPSHOT_COMMAND","DATABASE_RESTORE_COMMAND","SCHEDULE_TZ","TARGET_HOUR","INTERVAL_DAYS","CATCH_UP_HOURS","UNKNOWN_RECENT_MINUTES","HEALTHCHECK_URL","VERIFY_COMMAND","QUIESCE_COMMAND","RESUME_COMMAND","USE_SUDO","KEEP_LOGS","KEEP_BACKUPS"}
p=os.path.expanduser(sys.argv[1])
try: data=json.load(open(p))
except FileNotFoundError: data={}
if not isinstance(data,dict): raise SystemExit("config must be a JSON object")
for key,lo,hi in (("TARGET_HOUR",0,23),("INTERVAL_DAYS",1,365),("CATCH_UP_HOURS",1,168),("UNKNOWN_RECENT_MINUTES",1,1440),("KEEP_LOGS",0,1000),("KEEP_BACKUPS",1,100)):
    if key in data and (not isinstance(data[key],int) or isinstance(data[key],bool) or not lo <= data[key] <= hi): raise SystemExit(f"invalid {key}: expected integer {lo}..{hi}")
if data.get("ROLE","auto") not in ("auto","hub","runner","hub+runner"): raise SystemExit("invalid ROLE")
if data.get("UPDATE_MODE","package") not in ("package","source"): raise SystemExit("invalid UPDATE_MODE")
if data.get("BUN_INSTALL_MODE","frozen") not in ("frozen","no-save"): raise SystemExit("invalid BUN_INSTALL_MODE")
if str(data.get("USE_SUDO","auto")) not in ("auto","0","1","False","True"): raise SystemExit("invalid USE_SUDO")
for key,value in data.items():
    if not key.replace("_","").isalnum() or not key.isupper(): raise SystemExit(f"invalid config key: {key}")
    if key not in ALLOWED: raise SystemExit(f"unknown config key: {key}")
    if isinstance(value,bool): value="1" if value else "0"
    elif isinstance(value,(dict,list)) or value is None: raise SystemExit(f"config value must be scalar: {key}")
    print(f"HSU_{key}={shlex.quote(os.path.expanduser(str(value)))}")
