# 新 Mac + 自有服务器：Agent 安装入口

把下面这段话和本仓库地址交给新用户的 Agent 即可开始：

> 请为我的 Mac 和自有服务器配置 HAPI 完成提醒及后续安全升级。先阅读本仓库 AGENTS.md、README.md 和 `docs/agents/NEW_INSTALL.md`，再沿文档链接阅读 HAPI Companion 的新环境引导。识别已有安装、目标服务器和访问方式；安装 Mac Companion，验证服务器使用兼容补丁的 Hub，再配置 updater 的补丁 pin、隔离候选验收与回滚。不要输出凭据，不要直接用无补丁的官方包覆盖 Hub。逐项报告实际验证结果和未完成项。

入口仓库：<https://github.com/creeep123/hapi-safe-updater>

## 三个组成部分

1. **Mac HAPI Companion** 负责原生通知、声音及精确会话跳转。
2. **带 Companion 补丁的 HAPI Hub** 负责设备注册、会话目录、SSE 通知与 ACK；补丁及接口契约由 [HAPI Companion](https://github.com/creeep123/hapi-companion) 维护。
3. **HAPI Safe Updater** 负责在升级 Hub/Runner 时重放并锁定补丁、验证隔离候选、切换服务及失败回滚。Updater 不参与日常提醒事件传输。

两个项目必须保持边界：Companion 仓库拥有应用、权威 Hub 补丁和契约测试；本仓库拥有自动升级、pin、候选门禁和回滚。不得把 updater 实现写回 Companion。

## Agent 执行顺序

1. **阅读两边入口。** 阅读本仓库的 `AGENTS.md`、`README.md`、Control Panel 和 patched-Hub spec；随后阅读 Companion 的 [`docs/agents/NEW_INSTALL.md`](https://github.com/creeep123/hapi-companion/blob/main/docs/agents/NEW_INSTALL.md)、README、AGENTS 及 Hub integration 文档。不要假定未合并分支已经存在于默认分支。
2. **盘点环境。** 确认 Mac、服务器、Hub、Runner、HAPI/Codex 版本、服务管理方式和现有补丁来源。不得展示完整配置、token、Keychain 或设备凭据。没有服务器访问权时可以准备 Mac，但必须把服务器部分列为未完成。
3. **先准备兼容 Hub。** 从明确的上游 HAPI tag/commit 构建；使用 Companion 仓库中已验收的权威 patch，并核对不可变 Companion commit 和 patch SHA-256。已有生产 Hub 必须先识别当前二进制、数据库和回滚目标。
4. **配置 updater。** Patched Hub 必须使用 `UPDATE_MODE=source`，设置 `REQUIRED_PATCH_FILE`、`REQUIRED_PATCH_SHA256`、`REQUIRE_CANDIDATE_VERIFY=1`、`CANDIDATE_VERIFY_COMMAND`、`BINARY_INTEGRITY_PATH` 及首次纳管 SHA。补丁文件必须来自审计过的 Companion checkout 或等价的完整性保护传输。
5. **完成生产前候选验收。** 在隔离端口和临时数据库上验证 `/health`、未认证 `/companion/sessions=401`、设备认证后的最小目录 JSON、`/companion/events` 的 `connected` 首帧及 ACK。临时凭据只能存在于进程内存或由 trap 清除的 `0600` 临时文件，不得打印或保存。
6. **准备回滚。** 验证完整 npm 安装树、当前二进制 SHA-256、Hub 数据库快照和恢复命令，并在 disposable/staging 环境做一次失败回滚演练。Companion 数据库迁移可能是前向的，只有二进制备份不够。
7. **获得生产切换授权。** `doctor`、dry-run 或候选构建成功不等于允许修改生产。只有用户明确批准后才能执行切换；切换后必须复验 Hub、Companion 契约和 Runner 恢复。任一失败立即回滚；回滚失败写入冻结标记，禁止后续无人值守升级。
8. **安装和验收 Mac Companion。** 按 Companion 文档安装，完成通知权限、声音、Edge PWA 精确跳转和真实任务完成通知。Mac 应连接同一个已验收 Hub。
9. **交付可审计记录。** 报告 Companion 版本/安装路径、Hub 上游 commit、patch commit/SHA、生产及回滚二进制身份、数据库快照、updater commit/config pin、每项门禁实测结果和所有未完成项；不得记录凭据。

## 不得提前宣称完成

以下任一存在时，必须明确写“未完成”或“尚未部署”，不能说整套已经安装完成：

- updater 能力只在工作分支或 PR，尚未进入新用户可访问的默认分支；
- VM/服务器仍运行无补丁 Hub，或 patch commit/SHA 未 pin；
- 隔离候选没有执行完整 Companion HTTP/SSE/ACK 契约；
- 数据库备份、恢复或失败回滚演练未通过；
- updater 尚未实际安装并启用调度器；
- Mac 只显示“已连接”，但真实完成提醒、声音或精确跳转未验收；
- Hub/Runner 恢复没有实际证明。

## 完成定义

提醒闭环要求 **Mac Companion + 兼容补丁 Hub**。安全升级要求另加 **已部署并通过门禁的 Safe Updater**。三者可以分阶段交付，但必须分别报告状态，不能把代码存在、dry-run、候选测试或其中一个组件成功混称为端到端完成。
