#!/usr/bin/env python3
"""Fail closed when a local or hub-visible HAPI task is executing/outputting."""
from __future__ import annotations
import argparse, glob, json, os, re, sqlite3, subprocess, sys, time
from dataclasses import asdict, dataclass

FLAVORS = {"codex", "claude", "cursor", "gemini", "opencode", "grok", "kimi", "pi"}
BUSY_PREFIXES = ("busy", "unknown")

@dataclass
class Status:
    status: str
    session_id: str
    pid: int | None
    age_min: float | None
    path: str | None
    evidence: list[str]

def j(value):
    try: return json.loads(value) if value else {}
    except Exception: return None

def agent_pids() -> set[int]:
    try: out = subprocess.check_output(["ps", "-eo", "pid=,command="], text=True,stderr=subprocess.DEVNULL)
    except Exception as exc: raise RuntimeError("process_scan_failed") from exc
    found=set()
    for line in out.splitlines():
        if re.search(r"(?:^|/)hapi\s+(?:codex|claude|cursor|gemini|opencode|grok|kimi|pi)(?:\s|$)", line):
            try: found.add(int(line.split(None,1)[0]))
            except Exception: pass
    return found

def log_state(pid, age, logdir, unknown_min, local_live=False):
    if not pid: return "unknown_recent_no_pid" if age < unknown_min else "idle_no_pid", []
    files=glob.glob(os.path.join(logdir, f"*-pid-{pid}.log"))
    if not files: return ("unknown_live_no_log" if local_live else ("unknown_recent_no_log" if age < unknown_min else "idle_no_log")), []
    try:
        with open(max(files,key=os.path.getmtime),errors="replace") as fp:
            lines=fp.read().splitlines()[-1000:]
    except Exception: return "unknown_unreadable_log", []
    event_re=re.compile(r"^\[[0-9:. -]+\](?: \[MessageQueue2\])? (thinking started|thinking completed|Waiting for messages)(?:\.\.\.)?\s*$")
    events=[event_re.match(x).group(1) for x in lines if event_re.match(x)]
    start=max((i for i,x in enumerate(events) if "thinking started" in x),default=-1)
    idle=max((i for i,x in enumerate(events) if "thinking completed" in x or "Waiting for messages" in x),default=-1)
    if start > idle: return "busy_executing", events[-8:]
    if idle >= 0: return "idle_waiting", events[-6:]
    return ("unknown_live_no_state" if local_live else ("unknown_recent_no_state" if age < unknown_min else "idle_no_recent_state")), events[-6:]

def collect(db, logdir, unknown_min):
    if not os.path.exists(db):
        # Runner-only hosts may have no hub DB; classify their local logs by PID.
        out=[]
        try: pids=agent_pids()
        except RuntimeError: return [Status("unknown_process_scan","local",None,None,None,["process scan failed"])]
        for p in sorted(pids):
            status,evidence=log_state(p,0,logdir,unknown_min,local_live=True)
            out.append(Status(status,f"local-pid-{p}",p,None,None,[x[-300:] for x in evidence]))
        return out
    con=sqlite3.connect(f"file:{db}?mode=ro",uri=True); con.row_factory=sqlite3.Row
    cols={r[1] for r in con.execute("pragma table_info(sessions)")}
    needed={"id","metadata","agent_state","updated_at"}
    if not needed <= cols: return [Status("unknown_schema", "database", None, None, db, [str(sorted(cols))])]
    now=int(time.time()*1000)
    try: pids=agent_pids()
    except RuntimeError: return [Status("unknown_process_scan","local",None,None,None,["process scan failed"])]
    out=[]
    for r in con.execute("select id,metadata,agent_state,updated_at from sessions order by updated_at desc"):
        md,st=j(r["metadata"]),j(r["agent_state"])
        if md is None or st is None:
            out.append(Status("unknown_invalid_json",r["id"],None,None,None,["metadata/agent_state JSON invalid"])); continue
        flavor=md.get("flavor")
        raw=md.get("hostPid"); pid=int(raw) if str(raw).isdigit() else None
        if md.get("lifecycleState") != "running" and pid not in pids: continue
        age=(now-(r["updated_at"] or now))/60000
        if flavor not in FLAVORS:
            out.append(Status("unknown_flavor",r["id"],pid,round(age,1),md.get("path"),[f"flavor={flavor!r}"])); continue
        req=st.get("requests") if isinstance(st,dict) else None
        if isinstance(req,dict) and req:
            out.append(Status("busy_pending_request",r["id"],pid,round(age,1),md.get("path"),[f"requests={len(req)}"])); continue
        if st.get("steeringActive") is True:
            out.append(Status("busy_steering_active",r["id"],pid,round(age,1),md.get("path"),["agent_state.steeringActive=true"])); continue
        if pid not in pids:
            out.append(Status("idle_remote_not_steering",r["id"],pid,round(age,1),md.get("path"),["steeringActive=false"])); continue
        status,evidence=log_state(pid,age,logdir,unknown_min,local_live=True)
        out.append(Status(status,r["id"],pid,round(age,1),md.get("path"),[x[-300:] for x in evidence]))
    return out

def main():
    home=os.path.expanduser(os.environ.get("HAPI_HOME","~/.hapi"))
    ap=argparse.ArgumentParser(); ap.add_argument("--db",default=os.path.join(home,"hapi.db")); ap.add_argument("--logdir",default=os.path.join(home,"logs")); ap.add_argument("--unknown-recent-minutes",type=int,default=int(os.environ.get("UNKNOWN_RECENT_MINUTES","15"))); ap.add_argument("--json",action="store_true")
    a=ap.parse_args(); statuses=collect(a.db,a.logdir,a.unknown_recent_minutes); busy=[x for x in statuses if x.status.startswith(BUSY_PREFIXES)]; idle=[x for x in statuses if x not in busy]
    result={"safe":not busy,"busy_count":len(busy),"idle_count":len(idle),"busy":[asdict(x) for x in busy],"idle":[asdict(x) for x in idle]}
    print(json.dumps(result,ensure_ascii=False,indent=2) if a.json else f"safe={not busy} busy={len(busy)} idle={len(idle)}")
    return 0 if not busy else 10
if __name__ == "__main__": sys.exit(main())
