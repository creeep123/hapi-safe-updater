# Implement and deploy the Companion-patched Hub profile

Status: in progress — repository gates implemented; VM candidate harness and rollout pending.

## Scope

- [x] Record production binary and authoritative patch identities.
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
- Current patch SHA-256: `2a96be323c0d837793d32fd20fffc44efd6828e6a9263da5ebffcc5cf79e95bd`.
- Patch authority remains HAPI Companion; updater implementation remains in this repository.

## Verification commands

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
bash tests/integration-source.sh
bash tests/integration-package.sh
```

Current branch evidence (2026-09-08): 13 Python tests passed; source-mode required-patch/candidate/integrity integration passed; package install and rollback integration passed; `git diff --check` passed. No production service or credential was touched.
