# Native ARM Linux container chain — partial evidence

Date: 2026-09-25, Asia/Shanghai. **ARM CONTAINER PARTIAL PASS; PRODUCTION NO-GO remains.**

## What actually ran

On this Mac's existing local Colima Docker daemon (Linux aarch64, 2 CPUs, approximately 2 GiB RAM), a newly compiled ARM HAPI executable ran a fresh Hub and Runner. Installed real **Codex 0.154.0 ARM Linux** ran behind HAPI's authenticated loopback TCP app-server transport. A Python fixture, not a model service, answered one Responses request.

Successful sequence, observed through real APIs/processes:

1. Isolation, artifact hash and executable version checks passed.
2. Hub `/health` 200; synthetic `/api/auth` exchange 200; unauthenticated `/companion/sessions` 401.
3. Exactly one temporary active machine registered through the real Runner.
4. Runner model discovery returned six models, without sending any request to the fixture.
5. Hub spawn returned a session; the real Runner's spawn/webhook path completed and the session was active with the expected machine identity. `/proc` showed real Codex app-server using loopback WebSocket and capability-token flags. Token values were never printed.
6. A unique synthetic user message was accepted by Hub.
7. The real Codex process issued exactly one request to the local fixture. The fixture checks path, bounded body, model, stream flag, nonce, absence of Authorization, and refuses extra accepted calls. It has no forwarding implementation.
8. Hub returned the exact fixture text in an agent `codex/message` envelope with sequence greater than the matching user's localId; session thinking ended.
9. Container exit was 0, OOM=false; the exact temporary container was removed. Its tmpfs held all test state/credentials and was destroyed. No database or credential files were exported.

A second independent fresh-state run forced fixture HTTP 400. The real chain surfaced a Codex error, ended thinking, and did **not** produce the success reply. Exactly one fixture request was made; zero accepted. This negative scenario passed; it is not an actual model-provider availability test.

The initial implementation passed both scenarios. The final launcher was hardened to explicitly address only the current user's local `.colima/default/docker.sock` (not a mutable/remote Docker context), and added cgroup CPU/PID checks and peak-memory reporting. The final positive run passed again with peak memory **818,905,088 bytes** (about 781 MiB), under the unchanged 1 GiB container cap. An attempt to repeat the negative scenario with that final image returned `other_containers_running_defer` before creating a test container: another session's testcontainers workload was using Docker. It was not stopped or inspected beyond aggregate container status. After that workload naturally exited, a fresh empty-daemon check allowed the final negative scenario to run: **PASS**, one rejected fixture request, no success reply, thinking=false, container exit=0/OOM=false, peak **855,146,496 bytes** (about 816 MiB). Its container was removed. Thus both scenarios passed with the final image; the temporary defer is retained as evidence that contention protection was exercised.

## Immutable sources and hashes

- HAPI baseline: `0239edf38e2da653d662f31039e24ccea04c7837`, v0.30.7.
- Companion main source: `75f335aac9f6f806e23d6f3acd22994a4aecfa5e`.
- Cumulative patch SHA-256: `0134292bf4f6dd2743bf17ad991c1be6ce61515041757447015ee97d67586c68`.
- Build: Bun **1.3.14**, existing isolated exact-baseline+patch source, official executable script with `--target bun-linux-arm64 --with-web-assets`. Patch reverse apply-check passed; tracked bun.lock and root/CLI/Hub/Web/Shared/Relay package manifests remained unchanged. Previously recorded full-source test results were not rerun or relabeled as ARM tests.

| Artifact | SHA-256 |
| --- | --- |
| ARM HAPI all-in-one | `b708a7f499e7ed59d89c9882c1cfa7bb9a8771af666fc4b61f0ca3e0fd4503bf` |
| Codex ARM executable | `9b7c1c7abdc26fc3c4f47c77656a8e9121def5483dbae830ef1ee561758448a9` |
| Codex npm archive | `a2315b5f64bfeaff79b71e0d35505ba8c22cc1e96cab9dc950b614c804105b24` |
| ARM tunwg | `d2d29afda075e26bb70140184b5ee6c8a8cf56b18f1fe56db3c002d7dbe5eef9` |

Codex source: `https://registry.npmjs.org/@openai/codex/-/codex-0.154.0-linux-arm64.tgz`. The official package alias was resolved from `@openai/codex@0.154.0`. Complete archive SHA-512 matched registry integrity exactly:
`KmTCB6ST484zeYlPpKP/K5P/gRaYmt6TihVD+zotoe6O9q0JSBP+FYvCz4A/zZXR7xDOHURTSjHp0sD8wWS0YQ==`.
Truncated download attempts were rejected; only the verified complete archive was extracted. All vendor resources, including code-mode-host, bwrap, zsh and rg, were packaged; no npm install/lifecycle script was run.

tunwg source was resolved to the fixed release URL `https://github.com/tiann/tunwg/releases/download/v26.08.03+122a6d0/tunwg-arm64`. Its downloaded bytes were locally hashed and embedded; no independent upstream signed checksum was obtained, so do not describe this as signature/attestation verification. ELF checks confirmed HAPI, Codex and tunwg are ARM aarch64. tunwg was not launched and no tunnel was opened.

Base image: `python:3.12-slim-bookworm`, digest `sha256:392307d22300de8b5986851a12d9176dfc0fc073e65bf6523ebd7dcbeb23564e`, arm64. A dedicated preparation container installed only public Debian `procps` / `libproc2-0` version `2:4.0.2-3` (HAPI requires actual `ps` for process generation checks). This preparation had package-download network access, no host mounts or test credentials, 256 MiB/0.5 CPU/64 PID limits. Test programs were copied only after preparation exited. No production filesystem was copied.

Final tested image: `sha256:cff8251f500bc4bf9a5705c41f20dca18c3568ce9b54c120e3dbfcda95b9c10b`. Initial successful test image: `sha256:7dae74471bf5f71f4a60cafc0c337ff1dedef2b082fab98b929b8d462a5b3350`.

Durable local public artifacts (not installed):
`/Users/mayuming/.hapi/maintenance/candidates/companion-pr41-75f335aa/arm-linux-partial/`
contains `hapi-linux-arm64`, `codex-0.154.0-linux-arm64.tgz`, `tunwg-arm64-linux`.
The existing Darwin/x86 candidates and both pins were not replaced.

## Isolation and test implementation

`bin/verify-arm-container.py` is separate from install/update entry points. Host mode accepts only an immutable image ID and uses the local Colima socket. It refuses to start if another container is running, checks created container mount/network configuration, and imposes a 240-second deadline with exact-container cleanup. No SSH, systemd, deployment, scheduler, host process kill or image pull is implemented.

Execution: `--network none`, no mounts or published ports, read-only root, non-root UID 65534, all capabilities dropped, no-new-privileges, 1 GiB memory/no extra swap, 0.75 CPU, 128 PIDs, 192 MiB `/work` tmpfs plus 32 MiB `/tmp` tmpfs, Docker logging disabled. Worker checks loopback-only interfaces, outbound denial to a documentation-reserved IP, effective capabilities, no-new-privileges, cgroup limits, hidden host paths and environment allowlist before any HAPI/Codex launch. Child environment is explicitly constructed, not inherited from this HAPI maintenance conversation. All fixture/test auth and DB state are synthetic.

Worker stdout is structured non-sensitive summaries only. Child stdout/stderr are suppressed; application-created test logs stay in bounded tmpfs and are destroyed. Host cleanup removes only its freshly created random-name container; no broad prune. Container exit destroys any detached descendants too; this is **container lifecycle cleanup**, not proof of production Runner graceful control takeover.

TDD unit tests cover fail-closed container arguments/image references, fixed-local-daemon selection, fixture auth/model/nonce/repeated-call rejection, and exact sequenced agent-message acceptance (reject missing user, stale sequence, wrong nonce and error envelope). Four new tests passed; full updater suite: **33 tests, 31 passed / 2 opt-in Mac real-Codex tests skipped**. `git diff --check` is required before archival. Unit-test fake responses are not being substituted for the real container runs above.

Codex provider configuration follows [official advanced configuration](https://learn.chatgpt.com/docs/config-file/config-advanced): explicit custom provider with loopback base URL, Responses wire protocol, no required OpenAI auth and zero retries. Network isolation, not configuration alone, enforces no external model access.

## Not proven / unchanged release blockers

- Not VM x86_64 executable acceptance, native-x86 memory behavior, Bun 1.3.13 equivalence, systemd isolation/startup/recovery or real VM rollback.
- Not fleet replay/child-status/Hub override equivalence. This baseline+Companion artifact must not replace maintained fleet packages.
- No same-database matched-package rollback ran on ARM; no compatible prior ARM package was supplied. No schema downgrade or stale DB restoration.
- No full Companion SSE/ACK/replay/namespace/input-request gate in this run, no Sidecar shadow, no real notification or Edge PWA click. The one unauthenticated endpoint check is not full Companion acceptance.
- Fake provider proves transport, request/reply projection and error propagation, not real model/account entitlements, model quality, tool execution, paid-provider compatibility or all failure modes.

No VM/production endpoints, production credentials/configuration/DB, installed pin, automatic upgrade or PR timers were accessed or changed. Colima memory/configuration was not changed. **No production authorization is implied.**

## Cleanup and rerun preparation

All this task's execution containers were removed by the launcher; the named preparation container and all three dedicated ARM test images (initial, final, preflight) were also explicitly removed after evidence collection. No `hsu-arm` containers remained. Removal of the public Python base image was refused because another session's container references it; it was deliberately retained, without force or touching that container. No broad prune was used. Public downloads/build outputs and the durable artifacts above remain recoverable/reusable; no synthetic DB/auth/logs were saved.

For a later authorized rerun, rebuild a disposable image rather than expecting the removed image ID to exist. Use the pinned ARM Python base and real procps package; extract the integrity-verified Codex archive's `package/vendor/aarch64-unknown-linux-musl` tree into `/opt/gate` (keep `bin`, `codex-resources`, `codex-path` layout). Add only the recorded ARM candidate as `/opt/gate/hapi`, this repository's `bin/verify-arm-container.py` as `/opt/gate/verify-arm-container.py`, and a public `/opt/gate/artifacts.json` containing the `hapi`/`codex` hashes above. Never copy an entire user/repository directory or account config. Record the newly built immutable image ID and invoke:

```text
python3 bin/verify-arm-container.py --image sha256:<new-image-id>
python3 bin/verify-arm-container.py --image sha256:<new-image-id> --fail-provider
```

These commands cannot pull/install/deploy and will refuse concurrent Docker workloads. Rebuilding a test image does not authorize increasing Colima resources, accessing VM/production, changing pins or using a real provider.
