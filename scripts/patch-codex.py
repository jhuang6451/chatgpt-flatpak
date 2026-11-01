#!/usr/bin/env python3
"""
Codex binary patcher for the Flatpak build.

Two checks in the bundled `codex` binary break inside a Flatpak sandbox:

1. Mountinfo path check
   `path.is_absolute()` fails on Flatpak nsfs mounts (e.g. `user:[<inode>]`
   under /run/.userns) and Codex aborts with
   `error building bubblewrap command: mountinfo path is not absolute`.
   The conditional jump after `cmp byte [reg], '/'` is turned into NOPs.

2. Bundled bubblewrap SHA-256 check
   Codex refuses to run a bubblewrap whose digest differs from the one it
   shipped with. The Flatpak build replaces bwrap with a shim, so the
   comparison failure branch is disabled.

Every patch must match exactly one location, and that location must sit next
to code that references the matching error message. If a pattern is missing or
ambiguous the script exits non-zero and the build fails. There is no fuzzy
fallback: a wrong guess would silently corrupt an unrelated branch.
"""

import re
import struct
import subprocess
import sys

MOUNTINFO_MSG = b"mountinfo path is not absolute"
DIGEST_MSG = b"bundled bubblewrap digest mismatch for "
XREF_WINDOW = 0x400


def elf_text_range(path):
    """Return (file_offset, vaddr, size) of .text from readelf."""
    out = subprocess.check_output(["readelf", "-SW", path], text=True)
    for line in out.splitlines():
        m = re.search(r"\]\s+\.text\s+\S+\s+([0-9a-f]+)\s+([0-9a-f]+)\s+([0-9a-f]+)", line)
        if m:
            return int(m.group(2), 16), int(m.group(1), 16), int(m.group(3), 16)
    raise RuntimeError("could not locate .text section")


def has_xref(data, site, text, msg_offsets, lo, hi):
    """True if code within XREF_WINDOW of `site` references a string in [lo, hi) relative to msg."""
    foff, vaddr, size = text
    delta = vaddr - foff
    start = max(site - XREF_WINDOW, foff)
    end = min(site + XREF_WINDOW, foff + size - 4)
    for q in range(start, end):
        disp = struct.unpack_from("<i", data, q)[0]
        target = q + delta + 4 + disp
        for m in msg_offsets:
            if m + lo <= target < m + hi:
                return True
    return False


def find_unique(data, text, patterns, msg, lo, hi, label):
    """Collect regex matches that sit near a reference to `msg`; require exactly one."""
    msg_offsets = [m.start() for m in re.finditer(re.escape(msg), data)]
    if not msg_offsets:
        raise RuntimeError(f"{label}: message string not found in binary")
    # String offsets are file offsets; the xref check assumes file offset == vaddr for
    # .rodata, which holds for this binary (the check fails loudly if it ever stops).
    found = []
    for name, regex, patch in patterns:
        for m in re.finditer(regex, data, re.S):
            if has_xref(data, m.start(), text, msg_offsets, lo, hi):
                found.append((name, m, patch))
    if len(found) != 1:
        raise RuntimeError(f"{label}: expected exactly 1 verified match, found {len(found)}")
    return found[0]


def main(path):
    with open(path, "rb") as f:
        data = bytearray(f.read())
    data_b = bytes(data)
    text = elf_text_range(path)

    mountinfo_patterns = [
        # 26.1016+: cmp byte [r15], 0x2f ; mov rbp,[rsp+0x20] ; jne rel32
        ("mountinfo v2", rb"\x41\x80\x3f\x2f\x48\x8b\x6c\x24\x20(\x0f\x85[\x00-\xff]{4})",
         lambda m: (m.start(1), b"\x90" * 6)),
        # 26.917: same with rbx
        ("mountinfo v1", rb"\x41\x80\x3f\x2f\x48\x8b\x5c\x24\x20(\x0f\x85[\x00-\xff]{4})",
         lambda m: (m.start(1), b"\x90" * 6)),
    ]
    digest_patterns = [
        # 26.1016.51333: xor ecx,0xf ; je rel8  -> jmp rel8
        ("digest v2", rb"\x66\x0f\xef\xc9\x66\x0f\x76\xc8\x0f\x50\xc9\x83\xf1\x0f(\x74)[\x01-\x7f]\x8b\x4c\x24\x28",
         lambda m: (m.start(1), b"\xeb")),
        # 26.917 and 26.1027: pmovmskb eax,xmm ; cmp eax,0xffff ; jne rel8 ; movabs rbx,0x8000000000000000
        ("digest v1", rb"\x66\x0f\xd7[\xc0-\xcf]\x3d\xff\xff\x00\x00(\x75[\x01-\x7f])\x48\xbb\x00\x00\x00\x00\x00\x00\x00\x80",
         lambda m: (m.start(1), b"\x90\x90")),
    ]

    applied = []
    for label, patterns, msg, lo, hi in (
        ("mountinfo check", mountinfo_patterns, MOUNTINFO_MSG, -0x20, 0x20),
        ("bwrap digest check", digest_patterns, DIGEST_MSG, -4, 0x30),
    ):
        name, m, patch = find_unique(data_b, text, patterns, msg, lo, hi, label)
        off, repl = patch(m)
        data[off:off + len(repl)] = repl
        applied.append(f"{label}: {name} at 0x{off:x}")

    with open(path, "wb") as f:
        f.write(data)
    for line in applied:
        print(f"  [+] {line}")
    print(f"Patched {path} ({len(applied)}/2 patches applied).")


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "/app/lib/chatgpt/resources/codex"
    try:
        main(target)
    except Exception as e:  # noqa: BLE001
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
