#!/usr/bin/env bash
# Check that the patched Codex binary can run a command through its Linux
# sandbox inside the Flatpak.
#
# Usage:
#   verify-codex-sandbox.sh              # test the installed com.openai.chatgpt
#   verify-codex-sandbox.sh <repo-dir>   # install from a local OSTree repo first (CI)
#
# Exit status:
#   0  the command ran, or it failed for a reason unrelated to the patches
#      (reported as a warning, since CI containers may lack seccomp or userns)
#   1  Codex hit one of the checks that patch-codex.py is supposed to disable
set -euo pipefail

APP_ID=com.openai.chatgpt
CODEX=/app/lib/chatgpt/resources/codex
MARKER=codex-sandbox-ok

if [ -n "${1:-}" ]; then
  REPO="$(realpath "$1")"
  flatpak remote-add --if-not-exists --no-gpg-verify ci-local "file://$REPO"
  flatpak install -y --noninteractive --reinstall ci-local "$APP_ID"
fi

workdir="$(mktemp -d)"
trap 'rm -rf "$workdir"' EXIT

set +e
output=$(cd "$workdir" && timeout 120 flatpak run --command="$CODEX" "$APP_ID" \
  sandbox -- sh -c "echo $MARKER" 2>&1)
status=$?
set -e

printf '%s\n' "$output"

if grep -qx "$MARKER" <<<"$output"; then
  echo "Codex sandbox check passed."
  exit 0
fi

if grep -qE 'mountinfo path is not absolute|bubblewrap digest mismatch' <<<"$output"; then
  echo "::error::Codex rejected the Flatpak sandbox; patch-codex.py did not take effect (exit $status)." >&2
  exit 1
fi

echo "::warning::Codex sandbox check did not print the marker (exit $status), but no patched check failed. This is usually a limitation of the CI container."
exit 0
