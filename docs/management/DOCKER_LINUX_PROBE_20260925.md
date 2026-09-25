# Local Docker Linux candidate feasibility — 2026-09-25

Later follow-up: native ARM container chain testing subsequently passed as **partial ARM evidence**; see `ARM_LINUX_CHAIN_20260925.md`. The x86-emulation failures below remain valid and are not superseded by ARM success.

Result: **BLOCKED before Hub/Runner startup; production NO-GO unchanged.**

## Scope and architecture

User authorized temporary local Docker execution with synthetic state, no host credentials/production mounts, no VM access and no paid model calls. Docker server reports Linux aarch64, 2 CPUs, 2,053,644,288 bytes memory. No running containers were reported before the probes.

The existing PR41 candidate is x86-64 ELF, dynamically linked through `/lib64/ld-linux-x86-64.so.2`. Its independently rechecked SHA-256 is `1d09cc25c6cf789641a7b70ae160c0ae743b8fd0ee924ae1e8ad5e664a8bb869`. It is not an ARM64 build and has not been substituted with one.

Public Debian bookworm-slim image digest: `sha256:3783cc01769c7b2b1b83a5c5ad96c815348e28ed7da68e2e3687004faa906251`. Pulled with a new empty Docker CLI config because the ordinary config referenced an unavailable docker-credential-desktop helper. No registry credentials were read or repaired. Daemon endpoint was the existing local Colima socket; that socket was never mounted into a container.

`--platform linux/amd64` plus `/bin/uname -m` returned `x86_64`. This establishes basic foreign-architecture execution, not native amd64 equivalence or a verified emulator implementation.

## Actual candidate probes

Only the candidate executable was copied into a never-started staging container and committed to a dedicated test image. No repository, HOME, Docker socket, credentials or production files were mounted/copied. The initial read-only staging copy was refused by Docker; an offline Docker build also failed with a content-digest-not-found error. Neither failure was treated as candidate evidence. The subsequently successful dedicated image was `sha256:007be1b678c5d2023ea321c34b6ee791bb52da01b7e2ecea13084efbb0a3bcbc`.

Both candidate invocations were only `hapi --version`, with:

- `--network none`, no published ports, no mounts;
- read-only root filesystem; dedicated 128 MiB `/tmp` tmpfs;
- user 65534:65534, all capabilities dropped, no-new-privileges;
- 0.5 CPU, 64 PID cap; memory+swap equal (no additional swap);
- synthetic HOME=/tmp/home and HAPI_HOME=/tmp/hapi, no host environment forwarding.

| UTC execution interval | Memory cap | Exit | Docker OOMKilled |
| --- | --- | --- | --- |
| 10:20:15.076–10:20:17.342 | 768 MiB | 137 | true |
| 10:20:33.659–10:20:39.441 | 1 GiB | 137 | true |

These times are 18:20 CST. Both exited with PID=0 and no version output. This is direct evidence of container memory-limit failure during candidate startup under foreign-architecture execution. It does **not** distinguish emulator overhead from Bun/runtime behavior, prove a candidate defect, or establish memory needs on native amd64 Linux.

No further limit increases were attempted on the approximately 2 GiB Docker VM. No Hub, Runner, Codex, provider or rollback test was started; no synthetic database was created. The TDD skill was consulted for potential harness work, but no test harness implementation or unit-test PASS is claimed for this feasibility probe.

## Remaining gates and next options

1. A resource-sufficient isolated amd64 environment must first run the exact candidate executable successfully. A separately approved Docker VM resource increase could permit another bounded probe; native amd64 removes this emulation variable. No host/Colima configuration was changed here.
2. The real Hub → Runner → installed Codex app-server → local non-forwarding fake provider worker, evidence collector and negative tests remain unimplemented as listed in `LINUX_CANDIDATE_PLAN_20260925.md`.
3. A verified compatible Linux rollback package is still required for same-synthetic-schema27 code rollback with message/cursor preservation. Do not use a Mac executable or the candidate itself as a false rollback target.
4. Current fleet replay/child-status/Hub override equivalence remains unresolved; this candidate must not replace maintained production components.
5. Even successful Docker tests would not replace VM/systemd/cgroup/topology acceptance or real Edge PWA human acceptance. No VM execution or production deployment authorization is inferred.

Active/default pin, production services/data, host credentials and automatic-upgrade pause settings were not changed. No paid provider or production API was contacted.

Cleanup: all three dedicated staging/runtime containers and the dedicated candidate image were removed after collecting the above observations. The earlier failed copy container was also removed. Public Debian image/cache and local temporary candidate copy/Dockerfile were retained; no broad Docker prune or deletion of pre-existing images was performed. Candidate artifacts remain intact at their original maintenance path, so the disposable image is reproducible. `git diff --check` passed; this report is local and has not been pushed.

## Follow-up cleanup and native ARM assessment

On the user's subsequent cleanup request, the named probe containers and dedicated image were confirmed absent. The Debian image pulled by this task was then also explicitly removed (`debian:bookworm-slim`, digest above); no force or prune was used. A newly visible `hapi-companion-linux-gate:local` image was not created by this session and was left untouched, as were the pre-existing postgres and ryuk images. Local evidence and original candidate artifacts remain preserved.

Native ARM Linux is a viable **partial-test design**, not yet a passed test. The exact-baseline build script explicitly supports `bun-linux-arm64`; ARM Linux difftastic and ripgrep archives exist in the isolated source tree. The recorded accepted artifacts currently contain only Darwin ARM64 and Linux x86-64, so a newly built and independently hashed ARM Linux executable would be a separate test artifact, not the VM candidate.

An immediate packaging gap was confirmed: `shared/tools/tunwg/tunwg-arm64-linux` is absent from the isolated source tree, but the ARM embedding code requires it. Its pinned public bytes must be acquired and verified before an all-in-one ARM build; an existing x86 helper must not be relabeled as ARM.

Useful native ARM coverage would include a real temporary Hub and Runner, real ARM Codex app-server loopback transport, and Hub message → Codex → non-forwarding local fake provider → Hub reply. Use synthetic HOME/DB/auth only, no host mounts, network none, read-only root, non-root UID, dropped capabilities and bounded memory/CPU/PIDs/time. Start with an executable/health probe and stop on OOM rather than increasing Colima resources. The existing full-chain worker/collector and ARM Codex packaging still need implementation; this assessment does not claim they exist or that these tests ran.

ARM results cannot establish x86-64 executable compatibility, VM memory requirements, systemd control/recovery, installed fleet component equivalence or VM rollback. Even an ARM synthetic-data rollback would only be ARM container evidence and require its own compatible ARM prior package. No native container, Colima configuration change, VM access or production mutation was performed during this follow-up assessment.
