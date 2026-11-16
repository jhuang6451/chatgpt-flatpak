# OpenAI ChatGPT Linux client: Flatpak packaging context

English · [简体中文](PROJECT_CONTEXT.zh-CN.md)

> **Last updated**: 2026-11-15 (synced to 26.1111.21308, Codex CLI 0.169.0-alpha.11.1)
> **GitHub repository**: `https://github.com/jhuang6451/chatgpt-flatpak`
> **Pages site and software repository**: `https://jhuang6451.github.io/chatgpt-flatpak/`

The manifest (`com.openai.chatgpt.yaml`) is the source of truth for build steps and permissions. This file records why things are the way they are.

---

## 1. Upstream source

* **Official YUM repository**: `https://persistent.oaistatic.com/codex-app-prod/linux/rpm/x86_64`
  * Index: `repodata/repomd.xml`, which points to `primary.xml.gz` with versions and SHA-256 hashes.
  * Packages: `chatgpt-<version>-<release>.x86_64.rpm`. Only x86_64 is published.
* **Layout of the official RPM**:
  * Main binary: `/usr/lib/chatgpt/ChatGPT` (Electron)
  * Codex app server and CLI: `/usr/lib/chatgpt/resources/codex` (Rust, statically linked)
  * Bundled bubblewrap: `/usr/lib/chatgpt/resources/codex-resources/bwrap`
  * Icon: `/usr/share/pixmaps/chatgpt.png`, 1024x1024. Flatpak rejects icons over 512x512, so the repository ships pre-scaled icons in `icons/hicolor/`.
* `flatpak-builder` strips the first path component of archive sources, so the manifest looks for the files under both `extracted/usr/lib/chatgpt` and `extracted/lib/chatgpt`.

---

## 2. Flatpak decisions

### 2.1 Base and sandbox
* **App ID**: `com.openai.chatgpt`
* **Runtime**: `org.freedesktop.Platform//25.08`
* **SDK**: `org.freedesktop.Sdk//25.08`
* **BaseApp**: `org.electronjs.Electron2.BaseApp//25.08`
* **Why**: it matches Flathub and the CI container image (`ghcr.io/flathub-infra/flatpak-github-actions:freedesktop-25.08`). Electron needs unprivileged user namespaces for its own sandbox, and `zypak-wrapper` from the BaseApp forwards that to the host.

### 2.2 Launcher (`chatgpt.sh`, installed as `/app/bin/chatgpt`)
* On Wayland adds `--ozone-platform-hint=auto` and the `WaylandWindowDecorations` feature.
* Reads extra flags from `$XDG_CONFIG_HOME/chatgpt-flags.conf` and merges any `--enable-features=` line with the defaults.
* Sets `TMPDIR` to `$XDG_CACHE_HOME/tmp`, then runs `zypak-wrapper /app/lib/chatgpt/ChatGPT`.

### 2.3 Codex command execution
Codex runs shell commands through bubblewrap, which fails inside Flatpak:

1. Codex parses `/proc/self/mountinfo` and requires every mount root to be absolute. Flatpak's nsfs mount at `/run/.userns` has the root `user:[<inode>]`, so Codex returns `error building bubblewrap command: mountinfo path is not absolute`.
2. Flatpak's seccomp filter blocks `CLONE_NEWUSER`, so a nested bubblewrap can't create a sandbox.

Fixes:

* `scripts/patch-codex.py` patches two branches in `resources/codex`:
  * the mount-root check (`cmp byte [r15], '/'` followed by `jne rel32`, replaced with six NOPs);
  * the SHA-256 check on the bundled bubblewrap (`je rel8` changed to `jmp`, or `jne rel8` to NOPs on older builds).
  Each pattern must match exactly once and sit within 0x400 bytes of code that references the matching error string. Otherwise the script exits non-zero and the build fails.
* `bwrap_shim.c` honors only options that affect the child process (`--argv0`, `--chdir`, `--die-with-parent`, `--setenv`, `--unsetenv`, `--clearenv`), skips everything up to `--`, and `execvp`s the command.
* Which copy is used (tested 2026-11-15 by replacing each copy with a logging build): Codex runs `/app/bin/bwrap --help` once as a probe, then executes every command through `resources/codex-resources/bwrap`. The former third copy at `resources/bwrap` was never called and has been removed.
* `scripts/verify-codex-sandbox.sh` runs `codex sandbox -- sh -c 'echo codex-sandbox-ok'`. CI runs it against the freshly built repository and fails only on the two patched errors. Other failures become warnings, because the CI container may not support seccomp or user namespaces.

### 2.4 Behavior verified on a real system (2026-11-15, 26.1111.21308)
* Installing from the signed repository works with `gpg-verify=true`; the app commit has a good signature from `B82A22666F3DEC39`. Before this date the appstream branches were unsigned and `flatpak update --appstream chatgpt` failed. `scripts/sign-repo.sh` now signs every ref and checks the result.
* `codex sandbox` runs commands, so both patches take effect.
* Network restriction holds: inside `codex sandbox`, DNS resolution fails and `connect()` returns `EPERM`.
* Filesystem restriction does not: a command in the default sandbox mode could create a file in `$HOME` outside the working directory.
* Electron `safeStorage` uses the system keyring: cookies in `config/Codex/Default/Cookies` carry the `v11` prefix (keyring-backed key). One older `v10` entry predates the keyring permissions.
* The runtime has `python3` and `curl` but no `git`, `node`, `gcc`, or `make`. The app has no `org.freedesktop.Flatpak` permission, so Codex can't reach host tools unless the user grants it.

### 2.5 Permissions
* `--filesystem=home` lets Codex work on projects anywhere in the home directory. An earlier `--filesystem=xdg-documents:ro` overrode it and made `~/Documents` read-only; it has been removed.
* `org.freedesktop.secrets` and `org.kde.kwalletd5/6` are for Electron `safeStorage`.

---

## 3. CI/CD and hosting

1. **Build and deploy (`.github/workflows/build-and-deploy.yml`)**:
   * Runs on pushes to `master` that touch the manifest, scripts, web pages, icons, or the workflow.
   * Builds in the Flathub Action container, runs the Codex sandbox check, then signs every ref and the summary with `scripts/sign-repo.sh` (secrets `GPG_PRIVATE_KEY` and `GPG_KEY_ID`).
   * Builds from an empty repository each time. The remote keeps only the latest commit and offers no deltas from older versions.
   * Tags `v<version>` and publishes a GitHub Release with the `.flatpak` bundle, `ostree-repo.tar.gz`, `.flatpakref`, and `.flatpakrepo`.
   * Deploys GitHub Pages through the Actions Pages API. Pages hosts the website (`web/`) and the full OSTree repository under `repo/`.
2. **Upstream check (`.github/workflows/check-update.yml`)**:
   * Runs `scripts/update-checker.py --ci --update` every 6 hours.
   * On a new version, updates the manifest URL and hash and the metainfo release list, commits, and triggers the build.
