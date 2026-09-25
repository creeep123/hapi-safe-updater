# Linux isolation and full-stack test preparation (offline review candidate)

## Decision and boundaries

Can be prepared locally: strict plan generation, configuration validation, workflow ordering and negative assertions. Cannot honestly finish Linux runtime acceptance on this Mac without an approved Linux environment. No VM, SSH, production connection, real model account, installation, scheduler or production pin was accessed or changed during this task.

`bin/plan-linux-candidate.py` is a **non-executing plan compiler**, not a ready-to-run launcher. It has no execute flag, subprocess, SSH, service-manager invocation or production settings default. Status is always `PLAN_ONLY_NOT_EXECUTION_READY`. This deliberate stop boundary must not be removed merely to get a passing report.

## Implemented and locally tested

- Manifest accepts only a run ID, exact dedicated rootfs path, three artifact hash declarations and bounded memory/CPU/task/runtime limits. Rejects root/home/production paths, path traversal, unknown fields (including environment injection), missing/malformed hashes, booleans as integers and unlimited/excessive resources.
- Generates proposed systemd properties: separate minimal RootDirectory, PrivateNetwork, DynamicUser, protected home/system/proc/devices, no privilege escalation/capabilities, only a bounded writable temporary workspace, hard memory/no swap, CPU/task/runtime caps, control-group termination, no restart. No host directory bind or environment inheritance is requested.
- No executable command or unit installation is generated. Declared hashes are syntactically checked only; the future launcher must verify actual bytes, provenance, ownership, symlinks and ELF architecture before execution.
- Generated workflow: isolation probes → loopback fixture → fresh test Hub/schema27/auth → test Runner registration → real Codex app-server initialize → spawn/webhook → user message → fixture request → exact agent reply → completion → cleanup.
- `evaluate_observations` checks normalized evidence ordering, loopback-only distinct origins, exact API statuses, machine/session identity continuity, real Codex and webhook observations, one nonce-matched unauthenticated/non-forwarding provider request, an exact agent reply after the user sequence, completion and zero remaining test processes/listeners/secrets.
- Evaluation only returns `ASSERTIONS_PASS_NOT_RUNTIME_ATTESTATION` or `ASSERTIONS_FAIL`; productionApproved is always false. Synthetic JSON cannot establish Linux execution or prove that the evidence collector is trustworthy.
- Five local unit tests cover the proposed plan, 11 unsafe manifest variants, a valid synthetic transcript, 28 invalid chain variants plus missing evidence, and exclusion of synthetic inherited credentials. Red-before-green runs were observed for absent implementation and missing validation. Mac real-Codex/fixture tests are separate evidence, not this Linux gate.

Public interfaces tested are the plan compiler and normalized observation evaluator, as authorized for local preparation. They do not mock a Hub reply and call it end-to-end success.

## Still unimplemented / must not be silently assumed

1. **Reviewed Linux rootfs packager:** stage real HAPI/Codex plus their libraries/resources and Python worker, no account/host files. Record all hashes and reconcile fleet replay/child-status/Hub override components. Current baseline+Companion binary is not a production-equivalent replacement.
2. **Privileged transient launcher and Linux probes:** verify systemd/cgroup support, available headroom, mount tree, private network namespace/loopback, hidden production paths, empty credential environment and enforced resource caps. The properties are a proposal, not proof. Required isolation failures must abort; never fall back to ordinary user processes in the production Runner cgroup.
3. **Actual full-stack worker:** start the ephemeral Hub and real Runner with explicit test-only paths/auth; wait for readiness; select the fake provider/model through real Codex app-server config; resolve custom model-catalog behavior; then send a unique request via Hub. The Mac helper currently exercises `codex exec`, not this app-server/Runner path.
4. **Evidence collector:** normalize actual Hub/Runner/app-server/provider observations into the checked schema, with PID/executable hashes and namespace/cgroup identity. Read credentials only from ephemeral in-memory/test state; never call the existing production-default Runner smoke verifier without explicit isolated replacements. No response/body/token logs. Proposed unit stdout/stderr is null; a safe bounded summary collection channel still needs implementation and review.
5. **Failure scenarios:** provider error/disconnect, spawn/webhook timeout, malformed/stale/wrong-session reply, remaining child process/listener, cleanup failure. Whole-test cgroup cleanup needs Linux verification and must never target production units/PIDs.
6. **Actual notification cases:** completion/ready and input-request must originate from the test Codex interaction. Existing synthetic outbox checks and normalized transcript unit tests do not establish these events, permission semantics or real notification delivery.
7. **Linux matched-package rollback:** retain synthetic schema27 messages/cursors while switching test code back to a verified compatible prior package. Do not restore an older production DB or lower user_version. No destructive VM drill is claimed.

No stage above is marked complete by the local five tests. We stop at offline reviewable preparation pending separate Linux execution authorization; real-account/paid-model tests, Sidecar shadow, production switching and automatic-upgrade enablement are separate and remain unauthorized.

## Example review-only invocation

Provide a reviewed JSON manifest with fields:
`runId`, `rootfs`, `artifactHashes` (`hapi`, `codex`, `rollback`), `memoryMaxMiB`, `cpuQuotaPercent`, `runtimeMaxSeconds`, `tasksMax`.

For runId `review-001`, rootfs must be exactly `/var/tmp/hsu-linux-candidate-review-001/rootfs`. No directory is created or inspected by the compiler.

`python3 bin/plan-linux-candidate.py --manifest /path/to/review-only-manifest.json`

This prints a non-executable review plan. It does not reserve resources, create a unit or start tests.

Systemd semantics were checked against official source documentation:
https://raw.githubusercontent.com/systemd/systemd/v255/man/systemd.exec.xml
The target VM's actual supported properties/kernel isolation are deliberately not inferred from that document.
