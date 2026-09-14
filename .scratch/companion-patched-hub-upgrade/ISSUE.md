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
- [x] Build the portable isolated Hub harness for `/health`, `401`, authenticated device session-catalog JSON, SSE `connected`, isolated event, and ACK.
- [ ] Execute that harness against the Linux candidate on the VM before production enablement.
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

V0.5 pin acceptance (2026-09-14): local immutable Companion commit resolved to `b4033aa30f39efdfdd5fa9bf1263e826d03a9416`; patch SHA-256 matched `399b6afc8e5ec1b6ad2a32152b3008905f697c42d68ca2325b4489e1ae60b0cf`; clean `d3d4fd17` cached apply-check passed. The isolated patched tree passed CLI 2,412/1 skip, Hub 1,216/3 skip, Web 2,798, Shared 283, Relay 80, root typecheck/build, and host single-executable build (`445afefd49cf1c6953aa8abc6b9202207cf6aea8f1d4c14624e94d4ffcc4eee4`). Updater tests passed (15 Python plus source/package integrations). VM-specific live candidate endpoint/ACK, production switch, Hub/Runner recovery, and rollback were not run; production remained untouched. Bun 1.3.14 rejects the baseline lockfile under `--frozen-lockfile`; the reviewed resolution is an explicit pin to `BUN_INSTALL_MODE=no-save`, followed by pre/post `bun.lock` SHA-256 equality and zero package-manifest changes. There is no automatic fallback. A clean isolated candidate built under this policy and the portable runtime harness passed `/health`, both unauthenticated 401 checks, ephemeral device registration, catalog JSON, SSE `connected` first frame, isolated notification and ACK cursor advancement. Production remained untouched.


VM candidate note (2026-09-14): Linux candidate SHA-256 `9c0e8e8b86044be3980fa048f18db48ad27b80183cc81815f3d913e4f06f6a8f` passed the portable runtime gate. Because the verification was launched from a HAPI peer, its build inherited the production Runner cgroup and the Runner was OOM-killed once, then automatically recovered. Hub PID, production binary SHA and DB inode remained unchanged. This is not the deployment topology used by the updater; the updater systemd template now isolates builds with `MemoryHigh=40%`, `MemoryMax=50%`, `MemorySwapMax=10%`, `OOMPolicy=stop`, and elevated OOM victim preference. Installing that updated unit remains a production/configuration action and was not performed.
