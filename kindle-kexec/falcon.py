#!/usr/bin/env python3
"""Generate the warm-boot I/O cursor reset for a matching Falcon BIOS pair."""
import argparse
import struct
from pathlib import Path


def word(blob, offset):
    if offset < 0 or offset + 4 > len(blob) or offset % 4:
        raise ValueError("BIOS reference outside the supplied image")
    return struct.unpack_from("<I", blob, offset)[0]


def literal(blob, offset, instruction):
    if word(blob, offset) != instruction:
        raise ValueError(f"Unrecognized Falcon instruction at {offset:#x}")
    return word(blob, offset + 8 + (instruction & 0xfff))


def unique(blob, pattern):
    hits = [i for i in range(0, len(blob) - len(pattern) + 1, 4)
            if blob[i:i + len(pattern)] == pattern]
    if len(hits) != 1:
        raise ValueError("Expected one matching Falcon I/O enumerator")
    return hits[0]


def generate(main, storage, main_base, storage_base):
    if word(main, 0x30) != 0x51494255 or word(storage, 0x20) != 0x51494255:
        raise ValueError("Invalid Falcon BIOS markers")
    svc = unique(main, struct.pack("<I", 0xf7f9bff6))
    context = literal(main, svc - 0x60, 0xe59f40e0)
    cursor_insn = word(main, svc - 0x54)
    count_insn = word(main, svc - 0x40)
    if cursor_insn & 0xfffff000 != 0xe5943000 or count_insn & 0xfffff000 != 0xe5953000:
        raise ValueError("Unrecognized Falcon cursor layout")
    cursor = context + (cursor_insn & 0xfff)
    count = literal(main, svc - 0x44, 0xe59f50c8) + (count_insn & 0xfff)
    layouts = [
        (0xe92d4010, 0xe59fe04c, 0xe59ec000, 0xe59c4004, 0xe3540000),
        (0xe92d4030, 0xe59f404c, 0xe594c000, 0xe59c5004, 0xe3550000),
    ]
    matches = [(i, words) for words in layouts
               for i in range(0, len(storage) - 20, 4)
               if storage[i:i + 20] == struct.pack("<5I", *words)]
    if len(matches) != 1:
        raise ValueError("Unrecognized storage BIOS I/O enumerator")
    iterator, instructions = matches[0]
    storage_cursor = literal(storage, iterator + 4, instructions[1])
    main_initial = word(main, cursor - main_base)
    storage_initial = word(storage, storage_cursor - storage_base)
    # Both cursors must point at tables within their respective firmware images.
    word(main, main_initial - main_base)
    word(storage, storage_initial - storage_base)
    word(main, count - main_base)
    return f"""/* Generated from the matching firmware; GPL-2.0-only. */
#ifndef KINDLE_FALCON_REARM_H
#define KINDLE_FALCON_REARM_H
#include <linux/types.h>
#include <linux/errno.h>
static int kindle_falcon_prepare(void)
{{
    /* Refuse a different firmware layout before accepting a kexec image. */
    if (*(volatile u32 *){main_base + 0x30:#x} != 0x51494255 ||
        *(volatile u32 *){storage_base + 0x20:#x} != 0x51494255 ||
        *(volatile u32 *){main_base + svc:#x} != 0xf7f9bff6 ||
        *(volatile u32 *){storage_base + iterator + 4:#x} != {instructions[1]:#x})
        return -EINVAL;
    return 0;
}}
static void kindle_falcon_rearm(void)
{{
    /* Executed after device shutdown, before the final cache clean.
     * Keep the running BIOS and its bootloader-installed exception hooks;
     * let the next kernel enumerate and replace every I/O mapping again. */
    *(volatile u32 *){cursor:#x} = {main_initial:#x};
    *(volatile u32 *){count:#x} = 0;
    *(volatile u32 *){storage_cursor:#x} = {storage_initial:#x};
}}
#endif
"""


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("bios", type=Path)
    p.add_argument("storage_bios", type=Path)
    p.add_argument("bios_address", type=lambda s: int(s, 0))
    p.add_argument("storage_address", type=lambda s: int(s, 0))
    p.add_argument("output", type=Path)
    a = p.parse_args()
    a.output.write_text(generate(a.bios.read_bytes(), a.storage_bios.read_bytes(),
                                a.bios_address, a.storage_address))
