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
It must be transferred to the VM through an audited source checkout or equivalent integrity-preserving step; credentials must not accompany it.

## Pre-mutation acceptance criteria

All checks run before service quiesce or production-tree mutation:

1. required patch exists inside `PATCH_DIR` and matches its pinned SHA-256;
2. patch applies cleanly, or is provably already upstream via reverse apply-check;
3. Hub and CLI typechecks pass and the single executable builds;
4. the configured isolated-candidate command receives only:
   - `HSU_CANDIDATE_BIN`,
   - `HSU_WORKTREE`,
   - `HSU_TARGET_VERSION`;
5. the candidate harness uses an isolated temporary database/configuration and asserts:
   - `/health` succeeds;
   - unauthenticated `/companion/sessions` returns exactly `401`;
   - registration response contains the expected device credential JSON fields and types;
   - authenticated `/companion/events` begins with the `connected` SSE frame;
   - publishing an isolated test event and ACKing its `{seq,eventId}` succeeds and advances monotonically;
6. ephemeral credentials are held only in process memory or a mode-`0600` temporary file removed by the harness trap, never printed.

Any failure exits before production mutation.

## Switch and rollback acceptance criteria

- Capture the complete installed npm tree and current binary SHA-256 before quiescing.
- The first managed run must match the configured production baseline SHA-256.
- Resume Hub then Runner in the configured order.
- Require post-switch `/health`, Companion verification command, and Runner reconnection.
- On failure, restore the complete previous tree offline and require the restored binary SHA-256 to equal the pre-update value.
- A failed rollback creates `ROLLBACK_FAILED` and freezes later scheduled updates.

## Non-goals

- Owning or modifying the Companion feature patch.
- Persisting production or device credentials.
- Treating unit tests alone as production endpoint verification.
