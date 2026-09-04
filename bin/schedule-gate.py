#!/usr/bin/env python3
"""Timezone-correct every-N-calendar-days gate with catch-up and retry."""
import argparse, datetime as dt, json, os, subprocess, sys
from zoneinfo import ZoneInfo

def load(path):
    try:
        with open(path) as fp: return json.load(fp)
    except Exception: return {}

def save(path,data):
    os.makedirs(os.path.dirname(path),exist_ok=True); tmp=path+".tmp"
    with open(tmp,"w") as fp: json.dump(data,fp)
    os.replace(tmp,path)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--state",required=True); ap.add_argument("--timezone",default="Asia/Shanghai"); ap.add_argument("--hour",type=int,default=4); ap.add_argument("--days",type=int,default=2); ap.add_argument("--catch-up-hours",type=int,default=20); ap.add_argument("command",nargs=argparse.REMAINDER); a=ap.parse_args()
    now=dt.datetime.now(ZoneInfo(a.timezone)); state=load(a.state)
    try: last=dt.datetime.fromisoformat(state["last_completed"])
    except Exception: last=None
    due_date=(last.date()+dt.timedelta(days=max(1,a.days))) if last else now.date()
    due=dt.datetime.combine(due_date,dt.time(a.hour),tzinfo=now.tzinfo)
    # Overdue runs are allowed immediately. This prevents a long sleep/offline
    # period from leaving the scheduler permanently behind an expired window.
    if now < due: return 0
    try: retry=dt.datetime.fromisoformat(state["retry_after"])
    except Exception: retry=None
    if retry and now < retry: return 0
    cmd=a.command[1:] if a.command and a.command[0]=="--" else a.command
    if not cmd: return 2
    rc=subprocess.call(cmd); state["last_result"]=rc; state["last_attempt"]=now.isoformat()
    if rc==0: state["last_completed"]=now.isoformat(); state.pop("retry_after",None)
    else: state["retry_after"]=(now+dt.timedelta(hours=1 if rc==75 else 6)).isoformat()
    save(a.state,state); return 0 if rc==75 else rc
if __name__ == "__main__": sys.exit(main())
