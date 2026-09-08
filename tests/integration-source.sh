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
hash_file(){ if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | awk '{print $1}'; else shasum -a 256 "$1" | awk '{print $1}'; fi; }
PATCH_SHA=$(hash_file "$T/patches/010-demo.patch")
PLATFORM_BIN="$T/npmroot/@twsxtd/hapi/node_modules/@twsxtd/hapi-test/bin/hapi"
BASELINE_SHA=$(hash_file "$PLATFORM_BIN")
python3 - "$T/config.json" "$T" "$PATCH_SHA" "$BASELINE_SHA" <<'PY'
import json,sys
out,t,patch_sha,baseline_sha=sys.argv[1:]
config={
 "HAPI_BIN":f"{t}/fakebin/hapi", "NPM_BIN":f"{t}/fakebin/npm", "BUN_BIN":f"{t}/fakebin/bun",
 "HAPI_HOME":f"{t}/home/.hapi", "USE_SUDO":"0", "UPDATE_MODE":"source", "SOURCE_REPO":f"{t}/src",
 "PATCH_DIR":f"{t}/patches", "REQUIRED_PATCH_FILE":f"{t}/patches/010-demo.patch",
 "REQUIRED_PATCH_SHA256":patch_sha, "REQUIRE_CANDIDATE_VERIFY":1,
 "CANDIDATE_VERIFY_COMMAND":"test -x \"$HSU_CANDIDATE_BIN\" && grep -q patched \"$HSU_WORKTREE/README.md\"",
 "BINARY_INTEGRITY_PATH":f"{t}/npmroot/@twsxtd/hapi/node_modules/@twsxtd/hapi-test/bin/hapi",
 "EXPECTED_CURRENT_BINARY_SHA256":baseline_sha,
 "QUIESCE_COMMAND":"true", "RESUME_COMMAND":"true", "VERIFY_COMMAND":"true"
}
open(out,"w").write(json.dumps(config))
PY
cp -R "$REPO/bin" "$T/root/"; export FAKE_VERSION_FILE="$T/version" FAKE_NPM_ROOT="$T/npmroot" FAKE_BUN_LOG="$T/bun.log"
PATH="$T/fakebin:$PATH" HAPI_UPDATER_ROOT="$T/root" HAPI_UPDATER_CONFIG="$T/config.json" "$REPO/bin/hapi-safe-update" --force
test "$(cat "$T/version")" = 1.0.1
grep -q patched "$T/root/worktrees/v1-0-1/README.md"
grep -q 'hapi version: 1.0.1' "$T/npmroot/@twsxtd/hapi/node_modules/@twsxtd/hapi-test/bin/hapi"
test "$(cat "$T/root/state/last-success-binary-sha256")" = "$(hash_file "$PLATFORM_BIN")"

# Patch identity drift must fail before touching the installed version/tree.
printf '1.0.0\n' >"$T/version"
python3 - "$T/config.json" <<'PY'
import json,sys
p=sys.argv[1]; x=json.load(open(p)); x["REQUIRED_PATCH_SHA256"]="0"*64; open(p,"w").write(json.dumps(x))
PY
set +e
PATH="$T/fakebin:$PATH" HAPI_UPDATER_ROOT="$T/root" HAPI_UPDATER_CONFIG="$T/config.json" "$REPO/bin/hapi-safe-update" --force
rc=$?
set -e
test "$rc" != 0
test "$(cat "$T/version")" = 1.0.0
echo 'source patch build integration OK'
