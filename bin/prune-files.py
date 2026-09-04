#!/usr/bin/env python3
import glob, os, sys
keep=max(0,int(sys.argv[1])); files=[]
for pattern in sys.argv[2:]: files.extend(glob.glob(os.path.expanduser(pattern)))
for p in sorted(set(files),key=os.path.getmtime,reverse=True)[keep:]:
    try: os.unlink(p)
    except FileNotFoundError: pass
