# Companion PR #41 — updater candidate evidence, 2026-09-25

## Decision

Local source/candidate and isolated updater rollback gates PASS. Production NO-GO: fleet component reconciliation, Linux runtime/rollback evidence and separate VM shadow/switch authorization remain outstanding. No production binary, installed pin/config, database, Runner or scheduler was changed. No real user events were consumed.

The repository candidate pin is `docs/pins/companion-patched-hub.candidate.json`; the existing `companion-patched-hub.json` and installed configurations remain unchanged. The candidate file is deliberately not wired into an automatic installer.

## Independently verified source

- Fetched Companion main into a separate bare clone; main resolved to merge commit `75f335aac9f6f806e23d6f3acd22994a4aecfa5e` and ancestor check passed.
- Extracted `integrations/hapi/hapi-companion.patch` from that Git object (not the earlier PR head or a mutable working file).
- SHA-256: `0134292bf4f6dd2743bf17ad991c1be6ce61515041757447015ee97d67586c68`.
- Diff against prior pinned commit `5fb0db093a70a6c0ffcd51969404c39927ad7707` changes only the PWA launch-handler UUID version regex 1–5 → 1–8 and corresponding regression tests.
- Clean separate HAPI checkout at `0239edf38e2da653d662f31039e24ccea04c7837`: patch apply-check and apply passed.
- Bun 1.3.14 `install --frozen-lockfile` passed. Committed bun.lock and all tracked package manifests unchanged after tests/build. Full source diff check passed.

Git blob transfer initially disconnected; a successful retry preceded hash verification and application. tunwg downloader also encountered a network reset; Linux tunwg was downloaded separately and cached Darwin tunwg copied into the isolated tree. These do not constitute a fully reproducible external-tool supply chain. Recorded tool hashes: Darwin `4ff96e3ff7271a1bb940c8e7e071900d2135b483baab387d4f8ba8dc2ddd333a`; Linux `c1a7e08d956d9ee1087b8bf3b651d5dc32aee80eee1052c11218189fd5635768`.

## Tests actually run

- Updater Python unittest discovery: 19 passed.
- `tests/integration-source.sh`: PASS (isolated fake installation, required-patch hash rejection, lock mutation rejection, candidate-before-mutation, dry-run).
- `tests/integration-package.sh`: PASS (isolated fake installation, successful upgrade, failed verification rollback, rollback_failed freeze). Its v26/v27 fixture is not a real VM database rehearsal or permission to restore production snapshots.
- Full HAPI root tests with isolated test HOME/HAPI_HOME and `NODE_OPTIONS=--no-experimental-webstorage`: CLI 2805 passed/8 skipped; Hub 1312 passed/3 skipped; Web 3183 passed; Shared 320 passed; Relay 118 passed. Root command exit 0.
- Dedicated PWA launch-handler regression: 2 passed, covering UUID v7 and invalid routing.
- Full root typecheck and build: PASS.
- Darwin arm64 and Linux x64-baseline single-executable builds with embedded Web: PASS.
- Darwin `verify-companion-candidate.py`: PASS (temporary DB/device, health, exact unauthenticated 401s, auth/catalog, SSE connected/event, ACK/cursor, unacknowledged replay, cross-namespace and cross-device rejection). This existing harness is not a complete proof of every notification contract clause: it injects synthetic outbox events and does not perform a real Runner task, real input-request generation, or human PWA click.

## Isolated matched-binary rollback drill

Copied the current Mac self-contained executable (including embedded Web) into an isolated staging directory. No production installation was overwritten.

1. Prior package contract gate PASS.
2. Replace staging executable with the candidate; candidate contract gate PASS.
3. Restore staging executable from the prior copy; byte comparison and SHA PASS, restored contract gate PASS.

Restored SHA: `8ddd2822779f1a8a64b3bbb8cf17e821f0513305bfc0a776736d1b03ffa34ffb`.

Each contract invocation used its own disposable DB. This validates local package restoration, NOT preservation of a continuously written database, VM service rollback, or destructive VM rollback. Those remain unverified. For this Web-only delta, preserve schema27 and current data; do not downgrade user_version or automatically restore a stale DB snapshot.

## Candidate artifacts (not installed)

Directory: `/Users/mayuming/.hapi/maintenance/candidates/companion-pr41-75f335aa` (mode 0700).

| File | SHA-256 |
| --- | --- |
| hapi-darwin-arm64 | db6ea7d51c3fe7c487ce10808af98d5d01a5d781c9f2964601ff496e88b2dd4d |
| hapi-linux-x64-baseline | 1d09cc25c6cf789641a7b70ae160c0ae743b8fd0ee924ae1e8ad5e664a8bb869 |

Both contain the candidate embedded Web. These are baseline + Companion-only artifacts, NOT reconciled fleet release packages; never overwrite current replay/child-status/Hub-override builds with them merely because the patch SHA matches.

Working source and transient build/test logs: `/private/tmp/hsu-pr41-20260925.A9X3ny`; temporary storage is not durable release provenance. Immutable source IDs, hashes and summarized results above are the repository evidence.

## Production and remaining gates

- Read-only current Mac check: safe-updater persistently disabled; legacy job absent and legacy plist not in LaunchAgents. Its historical launchd enabled flag alone does not mean it is loaded.
- Read-only VM check: safe-updater timer disabled/inactive; Hub PID1494840 and Runner PID1494842 active. No restart performed.
- UU remains paused per prior owner evidence; this turn did not independently access UU or claim a fresh three-machine measurement.
- Reconcile current fleet ordered patches/final trees/artifacts and required capabilities before selecting a release package. Do not equate the old installed required pin with actual Hub override provenance.
- Linux real Codex transport test is skipped on Darwin by design. Linux runtime, actual Runner spawn/message/reply, VM rollback and production-equivalent Bun validation remain pending. This build used Bun 1.3.14; prior approved Linux evidence used 1.3.13 and does not validate this artifact.
- VM shadow and production switch require separate approval. All automatic production upgrades stay paused.
- After an approved deployment, real Edge PWA exact-session click remains a human acceptance gate.
