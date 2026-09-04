#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
SRC=$(cd "$(dirname "$0")" && pwd); ROOT=${HAPI_UPDATER_ROOT:-$HOME/.local/share/hapi-safe-updater}; CFGDIR=$HOME/.config/hapi-safe-updater
mkdir -p -m 700 "$ROOT/state"
if [[ "${HAPI_INSTALL_LOCK_HELD:-0}" != 1 ]]; then exec env HAPI_INSTALL_LOCK_HELD=1 "$SRC/bin/lock-run.py" "$ROOT/state/update.lock" "$0" "$@"; fi
TX=$(mktemp -d); OS=$(uname -s); SCHED=
if [[ "$OS" == Darwin ]]; then SCHED="$HOME/Library/LaunchAgents/io.hapi.safe-updater.plist"; launchctl bootout "gui/$(id -u)/io.hapi.safe-updater" 2>/dev/null || true
else SCHED="$HOME/.config/systemd/user/hapi-safe-updater.service"; systemctl --user stop hapi-safe-updater.timer 2>/dev/null || true; fi
HAD_BIN=0; HAD_SCHED=0
if [[ -d "$ROOT/bin" ]]; then HAD_BIN=1; cp -R "$ROOT/bin" "$TX/bin"; fi
if [[ -f "$SCHED" ]]; then HAD_SCHED=1; cp "$SCHED" "$TX/scheduler"; fi
[[ "$OS" == Darwin || ! -f "$HOME/.config/systemd/user/hapi-safe-updater.timer" ]] || cp "$HOME/.config/systemd/user/hapi-safe-updater.timer" "$TX/scheduler.timer"
rollback_install(){
  rc=$?; [[ "$rc" == 0 ]] && return
  rm -rf "$ROOT/bin"; [[ "$HAD_BIN" == 0 ]] || mv "$TX/bin" "$ROOT/bin"
  [[ "$HAD_SCHED" == 1 ]] || rm -f "$SCHED"
  if [[ -f "$TX/scheduler" ]]; then
    mkdir -p "$(dirname "$SCHED")"; cp "$TX/scheduler" "$SCHED"
    if [[ "$OS" == Darwin ]]; then launchctl bootstrap "gui/$(id -u)" "$SCHED" 2>/dev/null || true
    else [[ ! -f "$TX/scheduler.timer" ]] || cp "$TX/scheduler.timer" "$HOME/.config/systemd/user/hapi-safe-updater.timer"; systemctl --user daemon-reload 2>/dev/null || true; systemctl --user enable --now hapi-safe-updater.timer 2>/dev/null || true; fi
  fi
  echo "Install failed; previous files restored." >&2
}
trap rollback_install EXIT
mkdir -p -m 700 "$ROOT" "$CFGDIR" "$ROOT/state" "$ROOT/logs"; STAGE="$TX/bin.new"; cp -R "$SRC/bin" "$STAGE"; chmod +x "$STAGE/"*; for f in "$STAGE"/*.py; do python3 -m py_compile "$f"; done
rm -rf "$ROOT/bin"; mv "$STAGE" "$ROOT/bin"
[[ -f "$CFGDIR/config.json" ]] || cp "$SRC/config.example.json" "$CFGDIR/config.json"; chmod 600 "$CFGDIR/config.json"; mkdir -p -m 700 "$CFGDIR/patches"
if [[ "$OS" == Darwin ]]; then
  mkdir -p "$HOME/Library/LaunchAgents"; sed -e "s|__HOME__|$HOME|g" -e "s|__ROOT__|$ROOT|g" "$SRC/schedulers/io.hapi.safe-updater.plist" >"$SCHED"
  plutil -lint "$SCHED" >/dev/null
  launchctl bootout "gui/$(id -u)/io.hapi.safe-updater" 2>/dev/null || true
  launchctl bootstrap "gui/$(id -u)" "$SCHED"; launchctl enable "gui/$(id -u)/io.hapi.safe-updater"
else
  mkdir -p "$HOME/.config/systemd/user"; sed -e "s|__HOME__|$HOME|g" -e "s|__ROOT__|$ROOT|g" "$SRC/schedulers/hapi-safe-updater.service" >"$SCHED"; cp "$SRC/schedulers/hapi-safe-updater.timer" "$HOME/.config/systemd/user/"
  systemd-analyze verify "$SCHED" 2>/dev/null
  systemctl --user daemon-reload; systemctl --user enable --now hapi-safe-updater.timer
  loginctl show-user "$USER" -p Linger 2>/dev/null | grep -q 'Linger=yes' || echo 'Note: enable linger for updates while logged out: sudo loginctl enable-linger "$USER"'
fi
trap - EXIT; rm -rf "$TX"
echo "Installed. Review $CFGDIR/config.json, then run: $ROOT/bin/hapi-safe-update --dry-run"
