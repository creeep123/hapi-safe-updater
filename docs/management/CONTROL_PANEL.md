# HAPI Safe Updater — Control Panel

## Current state

- Fresh-user and repository-link handoffs enter through `docs/agents/NEW_INSTALL.md`, which connects this updater to HAPI Companion without merging project ownership.
- The updater supports source builds, patch replay, offline npm-tree rollback, Hub health checks, and Runner reconnection checks.
- The HAPI Companion production constraint was **not** previously represented as a first-class gate.
- Required-patch identity, immutable dependency-install policy, isolated Companion candidate verification, and binary-integrity rollback checks are implemented on the default branch; production adoption remains a separate rollout task.
- Bun lockfile compatibility is handled explicitly: the V0.5 pin uses `no-save`, then verifies the committed `bun.lock` digest and all package manifests remain unchanged. It never falls back to a mutable install.
- Linux scheduled candidate builds run in a separate updater service with percentage-based memory/swap limits and `OOMPolicy=stop`; resource exhaustion must kill the candidate build, not production Hub/Runner.

## Production profile: VM HAPI Hub

- The VM Hub is a maintained patched build, not an unmodified upstream package.
- Recorded production binary SHA-256: `324a88f0d5a9e11cbb401c845cfb5da1a8387380126ff752f64ba7b9231ad917`.
- Authoritative patch source: `/Users/mayuming/develop/hapi-companion/integrations/hapi/hapi-companion.patch`.
- Current immutable Companion commit: `b4033aa30f39` (PR #16).
- Target HAPI baseline: `d3d4fd1706564782e9a58b917df4e0677f65051f` (`v0.29.0-2-gd3d4fd17`; 0.29.0 reference).
- Current authoritative patch SHA-256: `399b6afc8e5ec1b6ad2a32152b3008905f697c42d68ca2325b4489e1ae60b0cf` (previous: `2a96be323c0d837793d32fd20fffc44efd6828e6a9263da5ebffcc5cf79e95bd`).
- Machine-readable pin: [`docs/pins/companion-patched-hub.json`](../pins/companion-patched-hub.json).
- V0.5 delta is limited to embedded PWA launch behavior (`focus-existing` → `navigate-existing`) and exact same-origin `/sessions/<UUID>` routing. Hub API, Relay contract, and database schema/migrations are unchanged.
- This transition must replace/restore the complete Hub build together with its embedded web assets; it has no database rollback step.
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
