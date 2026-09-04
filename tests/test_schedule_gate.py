import datetime as dt, importlib.util, json, os, sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

P=Path(__file__).parents[1]/"bin/schedule-gate.py"
s=importlib.util.spec_from_file_location("gate",P); m=importlib.util.module_from_spec(s); sys.modules["gate"]=m; s.loader.exec_module(m)

class Fixed(dt.datetime):
    value=None
    @classmethod
    def now(cls,tz=None): return cls.value.astimezone(tz)

class GateTests(unittest.TestCase):
    def setUp(self): self.t=tempfile.TemporaryDirectory(); self.state=str(Path(self.t.name)/"state.json"); self.now=dt.datetime(2026,9,5,12,tzinfo=ZoneInfo("Asia/Shanghai")); Fixed.value=self.now
    def tearDown(self): self.t.cleanup()
    def run_gate(self,rc=0,extra=None):
        argv=["gate","--state",self.state,"--timezone","Asia/Shanghai","--hour","4","--days","2","--catch-up-hours","20","--","true"]
        with patch.object(sys,"argv",argv), patch.object(m.dt,"datetime",Fixed), patch.object(m.subprocess,"call",return_value=rc) as call:
            result=m.main(); return result,call.call_count
    def test_catches_up_after_four_am(self):
        self.assertEqual(self.run_gate(),(0,1))
    def test_two_calendar_day_gate_not_exact_48_hours(self):
        Path(self.state).write_text(json.dumps({"last_completed":dt.datetime(2026,9,3,4,15,tzinfo=ZoneInfo("Asia/Shanghai")).isoformat()}))
        Fixed.value=dt.datetime(2026,9,5,4,0,tzinfo=ZoneInfo("Asia/Shanghai"))
        self.assertEqual(self.run_gate(),(0,1))
    def test_busy_retries_in_one_hour(self):
        self.assertEqual(self.run_gate(75),(0,1)); data=json.loads(Path(self.state).read_text()); self.assertIn("retry_after",data); self.assertNotIn("last_completed",data)
    def test_long_overdue_does_not_stall_forever(self):
        Path(self.state).write_text(json.dumps({"last_completed":dt.datetime(2026,8,1,4,tzinfo=ZoneInfo("Asia/Shanghai")).isoformat()}))
        self.assertEqual(self.run_gate(),(0,1))

if __name__=="__main__": unittest.main()
