#!/usr/bin/env bash
set -euo pipefail

# Local Flatpak Build & Test Helper Script for ChatGPT

MANIFEST="com.openai.chatgpt.yaml"
BUILD_DIR="${BUILD_DIR:-build-dir}"
REPO_DIR="${REPO_DIR:-repo}"

echo "==> Checking required Flatpak runtimes..."
flatpak install -y --user flathub \
  org.freedesktop.Platform//25.08 \
  org.freedesktop.Sdk//25.08 \
  org.electronjs.Electron2.BaseApp//25.08 || true

BUILDER_CMD=""
if command -v flatpak-builder >/dev/null 2>&1; then
  BUILDER_CMD="flatpak-builder"
elif flatpak info org.flatpak.Builder >/dev/null 2>&1; then
  BUILDER_CMD="flatpak run org.flatpak.Builder"
else
  echo "Installing org.flatpak.Builder..."
  flatpak install -y --user flathub org.flatpak.Builder
  BUILDER_CMD="flatpak run org.flatpak.Builder"
fi

echo "==> Using Flatpak Builder: ${BUILDER_CMD}"
echo "==> Building ChatGPT Flatpak package..."
${BUILDER_CMD} --force-clean --repo="${REPO_DIR}" "${BUILD_DIR}" "${MANIFEST}"

echo "==> Updating repository index & generating static deltas..."
flatpak build-update-repo --generate-static-deltas "${REPO_DIR}"

echo "==> Building standalone bundle..."
flatpak build-bundle "${REPO_DIR}" com.openai.chatgpt.flatpak com.openai.chatgpt stable

echo "==> Done! You can install and test your local build with:"
echo "    flatpak install --user --bundle com.openai.chatgpt.flatpak"
echo "    flatpak run com.openai.chatgpt"
