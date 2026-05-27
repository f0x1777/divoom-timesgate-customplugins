#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LABEL="${LAUNCHD_LABEL:-com.divoom.timesgate.aifeats}"
PLIST_PATH="${HOME}/Library/LaunchAgents/${LABEL}.plist"
PYTHON_BIN="${PYTHON_BIN:-${ROOT_DIR}/.venv/bin/python}"

if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "Python not found at ${PYTHON_BIN}."
  echo "Create a virtualenv first: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
  exit 1
fi

mkdir -p "${HOME}/Library/LaunchAgents" "${ROOT_DIR}/logs"

cat > "${PLIST_PATH}" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${LABEL}</string>

  <key>WorkingDirectory</key>
  <string>${ROOT_DIR}</string>

  <key>ProgramArguments</key>
  <array>
    <string>${PYTHON_BIN}</string>
    <string>-u</string>
    <string>${ROOT_DIR}/main.py</string>
    <string>--provider</string>
    <string>both</string>
    <string>--hold-secs</string>
    <string>0</string>
  </array>

  <key>RunAtLoad</key>
  <true/>

  <key>KeepAlive</key>
  <true/>

  <key>StandardOutPath</key>
  <string>${ROOT_DIR}/logs/meter.log</string>

  <key>StandardErrorPath</key>
  <string>${ROOT_DIR}/logs/meter.err.log</string>
</dict>
</plist>
PLIST

launchctl bootout "gui/$(id -u)" "${PLIST_PATH}" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$(id -u)" "${PLIST_PATH}"
launchctl kickstart -k "gui/$(id -u)/${LABEL}"

echo "Installed and started ${LABEL}"
echo "Plist: ${PLIST_PATH}"
