#!/usr/bin/env python3
"""
Automated Codex Binary Patcher for Flatpak Environment

1. Mountinfo path patch:
   Bypasses the `path.is_absolute()` check that fails on Flatpak nsfs mounts
   (e.g., user:[<inode>] /run/.userns) causing:
   `error building bubblewrap command: mountinfo path is not absolute`

2. Bwrap digest check patch:
   Bypasses the hardcoded SHA-256 integrity check on bundled bubblewrap,
   allowing the use of the transparent compatibility shim in Flatpak.
"""

import sys
import os
import struct

def patch_binary(filepath):
    if not os.path.exists(filepath):
        print(f"Error: Target file not found: {filepath}", file=sys.stderr)
        return False

    with open(filepath, "rb") as f:
        data = bytearray(f.read())

    patches_applied = 0

    # -------------------------------------------------------------
    # 1. Mountinfo non-absolute path check bypass
    # -------------------------------------------------------------
    # v26.1016.51333:
    # 41 80 3f 2f                cmpb $0x2f, (%r15)
    # 48 8b 6c 24 20             mov 0x20(%rsp), %rbp
    # 0f 85 39 ff ff ff          jne ... -> NOPs
    p1_v2 = bytes.fromhex("41803f2f488b6c24200f8539ffffff")
    p1_v2_after = bytes.fromhex("41803f2f488b6c2420909090909090")

    # v26.917.61114:
    # 41 80 3f 2f                cmpb $0x2f, (%r15)
    # 48 8b 5c 24 20             mov 0x20(%rsp), %rbx
    # 0f 85 3a ff ff ff          jne ... -> NOPs
    p1_v1 = bytes.fromhex("41803f2f488b5c24200f853affffff")
    p1_v1_after = bytes.fromhex("41803f2f488b5c2420909090909090")

    if data.count(p1_v2) == 1:
        data = data.replace(p1_v2, p1_v2_after)
        print("  [+] Applied mountinfo patch (pattern v2 / 26.1016+)")
        patches_applied += 1
    elif data.count(p1_v1) == 1:
        data = data.replace(p1_v1, p1_v1_after)
        print("  [+] Applied mountinfo patch (pattern v1 / 26.917)")
        patches_applied += 1
    else:
        # Heuristic search: look for cmp [reg], 0x2f followed by jne near mountinfo string
        str_offset = data.find(b"mountinfo path is not absolute")
        if str_offset != -1:
            print("  [*] Searching for mountinfo check using heuristics...")
            # Look for 41 80 3f 2f (cmp byte ptr [r15], 0x2f)
            found = False
            for pos in range(len(data) - 15):
                if data[pos:pos+4] == bytes.fromhex("41803f2f") and data[pos+9:pos+11] == bytes.fromhex("0f85"):
                    # Replace 6-byte jne with NOPs
                    data[pos+9:pos+15] = b"\x90" * 6
                    print(f"  [+] Applied mountinfo heuristic patch at 0x{pos:x}")
                    patches_applied += 1
                    found = True
                    break
            if not found:
                print("  [-] Warning: Mountinfo check pattern not identified", file=sys.stderr)
        else:
            print("  [-] Warning: mountinfo string not found in binary", file=sys.stderr)

    # -------------------------------------------------------------
    # 2. Bubblewrap SHA-256 digest check bypass
    # -------------------------------------------------------------
    # v26.1016.51333:
    # 66 0f ef c9                pxor %xmm1, %xmm1
    # 66 0f 76 c8                pcmpeqd %xmm0, %xmm1
    # 0f 50 c9                   movmskps %xmm1, %ecx
    # 83 f1 0f                   xor $0xf, %ecx
    # 74 6a                      je 0x9436b6e -> eb 6a (jmp 0x9436b6e)
    # 8b 4c 24 28                mov 0x28(%rsp), %ecx
    p2_v2 = bytes.fromhex("660fefc9660f76c80f50c983f10f746a8b4c2428")
    p2_v2_after = bytes.fromhex("660fefc9660f76c80f50c983f10feb6a8b4c2428")

    # v26.917.61114:
    # ... 75 2a (jne +0x2a) -> 90 90 (NOPs)
    p2_v1 = bytes.fromhex("660f748424a0010000660f748c2490010000660fdbc8660fd7c13dffff0000752a48bb00")
    p2_v1_after = bytes.fromhex("660f748424a0010000660f748c2490010000660fdbc8660fd7c13dffff0000909048bb00")

    if data.count(p2_v2) == 1:
        data = data.replace(p2_v2, p2_v2_after)
        print("  [+] Applied bwrap digest patch (pattern v2 / 26.1016+)")
        patches_applied += 1
    elif data.count(p2_v1) == 1:
        data = data.replace(p2_v1, p2_v1_after)
        print("  [+] Applied bwrap digest patch (pattern v1 / 26.917)")
        patches_applied += 1
    else:
        # Heuristic search: look for 83 f1 0f 74 (xor $0xf, %ecx; je ...)
        found = False
        for pos in range(len(data) - 10):
            if data[pos:pos+4] == bytes.fromhex("83f10f74"):
                # Change 74 xx (je) to eb xx (jmp)
                data[pos+3] = 0xeb
                print(f"  [+] Applied bwrap digest heuristic patch at 0x{pos:x}")
                patches_applied += 1
                found = True
                break
        if not found:
            print("  [-] Warning: Bwrap digest check pattern not identified", file=sys.stderr)

    with open(filepath, "wb") as f:
        f.write(data)

    print(f"Successfully processed {filepath} ({patches_applied} patches applied).")
    return patches_applied > 0

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "/app/lib/chatgpt/resources/codex"
    success = patch_binary(target)
    sys.exit(0 if success else 1)
