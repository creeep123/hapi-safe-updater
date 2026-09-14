# Implement and deploy the Companion-patched Hub profile

Status: in progress — repository gates implemented; VM candidate harness and rollout pending.

## Scope

- [x] Record production binary and authoritative patch identities.
- [x] Accept Companion V0.5 handoff: immutable commit `b4033aa30f39`, baseline `d3d4fd1706564782e9a58b917df4e0677f65051f`, and patch SHA-256 `399b6afc8e5ec1b6ad2a32152b3008905f697c42d68ca2325b4489e1ae60b0cf`.
- [x] Fail closed on required-patch absence or checksum drift.
- [x] Add a mandatory isolated candidate verification hook before production mutation.
- [x] Capture and verify deployed-binary integrity through rollback.
- [x] Add configuration validation and integration tests for the new gates.
- [x] Verify the pinned Companion patch applies to upstream `v0.29.0` (`240ab2f0535eadbb0a3f51b287c7ed04f405f34a`) with an isolated Git index.
- [x] Publish an updater-side fresh-install entry that cross-links Companion and forbids premature completion claims.
- [ ] Build the VM-specific isolated Hub harness for `/health`, `401`, authenticated device session-catalog JSON, SSE `connected`, and ACK.
- [ ] Add and drill VM database snapshot/restore commands for the forward-only Companion schema migration.
- [ ] Configure the VM to source the patch from an audited HAPI Companion checkout.
- [ ] Run dry-run and destructive rollback drill against a disposable VM/staging copy.
- [ ] Enable the profile in production only after the drill passes.

## Production facts

- Current VM production binary SHA-256: `324a88f0d5a9e11cbb401c845cfb5da1a8387380126ff752f64ba7b9231ad917`.
- Current patch SHA-256: `399b6afc8e5ec1b6ad2a32152b3008905f697c42d68ca2325b4489e1ae60b0cf` (previous: `2a96be323c0d837793d32fd20fffc44efd6828e6a9263da5ebffcc5cf79e95bd`).
- Current Companion commit: `b4033aa30f39`; HAPI baseline: `d3d4fd1706564782e9a58b917df4e0677f65051f`.
- V0.5 changes embedded Web/PWA navigation only. Hub API, Relay contract, and DB schema/migrations are unchanged; deploy and roll back Hub plus embedded Web assets as one unit.
- Patch authority remains HAPI Companion; updater implementation remains in this repository.

## Verification commands

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
bash tests/integration-source.sh
bash tests/integration-package.sh
```

Current branch evidence (2026-09-08): 13 Python tests passed; source-mode required-patch/candidate/integrity integration passed; package install and rollback integration passed; `git diff --check` passed. No production service or credential was touched.

V0.5 pin acceptance (2026-09-14): local immutable Companion commit resolved to `b4033aa30f39efdfdd5fa9bf1263e826d03a9416`; patch SHA-256 matched `399b6afc8e5ec1b6ad2a32152b3008905f697c42d68ca2325b4489e1ae60b0cf`; clean `d3d4fd17` cached apply-check passed. The isolated patched tree passed CLI 2,412/1 skip, Hub 1,216/3 skip, Web 2,798, Shared 283, Relay 80, root typecheck/build, and host single-executable build (`f8017bdab8b8fdb0b43896239b246a964aa42ee8f5c3f126cd3de84095f7861a`). Updater tests passed (14 Python plus source/package integrations). VM-specific live candidate endpoint/ACK, production switch, Hub/Runner recovery, and rollback were not run; production remained untouched. The current Bun 1.3.14 rejects the baseline lockfile under `--frozen-lockfile`, so unattended source-mode construction remains fail-closed until the VM uses a compatible pinned Bun or the install policy is separately reviewed.
