# Implement and deploy the Companion-patched Hub profile

Status: in progress — HAPI v0.30.7 Linux candidate and database-copy rollback gates passed; production switch pending.

## Scope

- [x] Record production binary and authoritative patch identities.
- [x] Accept Companion HAPI v0.30.7 handoff: merge commit `940cb28a5642a5d536ea972cadf2aac25be27a72`, baseline `0239edf38e2da653d662f31039e24ccea04c7837`, and patch SHA-256 `f7492b0fb2614f0963c473007b1c3910eab80aa04bb2ab44dc96613fa8c5dd5b`.
- [x] Fail closed on required-patch absence or checksum drift.
- [x] Add a mandatory isolated candidate verification hook before production mutation.
- [x] Capture and verify deployed-binary integrity through rollback.
- [x] Add configuration validation and integration tests for the new gates.
- [x] Verify the pinned Companion patch applies to upstream `v0.29.0` (`240ab2f0535eadbb0a3f51b287c7ed04f405f34a`) with an isolated Git index.
- [x] Publish an updater-side fresh-install entry that cross-links Companion and forbids premature completion claims.
- [x] Build the portable isolated Hub harness for `/health`, `401`, authenticated device session-catalog JSON, SSE `connected`, isolated event, and ACK.
- [x] Execute the expanded harness against the Linux candidate on the VM before production enablement.
- [x] Add updater database snapshot/restore hooks and drill v26→v27 plus restored-v26 startup against production DB copies.
- [ ] Configure the VM to source the patch from an audited HAPI Companion checkout.
- [ ] Run dry-run and destructive rollback drill against a disposable VM/staging copy.
- [ ] Enable the profile in production only after the drill passes.

## Production facts

- Current VM production binary SHA-256: `324a88f0d5a9e11cbb401c845cfb5da1a8387380126ff752f64ba7b9231ad917`.
- Current patch SHA-256: `f7492b0fb2614f0963c473007b1c3910eab80aa04bb2ab44dc96613fa8c5dd5b` (previous: `399b6afc8e5ec1b6ad2a32152b3008905f697c42d68ca2325b4489e1ae60b0cf`).
- Current Companion commit: `940cb28a5642a5d536ea972cadf2aac25be27a72`; HAPI baseline: `0239edf38e2da653d662f31039e24ccea04c7837` (`v0.30.7`).
- Contract v1 adds `input-request`; schema v27 reconciles both v26 lineages. Rollback requires both the old complete build and restored v26 DB.
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

HAPI v0.30.7 VM acceptance (2026-09-15): exact baseline and patch applied cleanly under `bun install --frozen-lockfile`. CLI 2,802/7 skip, Hub 1,312/3 skip, Web 3,183, Shared 320 and Relay 118 passed; full typecheck and build passed. Linux candidate SHA-256 is `85eff68e137437db4ef577e38fb98432758d52c4399af61184ed7665901c8490`. The expanded isolated runtime gate passed health, both unauthenticated 401s, catalog types, schema v27, SSE connected/event, duration, ACK, reconnect replay, cross-device rejection and namespace isolation. A consistent production DB copy passed v26→v27 with Companion row/cursor preservation and the required upstream index; a separately restored v26 copy passed quick-check and startup under the old v26 binary. All heavy work ran in transient updater cgroups; production Hub/Runner remained active.
