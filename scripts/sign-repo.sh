#!/usr/bin/env bash
# Sign every ref commit in an OSTree repo (including app, runtime, and
# appstream branches), then regenerate the signed summary and static deltas.
# Usage: sign-repo.sh <repo-dir> <gpg-key-id> [extra build-update-repo args...]
set -euo pipefail

REPO="${1:?usage: $0 <repo-dir> <gpg-key-id> [build-update-repo args...]}"
KEY="${2:?usage: $0 <repo-dir> <gpg-key-id> [build-update-repo args...]}"
shift 2

# Honor --gpg-homedir if passed in extra build-update-repo args.
gpg_homedir=""
prev=""
for arg in "$@"; do
  if [ "$prev" = "--gpg-homedir" ]; then
    gpg_homedir="$arg"
    prev=""
  elif [ "$arg" = "--gpg-homedir" ]; then
    prev="--gpg-homedir"
  elif [[ "$arg" == --gpg-homedir=* ]]; then
    gpg_homedir="${arg#--gpg-homedir=}"
  fi
done

gpg_opts=()
ostree_gpg_opts=()
if [ -n "$gpg_homedir" ]; then
  gpg_opts+=(--homedir "$gpg_homedir")
  ostree_gpg_opts+=(--gpg-homedir="$gpg_homedir")
fi

mapfile -t key_ids < <(
  gpg "${gpg_opts[@]}" --list-secret-keys --with-colons "$KEY" 2>/dev/null \
    | awk -F: '/^(sec|ssb):/ && $12 ~ /[sS]/ {print $5}'
)

is_commit_signed() {
  local commit="$1" show_out kid
  show_out=$(LC_ALL=C ostree --repo="$REPO" show "$commit")
  if [ "${#key_ids[@]}" -gt 0 ]; then
    for kid in "${key_ids[@]}"; do
      if grep -qF "$kid" <<<"$show_out"; then
        return 0
      fi
    done
    return 1
  fi
  grep -qE '^Found [0-9]+ signature' <<<"$show_out"
}

# Sign all refs (app, runtime, appstream, appstream2, etc.) before
# build-update-repo: flatpak build-sign ignores appstream branches, and
# build-update-repo skips committing/signing appstream if its tree matches
# the unsigned commit already written by flatpak-builder.
while read -r ref; do
  commit=$(ostree --repo="$REPO" rev-parse "$ref")
  if is_commit_signed "$commit"; then
    echo "==> Ref $ref ($commit) already signed"
  else
    echo "==> Signing $ref ($commit)"
    ostree gpg-sign --repo="$REPO" "${ostree_gpg_opts[@]}" "$commit" "$KEY"
  fi
done < <(ostree refs --repo="$REPO")

echo "==> Updating signed summary and static deltas"
flatpak build-update-repo --gpg-sign="$KEY" --generate-static-deltas "$@" "$REPO"

while read -r ref; do
  commit=$(ostree --repo="$REPO" rev-parse "$ref")
  if ! is_commit_signed "$commit"; then
    echo "::error::Ref $ref ($commit) is missing a GPG signature after build-update-repo" >&2
    exit 1
  fi
done < <(ostree refs --repo="$REPO")
