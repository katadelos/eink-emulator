#!/usr/bin/env python3
"""Carve supported Kobo boot/system partitions without reading the userstore."""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path
from typing import BinaryIO

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from eink_emulator.images.kobo_sd import (
    BOARDS, HWCFG_OFFSET, SECTOR_SIZE, extract_uboot, identify_board, parse_layout,
)


def read_exact(source: BinaryIO, offset: int, length: int, *, limit: int) -> bytes:
    """Issue only sector-aligned reads, bounded before the userstore."""
    if offset < 0 or length < 0 or offset % SECTOR_SIZE or length % SECTOR_SIZE:
        raise ValueError("capture reads must be sector aligned")
    if offset + length > limit:
        raise ValueError("capture would overlap the userstore")
    source.seek(offset)
    data = source.read(length)
    if len(data) != length:
        raise ValueError(f"short read at byte {offset}: {len(data)} of {length}")
    return data


def carve(source_path: Path, output: Path | None, *, model: str | None) -> None:
    with source_path.open("rb", buffering=0) as source:
        mbr = read_exact(source, 0, SECTOR_SIZE, limit=SECTOR_SIZE)
        root, recovery, user = parse_layout(mbr)
        limit = user.start * SECTOR_SIZE
        region_size = root.start * SECTOR_SIZE
        if region_size < HWCFG_OFFSET + SECTOR_SIZE:
            raise ValueError("Kobo boot region does not contain its hardware configuration")
        board = identify_board(read_exact(source, HWCFG_OFFSET, SECTOR_SIZE, limit=limit))
        if model and board.model != model:
            raise ValueError(f"Expected {model}, found {board.model}")
        output = (output or ROOT / "firmware" / board.model).resolve()
        if output.exists():
            raise ValueError(f"destination already exists: {output}")
        region = read_exact(source, 0, region_size, limit=limit)
        bootloader = extract_uboot(region, board)
        output.parent.mkdir(parents=True, exist_ok=True)
        print(f"Found Kobo {board.description} (PCB {board.pcb})", flush=True)
        with tempfile.TemporaryDirectory(prefix=".kobo-carve-", dir=output.parent) as temporary:
            staging = Path(temporary) / "firmware"
            staging.mkdir(mode=0o755)
            (staging / "boot-region.img").write_bytes(region)
            (staging / board.bootloader_name).write_bytes(bootloader)
            for name, partition in (("rootfs.img", root), ("recoveryfs.img", recovery)):
                offset = partition.start * SECTOR_SIZE
                remaining = partition.sectors * SECTOR_SIZE
                print(f"Capturing {name} ({remaining:,} bytes)", flush=True)
                with (staging / name).open("wb") as target:
                    while remaining:
                        length = min(4 * 1024 * 1024, remaining)
                        target.write(read_exact(source, offset, length, limit=limit))
                        offset += length
                        remaining -= length
            if os.geteuid() == 0 and "SUDO_UID" in os.environ:
                uid, gid = int(os.environ["SUDO_UID"]), int(os.environ["SUDO_GID"])
                for path in (*staging.iterdir(), staging):
                    os.chown(path, uid, gid)
            staging.rename(output)
    print(f"Captured firmware in {output}; no userstore sectors were read.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="whole SD image or device, e.g. /dev/rdiskN")
    parser.add_argument("--model", choices=BOARDS, help="require this model instead of only detecting it")
    parser.add_argument("--output", type=Path, help="destination (default: firmware/<detected-model>)")
    args = parser.parse_args()
    try:
        carve(args.source, args.output, model=args.model)
    except (OSError, ValueError) as error:
        parser.exit(1, f"carve failed: {error}\n")


if __name__ == "__main__":
    main()
