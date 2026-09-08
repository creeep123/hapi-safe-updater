# HAPI Safe Updater

跨 Linux/macOS、Hub/Runner 的安全自动更新器。它不是“发现新版本就直接重启”，而是只在**没有任务正在执行或输出**时更新；失败自动回滚，定制补丁不会在升级时静默丢失。

## 给 Agent 的一句话

> 请为我的 Mac 和自有服务器配置 HAPI 完成提醒及后续安全升级。先阅读本仓库的 AGENTS.md、README.md 和 `docs/agents/NEW_INSTALL.md`，并沿文档链接检查 HAPI Companion。识别已有安装、目标服务器和访问方式；安装 Mac Companion，验证服务器使用兼容补丁的 Hub，再配置 updater 的补丁 pin、候选验收和回滚。不要输出凭据，不要用无补丁的官方包覆盖 Hub；逐项报告实际验证结果和未完成项。

**全新 Mac + 自有服务器：必须先读 [新环境安装引导](docs/agents/NEW_INSTALL.md)。** 本项目负责安全升级；[HAPI Companion](https://github.com/creeep123/hapi-companion) 负责 Mac 提醒应用、Hub 权威补丁和接口契约。只安装本 updater 不会产生提醒，只安装 Companion 也不等于已经获得安全自动升级。

下面原有的 updater 安装命令只适用于已经确认 Hub 类型、补丁责任和回滚边界的环境，不能替代新环境端到端引导。

## 支持场景

| 场景 | Linux 云服务器 | Linux 本地服务器 | macOS 电脑 |
|---|---:|---:|---:|
| Hub | ✅ systemd user | ✅ systemd user | ✅ launchd |
| Runner | ✅ | ✅ | ✅ |
| Hub + Runner | ✅ | ✅ | ✅ |
| 官方 npm 包直接更新 | ✅ | ✅ | ✅ |
| 保留本地源码补丁 | ✅ | ✅ | ✅ |

## “没有活跃会话”的准确定义

这里的“活跃”是**任务活跃**，不是网页是否打开，也不是 runner/app-server 是否常驻。

以下任一成立即视为忙碌并跳过更新：

- 最新日志显示已经 `thinking started` / `item/started`，尚未完成或回到 `Waiting for messages`；
- 会话 `agent_state.requests` 仍有待处理请求；
- 最近运行中的会话缺少足够状态，无法证明它是空闲（fail closed）；
- runner-only 机器存在本地 HAPI agent 子进程，但没有 Hub 数据库可进一步证明其空闲。

浏览器页面开着、会话标记为 running、runner 常驻，本身都**不算忙碌**。

## 安装

前置条件：Python 3.9+、Node/npm、已安装的 `hapi`；源码补丁模式还需要 Git 与 Bun。Linux 方案要求 systemd user，若退出登录后仍需执行 timer，应运行 `sudo loginctl enable-linger "$USER"`。macOS 的 LaunchAgent 仅在用户登录后生效；机器睡眠时不会强行唤醒，但会在当天补跑窗口内恢复后执行。

```bash
git clone <THIS_REPOSITORY_URL>
cd hapi-safe-updater
./install.sh
$HOME/.local/share/hapi-safe-updater/bin/doctor
$HOME/.local/share/hapi-safe-updater/bin/hapi-safe-update --dry-run
```

安装器不会读取或复制 HAPI token。默认配置位于：

```text
~/.config/hapi-safe-updater/config.json
```

默认每两个北京时间日历日于 04:00 左右检查。systemd/launchd 每小时只唤醒一次轻量级时间门禁；04:00 后当天还有补跑窗口，睡眠或离线恢复后不会立即错过整轮。忙碌时一小时后再试，失败时六小时后再试。常驻资源占用为 0，平时一次唤醒通常不足一秒。

## 两种更新模式

### 1. 官方包模式（默认）

```json
{"UPDATE_MODE": "package"}
```

执行 `npm install -g @twsxtd/hapi@latest`，重启被检测到的 HAPI Hub/Runner，并验证版本和可选健康检查；失败则重装旧版本。

### 2. 保留本地修复

```json
{
  "UPDATE_MODE": "source",
  "SOURCE_REPO": "https://github.com/tiann/hapi.git",
  "PATCH_DIR": "~/.config/hapi-safe-updater/patches"
}
```

把补丁放进 `PATCH_DIR/*.patch`。每个新版本都会从对应 tag 创建干净 worktree、应用补丁、typecheck、构建，再切换。冲突时在安装前停止；若补丁已被上游合并，则自动识别并跳过。详见 [`patches/README.md`](patches/README.md)。

### 强制补丁与候选 Hub 门禁

生产 Hub 依赖某个补丁时，不要只依靠“目录里碰巧有一个 patch”。应同时锁定补丁文件及 SHA-256，并要求在覆盖生产前验证隔离候选：

```json
{
  "UPDATE_MODE": "source",
  "PATCH_DIR": "/path/to/audited/patches",
  "REQUIRED_PATCH_FILE": "/path/to/audited/patches/required.patch",
  "REQUIRED_PATCH_SHA256": "<64-hex-digest>",
  "REQUIRE_CANDIDATE_VERIFY": 1,
  "CANDIDATE_VERIFY_COMMAND": "/path/to/verify-isolated-candidate",
  "BINARY_INTEGRITY_PATH": "/path/to/deployed/platform/hapi",
  "EXPECTED_CURRENT_BINARY_SHA256": "<first-adoption-production-sha256>"
}
```

候选命令在生产服务停止、npm 安装树变化之前运行，可读取 `HSU_CANDIDATE_BIN`、`HSU_WORKTREE`、`HSU_TARGET_VERSION`。它必须自行使用隔离端口、临时数据库和临时凭据，且不得输出或持久化凭据。首次纳管核对配置中的生产 SHA；成功后由 updater state 跟踪下一版 SHA。回滚必须恢复并核对升级前的原始 SHA。

HAPI Companion patched Hub 的完整强制契约见 [`docs/specs/COMPANION_PATCHED_HUB_UPGRADE_SPEC.md`](docs/specs/COMPANION_PATCHED_HUB_UPGRADE_SPEC.md)。

## 配置 Hub / Runner

通常保持 `ROLE=auto` 即可。服务名符合 `hapi-hub.service`、`hapi-runner.service` 或 launchd label/path 含 hapi + hub/runner 时会自动重启。非标准部署请显式设置：

```json
{
  "ROLE": "hub+runner",
  "QUIESCE_COMMAND": "systemctl --user stop my-runner my-hub",
  "RESUME_COMMAND": "systemctl --user start my-hub my-runner",
  "HEALTHCHECK_URL": "http://127.0.0.1:8080/",
  "VERIFY_COMMAND": "systemctl --user is-active --quiet my-hub"
}
```

Runner-only Mac 示例：

```json
{
  "ROLE": "runner",
  "QUIESCE_COMMAND": "launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.example.hapi-runner.plist",
  "RESUME_COMMAND": "launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.example.hapi-runner.plist",
  "VERIFY_COMMAND": "launchctl print gui/$(id -u)/com.example.hapi-runner >/dev/null"
}
```

配置是严格 JSON，不会被当成 shell 代码加载；涉及自定义生命周期的 command 字段仍由 shell 执行，只能填写自己审核过的命令。文件权限由安装器设为 `600`。

## 运维命令

```bash
# 看当前忙闲判定及证据
~/.local/share/hapi-safe-updater/bin/hapi-idle-check.py --json

# 只检查是否有更新，不安装
~/.local/share/hapi-safe-updater/bin/hapi-safe-update --dry-run

# 手动执行，仍遵守忙闲门禁
~/.local/share/hapi-safe-updater/bin/hapi-safe-update

# 紧急人工维护才可绕过门禁
~/.local/share/hapi-safe-updater/bin/hapi-safe-update --force

# Linux 日志/计划
systemctl --user status hapi-safe-updater.timer
journalctl --user -u hapi-safe-updater.service -n 200

# macOS 状态
launchctl print gui/$(id -u)/io.hapi.safe-updater
```

## 安全与故障策略

1. 更新开始先检查；随后暂停 Hub/Runner，再检查一次。**边界：当前 HAPI 没有原生原子 maintenance/drain API**，默认 service stop 是 best-effort；Runner-only 若要求严格禁入，必须用 `QUIESCE_COMMAND`/`RESUME_COMMAND` 接入 Hub 侧摘流，并以 `VERIFY_COMMAND` 验证重新连接。项目不会把这个上游限制伪装成数学上的零竞态。
2. 文件锁防止重复更新。
3. 补丁冲突、构建失败、权限不足：切换前退出。
4. 安装后版本、`HEALTHCHECK_URL` 或 `VERIFY_COMMAND` 失败：恢复旧版本并重启。
5. 切换前会快照完整旧 npm 安装树（含平台 optional dependency）；回滚不依赖 registry 网络。恢复后会再次核对版本、服务和自定义健康验证，失败写入 `state/ROLLBACK_FAILED` 并以 70 退出，绝不伪称成功。
6. 不提交、不搬运 HAPI credentials/token；日志只记录状态和脱敏事件名。
7. `--force` 只允许人工执行，不用于定时任务。

若存在 `state/ROLLBACK_FAILED`，后续定时升级会永久 fail-closed。请人工恢复并完成版本、Hub 健康和 Runner 重连验证后，才可删除该标记。

## 卸载

```bash
./uninstall.sh
```

卸载只移除调度器，保留配置、日志和状态，便于审计。

## 当前来源说明

本项目由一套 Linux Hub+Runner 的 systemd 更新脚本和一套 macOS Runner 的 launchd 脚本归并而来。旧方案中硬编码的用户名、安装路径、Linux 平台二进制路径和特定补丁标记已改为自动检测/配置；原有“双重空闲检查、低优先级构建、更新后验证、失败回滚”原则被保留。

MIT License.
