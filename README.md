<div align="center">
  <img src="icons/hicolor/128x128/apps/com.openai.chatgpt.png" alt="ChatGPT" width="88" height="88" />

  <h1>ChatGPT for Linux (Flatpak)</h1>

  <p>Flatpak packaging and a software repository for OpenAI's official ChatGPT Linux desktop client.</p>

  <p>
    <a href="https://github.com/jhuang6451/chatgpt-flatpak/actions/workflows/build-and-deploy.yml"><img src="https://img.shields.io/github/actions/workflow/status/jhuang6451/chatgpt-flatpak/build-and-deploy.yml?branch=master&label=build&labelColor=0d0d0d&color=10a37f" alt="Build status" /></a>
    <a href="https://github.com/jhuang6451/chatgpt-flatpak/actions/workflows/check-update.yml"><img src="https://img.shields.io/github/actions/workflow/status/jhuang6451/chatgpt-flatpak/check-update.yml?branch=master&label=upstream%20check&labelColor=0d0d0d&color=10a37f" alt="Upstream check status" /></a>
    <a href="https://github.com/jhuang6451/chatgpt-flatpak/releases/latest"><img src="https://img.shields.io/github/v/release/jhuang6451/chatgpt-flatpak?label=release&labelColor=0d0d0d&color=10a37f" alt="Latest release" /></a>
    <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-10a37f?labelColor=0d0d0d" alt="License" /></a>
  </p>

  <p>English · <a href="README.zh-CN.md">简体中文</a></p>

  <p>
    <a href="https://jhuang6451.github.io/chatgpt-flatpak/">Website</a> ·
    <a href="https://github.com/jhuang6451/chatgpt-flatpak/releases/latest">Offline bundle</a> ·
    <a href="#known-limitations">Known limitations</a>
  </p>
</div>

## Overview

OpenAI ships its ChatGPT Linux client, which includes the Codex coding agent, only as an RPM package. This project repackages that RPM as a Flatpak and hosts an OSTree repository, so systems where installing an RPM is awkward (Fedora Atomic, Bazzite, SteamOS, Debian and Ubuntu) can use `flatpak install` and get updates the usual way.

The build downloads the RPM from OpenAI's YUM repository, checks its SHA-256, and unpacks it. Unlike a plain repackage, it also changes the bundled `codex` binary so that Codex can run commands inside Flatpak. [How Codex runs inside Flatpak](#how-codex-runs-inside-flatpak) explains what is changed and what that costs.

- The package comes from OpenAI's official YUM repository. The manifest pins the download URL and SHA-256.
- Two checks in the `codex` binary are patched, and a small `bwrap` shim replaces bubblewrap. CI runs a command through the Codex sandbox after every build.
- The launcher detects Wayland and enables the matching Ozone flags. A config file can add more Electron flags.
- Login state is stored in GNOME Keyring or KDE Wallet.
- GitHub Actions checks upstream every 6 hours. When a new version appears, it updates the manifest, builds, and publishes.

Only **x86_64** is built and published, because OpenAI publishes only x86_64 RPMs.

## Installation

### From the repository (recommended)

```bash
flatpak remote-add --if-not-exists chatgpt https://jhuang6451.github.io/chatgpt-flatpak/chatgpt.flatpakrepo
flatpak install chatgpt com.openai.chatgpt
flatpak run com.openai.chatgpt
```

Once the remote is added, `flatpak update` updates ChatGPT along with your other apps. The runtime comes from Flathub, so add Flathub first if it isn't enabled:

```bash
flatpak remote-add --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo
```

### From a `.flatpakref`

Download [chatgpt.flatpakref](https://jhuang6451.github.io/chatgpt-flatpak/chatgpt.flatpakref) and open it with GNOME Software or KDE Discover. The file includes the Flathub URL, so the runtime is installed too.

### From the offline bundle

Download `com.openai.chatgpt.flatpak` from [Releases](https://github.com/jhuang6451/chatgpt-flatpak/releases/latest):

```bash
flatpak install --user com.openai.chatgpt.flatpak
```

The bundle doesn't update itself. To upgrade, download a new one.

### Repository signing

Commits, appstream branches, and the summary file are signed with GPG. `chatgpt.flatpakrepo` and `chatgpt.flatpakref` embed the public key and set `gpg-verify=true`, so Flatpak verifies signatures after download. The signing key fingerprint is:

```text
5F01 B1FD 3DD6 D620 2FA9 0276 B82A 2266 6F3D EC39
```

If you added the `chatgpt` remote before signing was enabled, your old configuration has no public key and updates will fail. Remove the remote and add it again:

```bash
flatpak remote-delete chatgpt
flatpak remote-add chatgpt https://jhuang6451.github.io/chatgpt-flatpak/chatgpt.flatpakrepo
```

The offline bundle is not covered by this verification, so download it only from this repository's Releases page.

## Usage

### Launch flags

The launcher reads extra flags from the file below, one flag per line. Blank lines and lines starting with `#` are ignored.

```text
~/.var/app/com.openai.chatgpt/config/chatgpt-flags.conf
```

Inside the sandbox this path is `$XDG_CONFIG_HOME`, not `~/.config`. For example, to force X11:

```text
--ozone-platform=x11
```

On Wayland sessions the launcher adds `--ozone-platform-hint=auto` and `--enable-features=WaylandWindowDecorations` by default. If your config file also sets `--enable-features=...`, the launcher merges it with the defaults, so you don't need to repeat `WaylandWindowDecorations`.

The launcher also sets `TMPDIR` to `~/.var/app/com.openai.chatgpt/cache/tmp`.

### Where data lives

`$HOME` inside the sandbox is your real home directory, so Codex reads and writes the same `~/.codex` as a Codex CLI installed on the host. The Electron profile (cookies, local storage, caches) is kept in `~/.var/app/com.openai.chatgpt/config/Codex`.

## How Codex runs inside Flatpak

Codex runs each shell command through bubblewrap. Inside Flatpak that fails in two ways:

1. While building the bubblewrap command, Codex reads `/proc/self/mountinfo` and requires every mount root to be an absolute path. Flatpak has an nsfs mount at `/run/.userns` whose root is `user:[<inode>]`, so Codex stops with `mountinfo path is not absolute`.
2. Flatpak is already a bubblewrap sandbox, and its seccomp filter blocks unprivileged user namespaces, so a nested bubblewrap can't start.

The build works around both:

- `scripts/patch-codex.py` turns the mount-root check into NOPs and disables the SHA-256 check that Codex runs on its bundled bubblewrap. Each patch must match exactly one location next to code that references the matching error message. If upstream changes the code, the build fails instead of patching the wrong place.
- `bwrap_shim.c` is installed as `resources/codex-resources/bwrap`, which is the copy Codex executes. It handles `--argv0`, `--chdir`, `--die-with-parent`, `--setenv`, `--unsetenv`, and `--clearenv`, ignores every mount and namespace option, and runs the command. A second copy at `/app/bin/bwrap` is there because Codex probes `bwrap --help` on `PATH` before falling back to the bundled copy.
- `scripts/verify-codex-sandbox.sh` runs `codex sandbox -- sh -c 'echo ...'` in the built package during CI. The build fails if Codex reports either of the patched errors.

The shim does not create a sandbox, so Codex's filesystem restrictions are not enforced. In read-only or workspace-write mode, a command can still write anywhere the Flatpak can, which includes your whole home directory. Network restriction still works: Codex applies it with seccomp in `codex-linux-sandbox`, and in testing, DNS lookups and direct TCP connections from a restricted command failed. To give a task network access, raise its permissions in the app.

## Permissions and security

The manifest grants `--filesystem=home`, so ChatGPT and every command Codex runs can read and write your whole home directory, including dotfiles such as `~/.ssh`. Because the bubblewrap shim doesn't isolate anything, Codex's own sandbox modes don't narrow that. The app has no `org.freedesktop.Flatpak` permission, so it can't run commands on the host.

The full permission list:

| Permission | Purpose |
| --- | --- |
| `--socket=wayland`, `--socket=fallback-x11`, `--share=ipc` | Display |
| `--share=network` | ChatGPT and Codex services |
| `--socket=pulseaudio` | Audio and voice |
| `--device=dri` | GPU acceleration |
| `--filesystem=home` | Read and write the home directory, so Codex can work on local projects |
| `--talk-name=org.freedesktop.Notifications`, `org.kde.StatusNotifierWatcher` | Notifications, tray icon |
| `--talk-name=org.freedesktop.secrets`, `org.kde.kwalletd5`, `org.kde.kwalletd6` | Keyring for Electron `safeStorage` |

To limit access to one project directory, use [Flatseal](https://flathub.org/apps/com.github.tchx84.Flatseal) or the command line:

```bash
flatpak override --user --nofilesystem=home --filesystem=~/Projects com.openai.chatgpt
```

Undo all overrides with `flatpak override --user --reset com.openai.chatgpt`.

## Known limitations

- **x86_64 only.** OpenAI publishes only x86_64 RPMs.
- **Codex filesystem sandboxing is not enforced.** See [How Codex runs inside Flatpak](#how-codex-runs-inside-flatpak). Network restriction still works.
- **Few developer tools inside the sandbox.** Codex sees only the freedesktop runtime: `python3` and `curl` are there, `git`, `node`, `gcc`, and `make` are not, and host programs are not on `PATH`. If you want Codex to use host tools, grant `flatpak override --user --talk-name=org.freedesktop.Flatpak com.openai.chatgpt` and run them through `flatpak-spawn --host`. That gives the app full access to your user account on the host.
- **New upstream versions can break the patches.** If OpenAI changes the code around either check, `patch-codex.py` stops the build and the repository stays on the previous version until the patterns are updated.
- **The offline bundle doesn't install the runtime.** Enable Flathub before installing it.

## Building locally

You need `flatpak` and `flatpak-builder`. The script installs `org.flatpak.Builder` if `flatpak-builder` is missing.

```bash
git clone https://github.com/jhuang6451/chatgpt-flatpak.git
cd chatgpt-flatpak
./scripts/build-local.sh
```

The script installs the required runtimes, builds, exports the result to a local `repo/` directory, and writes `com.openai.chatgpt.flatpak`. After installing it, `scripts/verify-codex-sandbox.sh` checks that Codex can run commands.

## Automatic updates

1. `check-update.yml` runs `scripts/update-checker.py` every 6 hours. It reads `repomd.xml` and `primary.xml.gz` from OpenAI's YUM repository.
2. When there is a new version, the script updates the download URL and hash in `com.openai.chatgpt.yaml`, adds a release entry to `com.openai.chatgpt.metainfo.xml`, and commits to `master`.
3. The commit triggers `build-and-deploy.yml`, which builds the Flatpak, checks the Codex sandbox, signs the repository, creates a GitHub Release, and publishes the OSTree repository and the website through GitHub Pages.

Each release is built from an empty repository, so the remote holds only the latest commit. OSTree addresses files by content, and clients download only the objects they don't already have. The repository keeps no history and offers no deltas from older versions.

## License and trademarks

The packaging scripts and configuration are released under the [MIT License](LICENSE). ChatGPT, Codex, and the OpenAI logo are trademarks of OpenAI, and the ChatGPT desktop client is OpenAI's proprietary software. This project is not affiliated with or endorsed by OpenAI.
