# HAPI Safe Updater — Control Panel

## Current state

- **2026-09-25 fleet override:** automatic production upgrades remain paused. The deployment identities, enabled-timer statements and snapshot-restore guidance below are historical, not authority to replace the current maintained fleet or restore an old database. Component-specific release verification and a separately authorized production window are required.
- Companion PR #41 merged: independently verified main commit `75f335aac9f6f806e23d6f3acd22994a4aecfa5e`, patch SHA-256 `0134292bf4f6dd2743bf17ad991c1be6ce61515041757447015ee97d67586c68`, baseline `0239edf38e2da653d662f31039e24ccea04c7837`. Authorized candidate pin is recorded separately in [`companion-patched-hub.candidate.json`](../pins/companion-patched-hub.candidate.json); installed/default pin remains unchanged. Local full tests, build, isolated Companion runtime and local package-restoration gates passed. **Production NO-GO:** Linux/VM runtime and rollback, fleet component reconciliation, separate switch authorization and real Edge PWA acceptance remain pending. Full evidence and artifact hashes: [PR41 candidate report](PR41_CANDIDATE_20260925.md). Earlier PR heads are audit history only.

- Fresh-user and repository-link handoffs enter through `docs/agents/NEW_INSTALL.md`, which connects this updater to HAPI Companion without merging project ownership.
- The updater supports source builds, patch replay, offline npm-tree rollback, Hub health checks, and Runner reconnection checks.
- The HAPI Companion production constraint was **not** previously represented as a first-class gate.
- Required-patch identity, immutable dependency-install policy, isolated Companion candidate verification, and binary-integrity rollback checks are implemented on the default branch; production adoption remains a separate rollout task.
- Bun lockfile compatibility is handled explicitly: the V0.5 pin uses `no-save`, then verifies the committed `bun.lock` digest and all package manifests remain unchanged. It never falls back to a mutable install.
- Linux scheduled candidate builds run in a separate updater service with percentage-based memory/swap limits and `OOMPolicy=stop`; resource exhaustion must kill the candidate build, not production Hub/Runner.
- The repository now includes a credential-safe staged Runner smoke verifier (`bin/verify-runner-smoke.py`) covering auth, active-machine lookup, Codex models, spawn, message acceptance, and agent reply. Its isolated HTTP-contract tests assert that secrets and response bodies never enter output.

## Mac Runner handoff (2026-09-15)

- The live Mac scheduler has migrated to `io.hapi.safe-updater` under `~/.local/share/hapi-safe-updater`. The environment-B legacy label `cn.yangdexiong.hapi-auto-update` is unloaded and its plist, scripts, logs, and HAPI 0.29.0 rollback tree remain preserved for recovery; it is no longer in `~/Library/LaunchAgents` and therefore cannot race the new scheduler after login.
- The Mac profile uses unpatched source mode for the Runner only. It verifies the immutable upstream tag, frozen dependency install, Hub/CLI typechecks, executable build and candidate version before any future switch. The VM Companion-patched Hub remains a separate source-mode rollout and is not managed by this Mac profile.
- The reliable 2026-09-15 failure timeline is: candidate 0.30.6 Runner started at 04:21:22, machine registration at 04:21:23, `[API MACHINE] Connected to bot` at 04:21:24, and SIGTERM/rollback at 04:22:34. No `List Codex models request` or smoke session spawn appeared in the candidate log. The exact failing assertion remains unknown: evidence only bounds it to auth, machines, or models HTTP/assertion before spawn, and must not be narrowed further from the old log.
- An isolated upstream `v0.30.7` (`0239edf38e2da653d662f31039e24ccea04c7837`) Mac candidate passed dependency install, CLI/Hub typechecks, Codex model tests, tunwg acquisition, executable build, and version verification. Production was not replaced or restarted.
- `agent acp` (`executable="agent"`, `args=["acp"]`) is Cursor's ACP backend in this upstream release. The current Mac has no `agent` executable in either the interactive or Runner launchd PATH. After registration and `apiMachine.connect()`, Runner schedules Cursor model pre-warming in the background and catches its failure; this ENOENT is a diagnosable compatibility warning, not an established cause of the Codex smoke failure.
- The installed staged verifier now reports preflight/auth/machine/models/spawn/message/reply separately, retries transient 5xx/network failures without logging response bodies, and accepts the v0.30.7 wrapped session response. A real 0.30.7 Runner smoke passed every stage. The source candidate dry-run also passed without mutating the installed HAPI tree. Future post-switch failure remains fail-closed and invokes the updater rollback path.

## Production profile: VM HAPI Hub

- The VM Hub is a maintained patched build, not an unmodified upstream package.
- Recorded current production binary SHA-256: `324a88f0d5a9e11cbb401c845cfb5da1a8387380126ff752f64ba7b9231ad917`.
- Authoritative patch source: `/Users/mayuming/develop/hapi-companion/integrations/hapi/hapi-companion.patch`.
- Current immutable Companion commit: `5fb0db093a70a6c0ffcd51969404c39927ad7707` (merged PR #24; includes the Linux shared-Codex transport hotfix).
- Current HAPI baseline: `0239edf38e2da653d662f31039e24ccea04c7837` (`v0.30.7`).
- Current authoritative patch SHA-256: `2e75aa3ce6eaf7d965639d48feff3f0dc7ff4352306b48a1c28de1a5d35f5757` (previous production patch: `f7492b0fb2614f0963c473007b1c3910eab80aa04bb2ab44dc96613fa8c5dd5b`).
- The first patched v0.30.7 production switch completed at 2026-09-15 21:35 with binary SHA-256 `a7026c767f4d46ae252d44b69bc08a30fc8dd013383d93b238a6aec070025954` and schema v27, but its Linux Runner could not complete Codex session webhooks because Bun 1.3.13 terminated the Unix-socket WebSocket connection. The cumulative PR #24 patch selects authenticated loopback TCP on Linux/Windows and must pass a real Linux app-server initialize plus Runner spawn/message/reply before production replacement.
- The PR #24 transport hotfix was deployed on 2026-09-16 after all Linux candidate gates passed. Production binary SHA-256 is `88f986cd4bf857145b251f41e79df7343e6cd3ec99c58e2016c7c4a869243859`; Hub and Runner are active, schema remains v27, the production Companion contract passed, and a real Codex Runner smoke passed auth/machine/models/spawn/message/reply. A verified v27 database snapshot and the prior complete package tree are retained for rollback. Real Mac Companion notification delivery remains a separate human acceptance step.
- Machine-readable pin: [`docs/pins/companion-patched-hub.json`](../pins/companion-patched-hub.json).
- The candidate keeps Companion envelope version 1 and adds `kind=input-request`; the existing Mac client decodes `kind` as a string. It retains title, body, requestId, and exact same-origin `/sessions/<UUID>` routing.
- Production remains on schema v27. Hotfix rollback restores the pre-hotfix v27 database snapshot together with the prior complete Hub build and embedded web assets.
- The patch remains owned by HAPI Companion. The updater owns replay, validation, switching, and rollback.

## Mandatory release gate

Before replacing production, the updater must:

1. resolve the exact upstream release and apply the required Companion patch;
2. reject a missing patch, checksum drift, or apply conflict;
3. build and test an isolated candidate;
4. verify `/health`, unauthenticated `/companion/sessions` returns `401`, the authenticated device session-catalog JSON contract, `/companion/events` first `connected` frame, and ACK behavior without saving or logging credentials;
5. verify the rollback snapshot and current production binary identity;
6. after switching, verify Hub health and Runner recovery;
7. restore the complete previous installation tree and verify its original binary SHA-256 if any post-switch check fails.

## Do not do

- Do not use package mode for the patched production Hub.
- Do not silently fetch an arbitrary patch from a mutable URL.
- Do not reuse production Companion device credentials for candidate tests.
- Do not store tokens in config, logs, fixtures, shell history, or this repository.
- Do not implement updater orchestration inside `hapi-companion`.

## Open decision

The portable isolated candidate-Hub harness is implemented at `bin/verify-companion-candidate.py` and has passed on the Mac-built candidate. Its candidate binary path, ephemeral port, temporary database, device registration, catalog, SSE and ACK flow still must be exercised on the VM before enabling unattended upgrades.

Also choose and test the VM database snapshot/restore commands. The Companion schema migration is forward-only, so restoring only the old executable tree is not a sufficient rollback once a migration has run.
