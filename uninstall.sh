#!/usr/bin/env bash
set -e
if [[ $(uname -s) == Darwin ]]; then launchctl bootout "gui/$(id -u)/io.hapi.safe-updater" 2>/dev/null || true; rm -f "$HOME/Library/LaunchAgents/io.hapi.safe-updater.plist"
else systemctl --user disable --now hapi-safe-updater.timer 2>/dev/null || true; rm -f "$HOME/.config/systemd/user/hapi-safe-updater."{service,timer}; systemctl --user daemon-reload; fi
echo "Scheduler removed. Configuration and logs were retained."
