#!/usr/bin/env bash
set -euo pipefail
REPO=$(cd "$(dirname "$0")/.." && pwd); T=$(mktemp -d); trap 'rc=$?; if [[ $rc != 0 ]]; then cat "$T/bun.log" 2>/dev/null || true; find "$T/root/worktrees" -ls 2>/dev/null || true; fi; rm -rf "$T"; exit $rc' EXIT
mkdir -p "$T/fakebin" "$T/home/.hapi" "$T/root" "$T/npmroot/@twsxtd/hapi/node_modules/@twsxtd/hapi-test/bin" "$T/src/cli" "$T/patches"
printf '1.0.0\n' >"$T/version"; printf '# demo\n' >"$T/src/README.md"
git -C "$T/src" init -q; git -C "$T/src" config user.email test@example.com; git -C "$T/src" config user.name test; git -C "$T/src" add .; git -C "$T/src" commit -qm init; git -C "$T/src" tag v1.0.1
printf '# demo\npatched\n' >"$T/src/README.md"; git -C "$T/src" diff >"$T/patches/010-demo.patch"; git -C "$T/src" checkout -- README.md
cat >"$T/fakebin/hapi" <<'SH'
#!/bin/sh
echo "hapi version: $(cat "$FAKE_VERSION_FILE")"
SH
cat >"$T/fakebin/npm" <<'SH'
#!/bin/sh
case "$1" in
view) echo '"1.0.1"';;
root) echo "$FAKE_NPM_ROOT";;
pack) f="fake-${2##*@}.tgz"; : >"$f"; echo "$f";;
install) case "$3" in *.tgz) printf '1.0.0\n' >"$FAKE_VERSION_FILE";; *) printf '%s\n' "${3##*@}" >"$FAKE_VERSION_FILE";; esac;;
*) exit 2;; esac
SH
cat >"$T/fakebin/bun" <<'SH'
#!/bin/sh
echo "$PWD :: $*" >>"$FAKE_BUN_LOG"
if [ "$1 $2" = 'run build:single-exe' ]; then mkdir -p cli/dist-exe/test; printf '%s\n' '#!/bin/sh' "echo 'hapi version: 1.0.1'" >cli/dist-exe/test/hapi; chmod +x cli/dist-exe/test/hapi; fi
exit 0
SH
printf '%s\n' '#!/bin/sh' "echo 'old platform'" >"$T/npmroot/@twsxtd/hapi/node_modules/@twsxtd/hapi-test/bin/hapi"
chmod +x "$T/fakebin/"* "$T/npmroot/@twsxtd/hapi/node_modules/@twsxtd/hapi-test/bin/hapi"
cat >"$T/config.json" <<EOF
{"HAPI_BIN":"$T/fakebin/hapi","NPM_BIN":"$T/fakebin/npm","BUN_BIN":"$T/fakebin/bun","HAPI_HOME":"$T/home/.hapi","USE_SUDO":"0","UPDATE_MODE":"source","SOURCE_REPO":"$T/src","PATCH_DIR":"$T/patches","QUIESCE_COMMAND":"true","RESUME_COMMAND":"true","VERIFY_COMMAND":"true"}
EOF
cp -R "$REPO/bin" "$T/root/"; export FAKE_VERSION_FILE="$T/version" FAKE_NPM_ROOT="$T/npmroot" FAKE_BUN_LOG="$T/bun.log"
PATH="$T/fakebin:$PATH" HAPI_UPDATER_ROOT="$T/root" HAPI_UPDATER_CONFIG="$T/config.json" "$REPO/bin/hapi-safe-update" --force
test "$(cat "$T/version")" = 1.0.1
grep -q patched "$T/root/worktrees/v1-0-1/README.md"
grep -q 'hapi version: 1.0.1' "$T/npmroot/@twsxtd/hapi/node_modules/@twsxtd/hapi-test/bin/hapi"
echo 'source patch build integration OK'
