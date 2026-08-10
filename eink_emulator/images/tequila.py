#!/usr/bin/env python3
"""Build a sparse Tequila eMMC user-area image from a kernel and rootfs."""

import os
from pathlib import Path

from .common import atomic_output
from .yoshi import (
    EMMC_SIZE,
    KERNEL_OFFSET,
    P1_START,
    PARTITIONS,
    SECTOR_SIZE,
    write_kernel_and_rootfs,
    write_partition_table,
)


ROOTFS_SIZE = PARTITIONS[0][3] * SECTOR_SIZE
EXT_MAGIC_OFFSET = 1024 + 56


def validate(kernel: Path, rootfs: Path) -> None:
    if rootfs.stat().st_size != ROOTFS_SIZE:
        raise SystemExit(
            f"Tequila rootfs must be exactly {ROOTFS_SIZE} bytes"
        )
    with rootfs.open("rb") as source:
        source.seek(EXT_MAGIC_OFFSET)
        if source.read(2) != b"\x53\xef":
            raise SystemExit("Tequila rootfs is not an ext filesystem")
    with kernel.open("rb") as source:
        if source.read(4) != b"\x27\x05\x19\x56":
            raise SystemExit("Tequila kernel is not a legacy uImage")
    if KERNEL_OFFSET + kernel.stat().st_size > P1_START * SECTOR_SIZE:
        raise SystemExit("Tequila kernel overlaps partition 1")


def build(output: Path, kernel: Path, rootfs: Path) -> None:
    """Build a sparse Tequila eMMC image."""
    validate(kernel, rootfs)
    with atomic_output(output) as temporary:
        with temporary.open("w+b") as disk:
            disk.truncate(EMMC_SIZE)
            write_partition_table(disk, chs=b"\xfe\xff\xff")
            write_kernel_and_rootfs(disk, kernel, rootfs)

            disk.flush()
            os.fsync(disk.fileno())
