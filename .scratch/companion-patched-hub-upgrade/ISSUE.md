# Implement and deploy the Companion-patched Hub profile

Status as of 2026-09-25: PR #41 main merge independently verified; authorized local candidate gates PASS, production NO-GO. Automatic production upgrades remain paused. Earlier rollout/timer facts below are historical.

## Authorized merged-main candidate verification — supersedes handoff-only status

- Candidate source: main merge `75f335aac9f6f806e23d6f3acd22994a4aecfa5e`, independently fetched/read; patch SHA `0134292bf4f6dd2743bf17ad991c1be6ce61515041757447015ee97d67586c68` verified.
- Separate candidate pin: `docs/pins/companion-patched-hub.candidate.json`. Default/installed pin and production unchanged.
- Updater 19 tests + source/package fixture integrations PASS. Clean baseline apply/frozen install/lock+manifest invariants, full HAPI tests/typecheck/build PASS. Darwin isolated contract PASS. Local staging old→candidate→old package drill and restored hash/contract PASS; not a VM or same-live-DB rehearsal.
- Darwin artifact SHA `db6ea7d51c3fe7c487ce10808af98d5d01a5d781c9f2964601ff496e88b2dd4d`; Linux x64-baseline SHA `1d09cc25c6cf789641a7b70ae160c0ae743b8fd0ee924ae1e8ad5e664a8bb869`.
- Still blocked for production by fleet-composition reconciliation, Linux runtime/real Runner verification, VM rollback and separately authorized shadow/switch. Current candidate is baseline+Companion only, not a replacement for current fleet repair builds. Do not restore old DB for this Web-only change.
- Detailed evidence and limitations: `docs/management/PR41_CANDIDATE_20260925.md`.

## 2026-09-25 PR #41 handoff history — superseded above

- Source: https://github.com/creeep123/hapi-companion/pull/41
- Candidate immutable Companion PR head (latest handoff): `2d5e150c8c5b54d909579d74396d34d8a0216322`.
- Previous PR head: `cf59704a8f02d2eab2941a41492929766e2fffbf`. Companion reports the latest documentation-review commit only clarifies Control Panel wording, with patch bytes, baseline and prior test evidence unchanged. This is supplier-reported provenance, not a fresh updater gate result; historical tests remain attributed to their tested commits.
- Tested implementation parent: `adc9fa1b563ed7c56e072f14631956d33268c63f`. Companion reports the second commit only records updater acknowledgement and leaves patch bytes unchanged; this metadata correction is not independent source verification.
- While PR #41 remains open, use the current immutable PR head for candidate provenance. After any merge, independently reverify the exact patch blob and record the resulting main commit before a production pin; do not silently promote the PR head to production provenance.
- Patch path: `integrations/hapi/hapi-companion.patch`.
- Existing updater pin: `5fb0db093a70a6c0ffcd51969404c39927ad7707`, SHA-256 `2e75aa3ce6eaf7d965639d48feff3f0dc7ff4352306b48a1c28de1a5d35f5757` (unchanged).
- Proposed cumulative patch SHA-256: `0134292bf4f6dd2743bf17ad991c1be6ce61515041757447015ee97d67586c68`.
- Exact HAPI baseline: `0239edf38e2da653d662f31039e24ccea04c7837` (v0.30.7).
- Companion reports only embedded Web PWA UUID version acceptance 1–8 plus v7 regression changed; no API/DB/migration/Linux transport/Sidecar change, schema remains v27.
- Supplier-reported evidence, NOT updater independently rerun: regression red/green, clean apply, full root tests with `NODE_OPTIONS=--no-experimental-webstorage`, full typecheck/build, package/lock invariant and diff check passed.
- Additional Companion-reported validation at immutable PR head `cf59704a8f02d2eab2941a41492929766e2fffbf`: Mac xcodegen plus xcodebuild macOS tests passed, 75 tests / 0 failures, including SessionOpener tests. Reported patch SHA-256 remains `0134292bf4f6dd2743bf17ad991c1be6ce61515041757447015ee97d67586c68`. Not independently rerun by updater; no pin or production change, and real post-deployment Edge PWA click acceptance remains pending.
- [x] Record receipt and existing pin; retain paused-production boundary.
- [ ] After integration authorization, independently verify immutable Git-object patch bytes and exact delta, then update repository pin with source provenance.
- [ ] Reconcile the current fleet's separate replay/child-status, Hub override, transport and embedded-Web components; changing a required pin does not prove deployed equivalence and must not discard fleet repairs.
- [ ] Run isolated candidate gates, including PWA UUID-v7 regression, full configured contract/runtime and Runner gates; report immutable updater commit and actual results.
- [ ] Prepare a matched Hub + embedded-Web rollback package; preserve schema-v27 database. This Web-only hotfix does not authorize a DB downgrade or automatic old-snapshot restore.
- [ ] Obtain separate production authorization; keep automatic upgrades paused.
- [ ] After authorized deployment, human verifies real Edge PWA exact-session click. Automated routing tests cannot replace this gate.

Acknowledgement performed documentation-only: no pin/config/production/timer changes; no candidate gate run and no integration-acceptance claim.

## Scope

- [x] Record production binary and authoritative patch identities.
- [x] Accept Companion V0.5 handoff: immutable commit `b4033aa30f39`, baseline `d3d4fd1706564782e9a58b917df4e0677f65051f`, and patch SHA-256 `399b6afc8e5ec1b6ad2a32152b3008905f697c42d68ca2325b4489e1ae60b0cf`.
- [x] Accept the Linux transport hotfix handoff: immutable merged Companion commit `5fb0db093a70a6c0ffcd51969404c39927ad7707`, exact baseline `0239edf38e2da653d662f31039e24ccea04c7837`, and cumulative patch SHA-256 `2e75aa3ce6eaf7d965639d48feff3f0dc7ff4352306b48a1c28de1a5d35f5757`.
- [x] Fail closed on required-patch absence or checksum drift.
- [x] Add a mandatory isolated candidate verification hook before production mutation.
- [x] Capture and verify deployed-binary integrity through rollback.
- [x] Add configuration validation and integration tests for the new gates.
- [x] Verify the pinned Companion patch applies to upstream `v0.29.0` (`240ab2f0535eadbb0a3f51b287c7ed04f405f34a`) with an isolated Git index.
- [x] Publish an updater-side fresh-install entry that cross-links Companion and forbids premature completion claims.
- [x] Build the portable isolated Hub harness for `/health`, `401`, authenticated device session-catalog JSON, SSE `connected`, isolated event, and ACK.
- [x] Execute that harness against the Linux candidate on the VM before production enablement.
- [x] Add VM database snapshot/restore commands and capture a verified pre-hotfix schema-v27 rollback snapshot.
- [x] Configure the VM to source the immutable, checksum-verified Companion patch.
- [ ] Run dry-run and destructive rollback drill against a disposable VM/staging copy.
- [x] Enable the profile in production only after the candidate and rollback gates pass.

## Production facts

- Current VM production binary SHA-256: `88f986cd4bf857145b251f41e79df7343e6cd3ec99c58e2016c7c4a869243859`.
- Current patch SHA-256: `2e75aa3ce6eaf7d965639d48feff3f0dc7ff4352306b48a1c28de1a5d35f5757` (previous: `f7492b0fb2614f0963c473007b1c3910eab80aa04bb2ab44dc96613fa8c5dd5b`).
- Current Companion commit: `5fb0db093a70a6c0ffcd51969404c39927ad7707`; HAPI baseline: `0239edf38e2da653d662f31039e24ccea04c7837`.
- Candidate Companion commit: `5fb0db093a70a6c0ffcd51969404c39927ad7707`; HAPI baseline: `0239edf38e2da653d662f31039e24ccea04c7837` (`v0.30.7`).
- Candidate patch SHA-256: `2e75aa3ce6eaf7d965639d48feff3f0dc7ff4352306b48a1c28de1a5d35f5757`.
- Clean macOS cross-build evidence: exact baseline patch apply and frozen install passed with dependency manifests unchanged; Shared `320/0`, Relay `118/0`, embedded Web build passed; Linux x64-baseline candidate SHA-256 is `7c5d50a43f65bb8571c78360fc776a90fb5a939f2bd7be4817006614d7697b0c`. This does not replace the pending Linux VM runtime gate.
- V0.5 changes embedded Web/PWA navigation only. Hub API, Relay contract, and DB schema/migrations are unchanged; deploy and roll back Hub plus embedded Web assets as one unit.
- Patch authority remains HAPI Companion; updater implementation remains in this repository.
- VM evidence on 2026-09-16: the real Linux transport integration passed with Bun 1.3.13 and Codex CLI 0.154.0; CLI, Hub, Shared, Relay and Web suites passed (`Web 3183/3183`); full typecheck/build and the isolated Companion candidate gate passed. The updater captured a verified schema-v27 rollback snapshot, switched the complete Hub/embedded-Web tree, and passed the production Companion contract. A real Runner smoke passed auth, machine, models, Codex spawn, message and reply. Hub and Runner are active; schema remains v27; `/health` is 200 and unauthenticated Companion endpoints are 401. The new Safe Updater timer is enabled and the legacy timer remains disabled.

## Verification commands

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
bash tests/integration-source.sh
bash tests/integration-package.sh
```

Current branch evidence (2026-09-08): 13 Python tests passed; source-mode required-patch/candidate/integrity integration passed; package install and rollback integration passed; `git diff --check` passed. No production service or credential was touched.

V0.5 pin acceptance (2026-09-14): local immutable Companion commit resolved to `b4033aa30f39efdfdd5fa9bf1263e826d03a9416`; patch SHA-256 matched `399b6afc8e5ec1b6ad2a32152b3008905f697c42d68ca2325b4489e1ae60b0cf`; clean `d3d4fd17` cached apply-check passed. The isolated patched tree passed CLI 2,412/1 skip, Hub 1,216/3 skip, Web 2,798, Shared 283, Relay 80, root typecheck/build, and host single-executable build (`445afefd49cf1c6953aa8abc6b9202207cf6aea8f1d4c14624e94d4ffcc4eee4`). Updater tests passed (15 Python plus source/package integrations). VM-specific live candidate endpoint/ACK, production switch, Hub/Runner recovery, and rollback were not run; production remained untouched. Bun 1.3.14 rejects the baseline lockfile under `--frozen-lockfile`; the reviewed resolution is an explicit pin to `BUN_INSTALL_MODE=no-save`, followed by pre/post `bun.lock` SHA-256 equality and zero package-manifest changes. There is no automatic fallback. A clean isolated candidate built under this policy and the portable runtime harness passed `/health`, both unauthenticated 401 checks, ephemeral device registration, catalog JSON, SSE `connected` first frame, isolated notification and ACK cursor advancement. Production remained untouched.


VM candidate note (2026-09-14): Linux candidate SHA-256 `9c0e8e8b86044be3980fa048f18db48ad27b80183cc81815f3d913e4f06f6a8f` passed the portable runtime gate. Because the verification was launched from a HAPI peer, its build inherited the production Runner cgroup and the Runner was OOM-killed once, then automatically recovered. Hub PID, production binary SHA and DB inode remained unchanged. This is not the deployment topology used by the updater; the updater systemd template now isolates builds with `MemoryHigh=40%`, `MemoryMax=50%`, `MemorySwapMax=10%`, `OOMPolicy=stop`, and elevated OOM victim preference. Installing that updated unit remains a production/configuration action and was not performed.
