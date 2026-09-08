# Preserving local HAPI fixes

Set `UPDATE_MODE=source`, then place one or more `*.patch` files in the configured
`PATCH_DIR`. They are applied alphabetically to each upstream release tag.

The updater follows a fail-closed policy:

1. patch applies cleanly → apply and build;
2. reverse-check succeeds → upstream already contains it, so skip it;
3. neither succeeds → stop before touching the installed HAPI.

Generate a patch from a clean HAPI clone with:

```bash
git diff --binary upstream/main...your-fix-branch > 010-my-fix.patch
```

An optional executable `PATCH_DIR/pre-build` receives the release worktree path
and can perform semantic transformations. It must be idempotent and exit non-zero
on uncertainty. Never put tokens or credentials in patches.

For a patch that is mandatory in production, also configure
`REQUIRED_PATCH_FILE` and `REQUIRED_PATCH_SHA256`. This prevents an empty patch
directory, stale copy, or accidental replacement from producing an apparently
successful unpatched build. Use `REQUIRE_CANDIDATE_VERIFY=1` for any patched Hub
whose HTTP/API contract must be exercised before production mutation.
