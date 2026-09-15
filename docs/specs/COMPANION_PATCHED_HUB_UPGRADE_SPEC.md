# Companion-patched Hub upgrade gate

## Objective

Upgrade a production HAPI Hub that carries the HAPI Companion integration without ever replacing production with an unpatched or contract-incompatible build.

## Inputs

- Exact upstream HAPI tag and commit.
- `UPDATE_MODE=source`.
- `PATCH_DIR` containing the authoritative patch copy.
- `REQUIRED_PATCH_FILE` and `REQUIRED_PATCH_SHA256` pinning that copy.
- `REQUIRE_CANDIDATE_VERIFY=1` and `CANDIDATE_VERIFY_COMMAND` for an isolated candidate.
- `BINARY_INTEGRITY_PATH` identifying the deployed platform executable.
- `EXPECTED_CURRENT_BINARY_SHA256` for first adoption; thereafter the updater-maintained state hash is authoritative.

The authoritative patch is maintained by HAPI Companion at
`/Users/mayuming/develop/hapi-companion/integrations/hapi/hapi-companion.patch`.
The current immutable identity is recorded in [`docs/pins/companion-patched-hub.json`](../pins/companion-patched-hub.json). The configured `REQUIRED_PATCH_SHA256` must equal that record before candidate construction. It must be transferred to the VM through an audited source checkout or equivalent integrity-preserving step; credentials must not accompany it.

## Pre-mutation acceptance criteria

All checks run before service quiesce or production-tree mutation:

1. required patch exists inside `PATCH_DIR` and matches its pinned SHA-256;
2. patch applies cleanly, or is provably already upstream via reverse apply-check;
3. dependency installation consumes the committed lockfile without modifying it (`frozen`, or explicitly pinned `no-save` with pre/post lock hash and manifest checks);
4. Hub and CLI typechecks pass and the single executable builds;
5. the configured isolated-candidate command receives only:
   - `HSU_CANDIDATE_BIN`,
   - `HSU_WORKTREE`,
   - `HSU_TARGET_VERSION`;
6. the candidate harness uses an isolated temporary database/configuration and asserts:
   - `/health` succeeds;
   - unauthenticated `/companion/sessions` returns exactly `401`;
   - registration produces an ephemeral device credential with the expected fields and types;
   - authenticated `/companion/sessions` matches the minimal catalog contract: `capabilities.turnDuration` is boolean and every session projects only the allowed ID/title/optional machine/update/activity fields;
   - authenticated `/companion/events` begins with the `connected` SSE frame;
   - publishing an isolated test event and ACKing its `{seq,eventId}` succeeds and advances monotonically;
7. ephemeral credentials are held only in process memory or a mode-`0600` temporary file removed by the harness trap, never printed.
8. unacknowledged events replay after reconnect; cross-device and cross-namespace credentials or ACKs are rejected;
9. when the pin introduces schema v27, a production-database copy must preserve Companion rows and ACK cursors through v26→v27, and an old v26 binary may be started only after restoring a v26 backup.

Any failure exits before production mutation.

## Switch and rollback acceptance criteria

- Capture the complete installed npm tree (including embedded Web assets) and current binary SHA-256 before quiescing.
- The first managed run must match the configured production baseline SHA-256.
- Resume Hub then Runner in the configured order.
- Require post-switch `/health`, Companion verification command, and Runner reconnection.
- On failure, restore the complete previous tree offline and require the restored binary SHA-256 to equal the pre-update value.
- A failed rollback creates `ROLLBACK_FAILED` and freezes later scheduled updates.
- Because the Companion database migration is forward-only, production enablement also requires configured and drilled database snapshot/restore commands; binary-tree rollback alone is not enough after migration.
- The current v0.30.7 pin migrates v26→v27. Any rollback must restore the v26 database before the old executable is resumed; changing only `user_version` is forbidden.

## Non-goals

- Owning or modifying the Companion feature patch.
- Persisting production or device credentials.
- Treating unit tests alone as production endpoint verification.
