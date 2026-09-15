#!/usr/bin/env python3
"""Verify a Companion-patched HAPI candidate against an isolated local Hub.

Credentials exist only in process memory. Hub output is captured in a mode-0600
file inside the temporary directory and removed with that directory.
"""
import hashlib, json, os, secrets, signal, socket, sqlite3, subprocess, sys, tempfile, time, urllib.error, urllib.request, uuid
from pathlib import Path


def request(url, method="GET", headers=None, body=None, timeout=5):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type":"application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            return res.status, res.headers, res.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers, e.read()


def require(ok, stage):
    if not ok: raise RuntimeError(f"candidate gate failed: {stage}")


def read_frames(base, headers, count):
    req=urllib.request.Request(base+"/companion/events",headers=headers)
    with urllib.request.urlopen(req,timeout=5) as stream:
        require(stream.headers.get_content_type()=="text/event-stream","SSE content type")
        frames=[]; frame=[]
        while len(frames)<count:
            line=stream.readline().decode().rstrip("\r\n")
            if line: frame.append(line)
            elif frame: frames.append(frame); frame=[]
        return frames


def main():
    binary = Path(os.environ.get("HSU_CANDIDATE_BIN", ""))
    require(binary.is_file() and os.access(binary, os.X_OK), "candidate executable")
    with tempfile.TemporaryDirectory(prefix="hsu-companion-candidate-") as td:
        root=Path(td); home=root/"home"; home.mkdir(mode=0o700); db=root/"candidate.db"
        with socket.socket() as s:
            s.bind(("127.0.0.1",0)); port=s.getsockname()[1]
        access=secrets.token_urlsafe(32)
        env={**os.environ, "HOME":str(home), "HAPI_HOME":str(home/".hapi"), "DB_PATH":str(db),
             "CLI_API_TOKEN":access, "HAPI_LISTEN_HOST":"127.0.0.1", "HAPI_LISTEN_PORT":str(port),
             "HAPI_PUBLIC_URL":f"http://127.0.0.1:{port}", "HAPI_IOS_PUSH":"off",
             "TELEGRAM_NOTIFICATION":"false", "SERVERCHAN_NOTIFICATION":"false"}
        log=open(root/"hub.log","w", opener=lambda p,f: os.open(p,f,0o600))
        proc=subprocess.Popen([str(binary),"hub"],env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        base=f"http://127.0.0.1:{port}"
        try:
            deadline=time.time()+30
            while time.time()<deadline:
                try:
                    if request(base+"/health",timeout=1)[0]==200: break
                except Exception: pass
                require(proc.poll() is None,"Hub startup")
                time.sleep(.2)
            else: raise RuntimeError("candidate gate failed: /health timeout")
            require(request(base+"/companion/sessions")[0]==401,"unauthenticated sessions must be 401")
            require(request(base+"/companion/events")[0]==401,"unauthenticated events must be 401")
            st,_,raw=request(base+"/api/auth","POST",body={"accessToken":access})
            require(st==200,"ephemeral JWT exchange"); jwt=json.loads(raw)["token"]
            auth={"Authorization":f"Bearer {jwt}"}
            st,_,raw=request(base+"/api/companion/devices/register","POST",auth,{"installationId":str(uuid.uuid4()),"name":"Updater candidate"})
            require(st==200,"device registration"); reg=json.loads(raw)
            require(isinstance(reg.get("deviceId"),str) and isinstance(reg.get("token"),str) and isinstance(reg.get("lastAckSeq"),int),"device credential JSON contract")
            device={"Authorization":f"Bearer {reg['token']}","X-Hapi-Device-Id":reg["deviceId"]}
            st,_,raw=request(base+"/companion/sessions",headers=device)
            require(st==200,"authenticated session catalog"); catalog=json.loads(raw)
            require(isinstance(catalog.get("capabilities",{}).get("turnDuration"),bool) and isinstance(catalog.get("sessions"),list),"session catalog JSON contract")
            allowed={"id","title","machineName","updatedAt","active"}
            require(all(isinstance(x,dict) and set(x)<=allowed and isinstance(x.get("id"),str) and isinstance(x.get("title"),str) for x in catalog["sessions"]),"session catalog projection")
            with sqlite3.connect(db) as con:
                require(con.execute("PRAGMA user_version").fetchone()[0]==27,"schema v27")
            event_id=str(uuid.uuid4()); now=int(time.time()*1000)
            payload={"version":1,"eventId":event_id,"createdAt":now,"kind":"session-completed","title":"Candidate gate","body":"Isolated event","severity":"success","sessionId":str(uuid.uuid4()),"sessionName":"Candidate","url":"/sessions/"+str(uuid.uuid4()),"durationMs":1234}
            with sqlite3.connect(db) as con:
                cur=con.execute("INSERT INTO companion_notification_outbox(event_id,namespace,payload_json,created_at,expires_at) VALUES(?,?,?,?,?)",(event_id,"default",json.dumps(payload),now,now+60000)); seq=cur.lastrowid
            frames=read_frames(base,device,2)
            require(any(x=="event: connected" for x in frames[0]),"SSE connected first frame")
            require(any(x=="event: notification" for x in frames[1]) and any(x==f"id: {seq}" for x in frames[1]),"SSE isolated event")
            require(any('"durationMs":1234' in x for x in frames[1]),"durationMs contract")
            st,_,raw=request(base+"/companion/ack","POST",device,{"seq":seq,"eventId":event_id})
            require(st==200 and json.loads(raw).get("ok") is True,"ACK")
            with sqlite3.connect(db) as con: ack=con.execute("SELECT last_ack_seq FROM companion_devices WHERE id=?",(reg["deviceId"],)).fetchone()[0]
            require(ack==seq,"ACK cursor advancement")

            replay_id=str(uuid.uuid4()); foreign_id=str(uuid.uuid4()); replay_payload={**payload,"eventId":replay_id,"title":"Replay gate"}
            foreign_payload={**payload,"eventId":foreign_id,"title":"Foreign namespace"}
            foreign_device_id=str(uuid.uuid4()); foreign_token=secrets.token_urlsafe(32)
            with sqlite3.connect(db) as con:
                replay_seq=con.execute("INSERT INTO companion_notification_outbox(event_id,namespace,payload_json,created_at,expires_at) VALUES(?,?,?,?,?)",(replay_id,"default",json.dumps(replay_payload),now,now+60000)).lastrowid
                foreign_seq=con.execute("INSERT INTO companion_notification_outbox(event_id,namespace,payload_json,created_at,expires_at) VALUES(?,?,?,?,?)",(foreign_id,"other",json.dumps(foreign_payload),now,now+60000)).lastrowid
                con.execute("INSERT INTO companion_devices(id,installation_id,namespace,name,token_hash,created_at,updated_at,last_ack_seq,enabled) VALUES(?,?,?,?,?,?,?,?,1)",(foreign_device_id,str(uuid.uuid4()),"other","Foreign gate",hashlib.sha256(foreign_token.encode()).hexdigest(),now,now,0))
            replay_once=read_frames(base,device,2)
            replay_twice=read_frames(base,device,2)
            for observed in (replay_once,replay_twice):
                require(any(x==f"id: {replay_seq}" for x in observed[1]),"unacked event replay")
                require(not any(foreign_id in x for frame in observed for x in frame),"namespace stream isolation")
            foreign={"Authorization":f"Bearer {foreign_token}","X-Hapi-Device-Id":foreign_device_id}
            require(request(base+"/companion/ack","POST",device,{"seq":foreign_seq,"eventId":foreign_id})[0]==409,"cross-namespace ACK rejected")
            require(request(base+"/companion/ack","POST",foreign,{"seq":replay_seq,"eventId":replay_id})[0]==409,"foreign namespace ACK rejected")
            swapped={"Authorization":f"Bearer {foreign_token}","X-Hapi-Device-Id":reg["deviceId"]}
            require(request(base+"/companion/ack","POST",swapped,{"seq":replay_seq,"eventId":replay_id})[0]==401,"cross-device credential rejected")
            st,_,raw=request(base+"/companion/ack","POST",device,{"seq":replay_seq,"eventId":replay_id})
            require(st==200 and json.loads(raw).get("ok") is True,"replay ACK")
            with sqlite3.connect(db) as con:
                ack=con.execute("SELECT last_ack_seq FROM companion_devices WHERE id=?",(reg["deviceId"],)).fetchone()[0]
            require(ack==replay_seq,"monotonic replay ACK cursor")
            print("companion candidate gate: PASS")
        finally:
            if proc.poll() is None:
                os.killpg(proc.pid,signal.SIGTERM)
                try: proc.wait(timeout=5)
                except subprocess.TimeoutExpired: os.killpg(proc.pid,signal.SIGKILL); proc.wait()
            log.close()
    return 0

if __name__=="__main__":
    try: raise SystemExit(main())
    except Exception as e:
        print(str(e),file=sys.stderr); raise SystemExit(1)
