# Local fake-provider preparation — no VM execution

## Scope and result

Authorized local preparation only. No SSH/VM process, production HAPI connection, account login, paid inference, installed configuration change or scheduler operation was performed for this task.

`bin/verify-local-codex-provider.py` runs the installed real Codex executable against a Python HTTP Responses/SSE fixture. It does not mock Codex output or bypass Codex by posting an assistant reply to Hub.

Local command used real Codex 0.156.1 at:
`/opt/homebrew/lib/node_modules/@openai/codex/node_modules/@openai/codex-darwin-arm64/vendor/aarch64-apple-darwin/bin/codex`.

Five tests passed with explicit `HSU_RUN_LOCAL_CODEX_TEST=1` opt-in:

1. Synthetic account/token/proxy environment cannot leak into the child.
2. Real Codex sends one nonce-bearing request to the fixture and emits its reply as an `item.completed` agent message.
3. Fixture HTTP failure causes a non-successful Codex execution, not a passing reply; temporary server/state cleaned up.
4. Linux refuses this Mac-only adapter before starting any process; no unsandboxed fallback.
5. Forced timeout of a synthetic test process reaps that process; no production PID is targeted.

Two tests use the actual local Codex; normal unittest discovery skips them unless explicitly opted in. TDD evidence: environment test initially failed on absent implementation, then passed; real seam test initially failed on missing adapter, isolation syntax, then blocked system-proxy routing, and passed only after explicit test-only proxy isolation. No external network allowance was added to obtain a pass.

## Isolation actually exercised

- New private temporary HOME/CODEX_HOME/HAPI_HOME and working directory for every run. Child environment is constructed from a fixed allowlist, not inherited. No account file, production config or SSH agent socket copied.
- macOS sandbox applies to the Codex process and descendants. Outbound network is denied except the fixture's single localhost port. User-directory reads and writes outside the temporary root are denied; securityd lookup is denied. No application tools are requested or supplied by the fixture.
- Before starting Codex, a sandboxed probe must connect to the allowed fixture port, receive PermissionError on a different listening loopback port, and receive PermissionError reading the public repository script under `/Users`. No real credential file is read as a probe.
- Discovery: Codex/reqwest consulted macOS system proxy `127.0.0.1:7890` even with inherited proxies removed. The sandbox blocked it; initial real test timed out with zero provider requests. Explicit child-only dead proxies (`127.0.0.1:9`) plus localhost NO_PROXY suppress system-proxy fallback. Port 9 is not allowed by the sandbox. System proxy configuration is untouched.
- Codex may attempt background metadata/plugin connections; sandbox denies all non-fixture destinations. This is not a claim that the executable never attempts them, only that they cannot connect through this test's enforced boundary.
- Fixture never forwards traffic, rejects unexpected routes, authorization headers, excessive bodies and more than one Responses request. Logs do not dump request bodies, credentials or raw Codex stdout/stderr.
- Finite subprocess deadlines, own test process group termination, temporary HTTP server shutdown and TemporaryDirectory cleanup. No service-manager or name-based process killing; failures do not invoke production rollback/install/reload.

Official configuration reference used: https://developers.openai.com/codex/config-advanced (custom provider/base_url/Responses configuration). The fixture uses no OpenAI credentials; its reported token usage is synthetic, not billable usage.

## What this does NOT establish

This is a **real Codex CLI → fake provider** seam check on Mac, not a completed HAPI Hub → Runner → Codex app-server end-to-end test. It does not prove real provider authentication, model compatibility/quality, Linux transport, VM resource isolation, production readiness, or Sidecar shadow acceptance. Candidate/active pins remain unchanged.

## VM plan, pending separate authorization

After authorization, adapt the fixture behind real Codex app-server in the isolated candidate Hub/Runner chain. Do not feed a canned reply directly to Hub or replace Runner/Codex with a fake executable.

Run the whole test stack in one private Linux network namespace (loopback only, no host/public network routes) and a separately resource-limited transient cgroup; test HOME/config and synthetic credentials only. Hide production home/config/database paths and mount only staged test binaries/data. A Linux isolation probe must fail closed before Codex starts if namespace/filesystem/resource isolation cannot be established. The current Mac adapter intentionally cannot be used as the Linux launcher.

No package downloads or real account authentication should occur inside that run. Stage and hash required dependencies in advance under separate approval. Only the test cgroup/processes and disposable data may be cleaned up on failure. The VM implementation and its probes have not been executed or claimed validated here.

This separate zero-fee test authorization would not authorize Sidecar shadow, production replacement, account/paid inference, or enabling automatic upgrades.
