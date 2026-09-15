#!/usr/bin/env bash
set -euo pipefail
REPO=$(cd "$(dirname "$0")/.." && pwd); T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
mkdir -p "$T/fakebin" "$T/home/.hapi" "$T/root" "$T/npmroot/@twsxtd/hapi"
printf 'old package tree\n' >"$T/npmroot/@twsxtd/hapi/marker"
printf '1.0.0\n' >"$T/npmroot/@twsxtd/hapi/version"
printf 'v26\n' >"$T/database"
cat >"$T/fakebin/hapi" <<'SH'
#!/bin/sh
echo "hapi version: $(cat "$FAKE_NPM_ROOT/@twsxtd/hapi/version")"
SH
cat >"$T/fakebin/npm" <<'SH'
#!/bin/sh
if [ "$1" = view ]; then echo '"2.0.0"'
elif [ "$1" = root ]; then echo "$FAKE_NPM_ROOT"
elif [ "$1" = pack ]; then f="fake-${2##*@}.tgz"; : >"$f"; echo "$f"
elif [ "$1" = install ]; then
  case "$3" in *.tgz) :;; *) printf '%s\n' "${3##*@}" >"$FAKE_NPM_ROOT/@twsxtd/hapi/version"; printf 'v27\n' >"$FAKE_DB";; esac
else exit 2; fi
SH
chmod +x "$T/fakebin/"*
cat >"$T/config.json" <<EOF
{
"HAPI_BIN":"$T/fakebin/hapi",
"NPM_BIN":"$T/fakebin/npm",
"HAPI_HOME":"$T/home/.hapi",
"USE_SUDO":"0",
"UPDATE_MODE":"package",
"REQUIRE_DATABASE_ROLLBACK":1,
"DATABASE_SNAPSHOT_COMMAND":"cp \"\$FAKE_DB\" \"\$HSU_STATE/db-\$HSU_STAMP\"",
"DATABASE_RESTORE_COMMAND":"cp \"\$HSU_STATE/db-\$HSU_STAMP\" \"\$FAKE_DB\"",
"QUIESCE_COMMAND":"true",
"RESUME_COMMAND":"true",
"VERIFY_COMMAND":"true"
}
EOF
export FAKE_NPM_ROOT="$T/npmroot" FAKE_DB="$T/database"
cp -R "$REPO/bin" "$T/root/"
PATH="$T/fakebin:$PATH" HAPI_UPDATER_ROOT="$T/root" HAPI_UPDATER_CONFIG="$T/config.json" "$REPO/bin/hapi-safe-update" --force
test "$(cat "$T/npmroot/@twsxtd/hapi/version")" = 2.0.0
test "$(cat "$T/database")" = v27

# A failed post-install assertion must restore the old package version.
printf '1.0.0\n' >"$T/npmroot/@twsxtd/hapi/version"; printf 'v26\n' >"$T/database"; python3 - "$T/config.json" <<'PY'
import json,sys
p=sys.argv[1]; d=json.load(open(p)); d['VERIFY_COMMAND']='test "$(cat "$FAKE_NPM_ROOT/@twsxtd/hapi/version")" = 1.0.0'; json.dump(d,open(p,'w'))
PY
if PATH="$T/fakebin:$PATH" HAPI_UPDATER_ROOT="$T/root" HAPI_UPDATER_CONFIG="$T/config.json" "$REPO/bin/hapi-safe-update" --force; then exit 1; fi
test "$(cat "$T/npmroot/@twsxtd/hapi/version")" = 1.0.0
test "$(cat "$T/database")" = v26

# A lifecycle recovery failure must freeze future automatic attempts.
python3 - "$T/config.json" <<'PY'
import json,sys
p=sys.argv[1]; d=json.load(open(p)); d['VERIFY_COMMAND']='true'; d['RESUME_COMMAND']='false'; json.dump(d,open(p,'w'))
PY
set +e
PATH="$T/fakebin:$PATH" HAPI_UPDATER_ROOT="$T/root" HAPI_UPDATER_CONFIG="$T/config.json" "$REPO/bin/hapi-safe-update" --force
rc=$?
set -e
test "$rc" = 70; test -f "$T/root/state/ROLLBACK_FAILED"
set +e
PATH="$T/fakebin:$PATH" HAPI_UPDATER_ROOT="$T/root" HAPI_UPDATER_CONFIG="$T/config.json" "$REPO/bin/hapi-safe-update" --force >/dev/null 2>&1
frozen_rc=$?
set -e
test "$frozen_rc" = 70
echo 'package install + rollback integration OK'
