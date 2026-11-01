#!/bin/bash
set -euo pipefail

FLAGS=()
FEATURES=()

# Wayland auto-detection and flags
if [ -n "${WAYLAND_DISPLAY:-}" ] || [ "${XDG_SESSION_TYPE:-}" = "wayland" ]; then
    FLAGS+=(--ozone-platform-hint=auto)
    FEATURES+=(WaylandWindowDecorations)
fi

# Allow user custom flags via ~/.config/chatgpt-flags.conf
CONFIG_FILE="${XDG_CONFIG_HOME:-$HOME/.config}/chatgpt-flags.conf"
USER_FLAGS=()
if [ -f "$CONFIG_FILE" ]; then
    mapfile -t USER_FLAGS < <(grep -Ev '^\s*$|^#' "$CONFIG_FILE" || true)
fi

# Chromium keeps only the last --enable-features, so merge the user's list
# with ours instead of letting it override the defaults.
for flag in "${USER_FLAGS[@]}"; do
    case "$flag" in
        --enable-features=*) FEATURES+=("${flag#--enable-features=}") ;;
        *) FLAGS+=("$flag") ;;
    esac
done
if [ "${#FEATURES[@]}" -gt 0 ]; then
    FEATURES_JOINED=$(IFS=,; echo "${FEATURES[*]}")
    FLAGS+=("--enable-features=$FEATURES_JOINED")
fi

# Keep temporary files in their own dir instead of mixing them into the cache root
export TMPDIR="${XDG_CACHE_HOME:-$HOME/.cache}/tmp"
mkdir -p "$TMPDIR"

# Execute using zypak-wrapper (from org.electronjs.Electron2.BaseApp)
exec zypak-wrapper /app/lib/chatgpt/ChatGPT "${FLAGS[@]}" "$@"
