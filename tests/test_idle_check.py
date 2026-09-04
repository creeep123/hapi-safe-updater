import importlib.util, json, sqlite3, sys, tempfile, time, unittest
from pathlib import Path

P=Path(__file__).parents[1]/"bin/hapi-idle-check.py"
s=importlib.util.spec_from_file_location("idle",P); m=importlib.util.module_from_spec(s); sys.modules["idle"]=m; s.loader.exec_module(m)

def make_db(tmp, metadata, state):
    p=tmp/"hapi.db"; c=sqlite3.connect(p); c.execute("create table sessions(id text, metadata text, agent_state text, updated_at integer)"); c.execute("insert into sessions values(?,?,?,?)",("s",json.dumps(metadata),json.dumps(state),int(time.time()*1000))); c.commit(); return str(p)

class IdleTests(unittest.TestCase):
    def setUp(self): self.t=tempfile.TemporaryDirectory(); self.tmp=Path(self.t.name); self.old=m.agent_pids; m.agent_pids=lambda:{123}
    def tearDown(self): m.agent_pids=self.old; self.t.cleanup()
    def test_pending_request_is_busy(self):
        p=make_db(self.tmp,{"flavor":"codex","hostPid":123,"lifecycleState":"running"},{"requests":{"x":{}}})
        self.assertEqual(m.collect(p,str(self.tmp),15)[0].status,"busy_pending_request")
    def test_open_but_waiting_is_idle(self):
        (self.tmp/"x-pid-123.log").write_text("[12:00:00.000] thinking started\n[12:00:01.000] thinking completed\n[12:00:01.001] [MessageQueue2] Waiting for messages...\n")
        p=make_db(self.tmp,{"flavor":"codex","hostPid":123,"lifecycleState":"running"},{})
        self.assertEqual(m.collect(p,str(self.tmp),15)[0].status,"idle_waiting")
    def test_remote_steering_is_busy_without_local_log(self):
        m.agent_pids=lambda:set()
        p=make_db(self.tmp,{"flavor":"codex","hostPid":999,"lifecycleState":"running"},{"steeringActive":True,"requests":{}})
        self.assertEqual(m.collect(p,str(self.tmp),15)[0].status,"busy_steering_active")
    def test_live_old_process_without_log_stays_unknown(self):
        p=make_db(self.tmp,{"flavor":"codex","hostPid":123,"lifecycleState":"running"},{"steeringActive":False})
        c=sqlite3.connect(p); c.execute("update sessions set updated_at=?",(int((time.time()-3600)*1000),)); c.commit()
        self.assertEqual(m.collect(p,str(self.tmp),15)[0].status,"unknown_live_no_log")
    def test_user_text_cannot_fake_completion(self):
        (self.tmp/"x-pid-123.log").write_text("[12:00:00.000] thinking started\nuser said thinking completed\n")
        p=make_db(self.tmp,{"flavor":"codex","hostPid":123,"lifecycleState":"running"},{"steeringActive":False})
        self.assertEqual(m.collect(p,str(self.tmp),15)[0].status,"busy_executing")
    def test_unknown_flavor_fails_closed(self):
        p=make_db(self.tmp,{"flavor":"future-agent","hostPid":123,"lifecycleState":"running"},{})
        self.assertEqual(m.collect(p,str(self.tmp),15)[0].status,"unknown_flavor")

if __name__ == "__main__": unittest.main()
