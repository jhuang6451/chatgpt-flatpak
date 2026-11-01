#!/usr/bin/env bash
# Sign every app/runtime commit in an OSTree repo, then regenerate the
# summary (signed) and static deltas.
# Usage: sign-repo.sh <repo-dir> <gpg-key-id> [extra build-update-repo args...]
set -euo pipefail

REPO="${1:?usage: $0 <repo-dir> <gpg-key-id> [build-update-repo args...]}"
KEY="${2:?usage: $0 <repo-dir> <gpg-key-id> [build-update-repo args...]}"
shift 2

while read -r ref; do
  IFS=/ read -r kind id arch branch <<<"$ref"
  extra=()
  [ "$kind" = runtime ] && extra+=(--runtime)
  echo "==> Signing $ref"
  flatpak build-sign --gpg-sign="$KEY" --arch="$arch" "${extra[@]}" "$REPO" "$id" "$branch"
done < <(ostree refs --repo="$REPO" | grep -E '^(app|runtime)/')

echo "==> Updating signed summary and static deltas"
flatpak build-update-repo --gpg-sign="$KEY" --generate-static-deltas "$@" "$REPO"
