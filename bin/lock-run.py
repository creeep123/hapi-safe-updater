#!/usr/bin/env python3
import fcntl, os, subprocess, sys
lock=sys.argv[1]
os.makedirs(os.path.dirname(lock),exist_ok=True)
with open(lock,"a+") as fp:
    try: fcntl.flock(fp,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:
        print("another update is running")
        raise SystemExit(0)
    raise SystemExit(subprocess.call(sys.argv[2:]))
