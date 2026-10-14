#!/usr/bin/env python3
"""Capture Clara HD boot/system partitions without reading its userstore."""

from __future__ import annotations

import argparse
import os
import struct
import tempfile
from pathlib import Path
from typing import BinaryIO

ROOT = Path(__file__).resolve().parent.parent
SECTOR = 512
ROOT_START = 49152
RECOVERY_START = 573441
USER_START = 1097730
SYSTEM_SECTORS = 524289


def read_exact(source: BinaryIO, offset: int, length: int) -> bytes:
    """Issue only sector-aligned reads, bounded before the userstore."""
    if offset < 0 or length < 0 or offset % SECTOR or length % SECTOR:
        raise ValueError("capture reads must be sector aligned")
    if offset + length > USER_START * SECTOR:
        raise ValueError("capture would overlap the userstore")
    source.seek(offset)
    data = source.read(length)
    if len(data) != length:
        raise ValueError(f"short read at byte {offset}: {len(data)} of {length}")
    return data


def validate_mbr(mbr: bytes) -> None:
    if mbr[510:512] != b"\x55\xaa":
        raise ValueError("missing MBR signature")
    for index, start in enumerate((ROOT_START, RECOVERY_START, USER_START)):
        entry = mbr[446 + index * 16:462 + index * 16]
        actual, sectors = struct.unpack_from("<II", entry, 8)
        types = (0x83,) if index < 2 else (0x0b, 0x0c)
        if (entry[0] not in (0, 0x80) or entry[4] not in types or
                actual != start or not sectors or
                (index < 2 and sectors != SYSTEM_SECTORS)):
            raise ValueError(f"partition {index + 1} does not match the Clara HD card layout")
    if any(mbr[494:510]):
        raise ValueError("unexpected fourth partition")


def extract_uboot(region: bytes) -> bytes:
    ivt = 0x400
    if region[ivt:ivt + 4] != b"\xd1\x00\x20\x40":
        raise ValueError("missing i.MX U-Boot IVT at sector 2")
    entry = struct.unpack_from("<I", region, ivt + 4)[0]
    boot_data, address = struct.unpack_from("<II", region, ivt + 0x10)
    data_offset = ivt + boot_data - address
    if not ivt <= data_offset <= 0x80000 - 12:
        raise ValueError("U-Boot boot-data pointer lies outside the bootloader")
    start, size, plugin = struct.unpack_from("<III", region, data_offset)
    length = size - (address - start)
    if (plugin or address < start or length < 0x20 or
            ivt + length > 0x80000 or
            not 0x80000000 <= address < address + length <= 0xa0000000 or
            not address <= entry < address + length):
        raise ValueError("invalid U-Boot image extent or entry point")
    return region[ivt:ivt + length]


def capture(source_path: Path, output: Path) -> None:
    if output.exists():
        raise ValueError(f"destination already exists: {output}")
    with source_path.open("rb", buffering=0) as source:
        validate_mbr(read_exact(source, 0, SECTOR))
        hwconfig = read_exact(source, 0x80000, SECTOR)
        if hwconfig[:10] != b"HW CONFIG " or hwconfig[15] < 1 or hwconfig[16] != 74:
            raise ValueError("hardware configuration does not identify a Clara HD (PCB 74)")
        region = read_exact(source, 0, ROOT_START * SECTOR)
        bootloader = extract_uboot(region)
        output.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".clara-capture-", dir=output.parent) as temporary:
            staging = Path(temporary) / "firmware"
            staging.mkdir(mode=0o755)
            (staging / "boot-region.img").write_bytes(region)
            (staging / "u-boot.imx").write_bytes(bootloader)
            for name, start in (("rootfs.img", ROOT_START),
                                ("recoveryfs.img", RECOVERY_START)):
                print(f"Capturing {name} ({SYSTEM_SECTORS * SECTOR:,} bytes)", flush=True)
                offset, remaining = start * SECTOR, SYSTEM_SECTORS * SECTOR
                with (staging / name).open("wb") as target:
                    while remaining:
                        length = min(4 * 1024 * 1024, remaining)
                        target.write(read_exact(source, offset, length))
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
    parser.add_argument("source", type=Path, help="whole SD device, e.g. /dev/rdisk18")
    parser.add_argument("--output", type=Path, default=ROOT / "firmware/kobo-clara-hd")
    args = parser.parse_args()
    try:
        capture(args.source, args.output.resolve())
    except (OSError, ValueError) as error:
        parser.exit(1, f"capture failed: {error}\n")


if __name__ == "__main__":
    main()
