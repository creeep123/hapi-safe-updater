# Fleet upgrade pause — read-only recheck

Checked 2026-09-25 18:07:12–18:07:17 Asia/Shanghai. No upgrade, install, test workload, enable/disable, configuration write or restart was executed on any production host. Only local report creation followed read-only commands.

| Host | Evidence freshness | Result |
| --- | --- | --- |
| MacAir | Measured today 18:07:12 | `io.hapi.safe-updater` persistently disabled and not loaded; plist retained. Legacy `cn.yangdexiong.hapi-auto-update` not loaded and plist absent from LaunchAgents. Its launchd disabled-map entry says enabled, so do not describe the legacy label as persistently disabled; it is currently absent from autoload. Runner launchd job running, supervisor PID57048. |
| VM | Measured today 18:07:17 via read-only SSH/systemctl show | `hapi-safe-updater.timer` loaded but disabled/inactive/dead. Updater service inactive/dead, MainPID0, UnitFileState static. Hub active/running PID1494840; Runner active/running PID1494842. Neither restarted by this task. |
| UU Mac | Historical owner report, 2026-09-17 20:03; not remeasured today | Shared updater disabled/unloaded, covering both HAPI installations; configs retained. Owner reported both Runners still running. No claim of a fresh UU host measurement. |

Scope: checks cover the identified schedulers, not an exhaustive audit of every possible manual upgrade entry or proof of no unrelated changes by other operators.

Production-change clarification: no production modifications during this recheck or the current candidate/plan work. Historically, this session did apply the separately authorized Mac Runner workspace-root change on 2026-09-24; it must not be described as never having changed production. No current production binary/pin/database change or automatic-upgrade restoration was performed.

Historical evidence: `/Users/mayuming/.hapi/maintenance/FLEET-REPAIR.md`, section “最终暂停验收（2026-09-17 20:03）”. Authorized 9/24 Runner change evidence: `/Users/mayuming/.hapi/maintenance/WORKSPACE-ROOT-FINAL-20260924.md`.

Updater code HEAD during this recheck: `c10736014ea0fca57d400df3c097ba2e5ac6f913` (offline Linux plan candidate). This report is a new local document, not evidence embedded in that existing commit. VM isolated tests and production deployment remain pending separate authorization.
