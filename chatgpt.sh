#!/bin/bash
set -e

FLAGS=()

# Wayland auto-detection and flags
if [ -n "$WAYLAND_DISPLAY" ]; then
    FLAGS+=(
        --ozone-platform-hint=auto
        --enable-features=WaylandWindowDecorations
    )
fi

# Allow user custom flags via ~/.config/chatgpt-flags.conf
CONFIG_FILE="${XDG_CONFIG_HOME:-$HOME/.config}/chatgpt-flags.conf"
if [ -f "$CONFIG_FILE" ]; then
    mapfile -t USER_FLAGS < <(grep -Ev '^\s*$|^#' "$CONFIG_FILE")
    FLAGS+=("${USER_FLAGS[@]}")
fi

# Set temporary directory
export TMPDIR="${XDG_CACHE_HOME:-$HOME/.cache}"

# Execute using zypak-wrapper (from org.electronjs.Electron2.BaseApp)
exec zypak-wrapper /app/lib/chatgpt/ChatGPT "${FLAGS[@]}" "$@"
