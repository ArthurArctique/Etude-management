#!/bin/bash
# Compile le client EventKit et l'emballe dans la mini-app « Agent Calendar ».
# macOS rattache l'autorisation Calendriers à cette mini-app, quel que soit l'agent
# (Claude Code, Codex…) qui la lance. Recompiler change la signature ad hoc de l'app :
# macOS redemande alors l'accès. Ne relancer ce script que si l'app manque ou ne marche plus.
set -euo pipefail
skill_dir="$(cd "$(dirname "$0")/.." && pwd)"
app="$skill_dir/app/Agent Calendar.app"
mkdir -p "$app/Contents/MacOS"
/usr/bin/swiftc -swift-version 5 -O -target "$(uname -m)-apple-macosx14.0" \
  -module-cache-path "${TMPDIR:-/tmp}/agent-calendar-swift-cache" \
  "$skill_dir/scripts/calendar.swift" -o "$app/Contents/MacOS/apple-calendar" \
  -Xlinker -sectcreate -Xlinker __TEXT -Xlinker __info_plist \
  -Xlinker "$skill_dir/scripts/Info.plist"
cp "$skill_dir/scripts/Info.plist" "$app/Contents/Info.plist"
/usr/bin/codesign --force --sign - --identifier local.etude-management.apple-calendar "$app"
echo "$app"
