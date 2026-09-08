# HAPI Safe Updater — Control Panel

## Current state

- The updater supports source builds, patch replay, offline npm-tree rollback, Hub health checks, and Runner reconnection checks.
- The HAPI Companion production constraint was **not** previously represented as a first-class gate.
- Required-patch identity, pre-mutation candidate verification, and binary-integrity rollback checks are now implemented on the working branch; production adoption remains a separate rollout task.

## Production profile: VM HAPI Hub

- The VM Hub is a maintained patched build, not an unmodified upstream package.
- Recorded production binary SHA-256: `324a88f0d5a9e11cbb401c845cfb5da1a8387380126ff752f64ba7b9231ad917`.
- Authoritative patch source: `/Users/mayuming/develop/hapi-companion/integrations/hapi/hapi-companion.patch`.
- Current authoritative patch SHA-256: `2a96be323c0d837793d32fd20fffc44efd6828e6a9263da5ebffcc5cf79e95bd`.
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

Choose the VM's isolated candidate-Hub harness: ephemeral JWT/device registration against a temporary database is preferred, but its exact start command, port allocation, and database path must be validated on the VM before enabling unattended upgrades.

Also choose and test the VM database snapshot/restore commands. The Companion schema migration is forward-only, so restoring only the old executable tree is not a sufficient rollback once a migration has run.
