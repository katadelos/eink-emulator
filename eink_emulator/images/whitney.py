#!/usr/bin/env python3
"""Build a sparse Whitney eMMC image from a uImage and rootfs image."""

import os
import struct
import tempfile
from pathlib import Path
from typing import BinaryIO

from .common import atomic_output
from . import rootfs as rootfs_tools
from .yoshi import (
    EMMC_SIZE,
    KERNEL_OFFSET,
    P1_START,
    PARTITIONS,
    SECTOR_SIZE,
    partition_entry,
    write_kernel_and_rootfs,
    write_partition_table,
)


P1_SIZE = PARTITIONS[0][3] * SECTOR_SIZE
USERSTORE_START = PARTITIONS[3][2]
USERSTORE_SECTORS = PARTITIONS[3][3]
USERSTORE_INNER_START = 16
USERSTORE_RESERVED = 9150
USERSTORE_FAT_SECTORS = 1569


def validate_kernel(kernel: Path) -> None:
    with kernel.open("rb") as source:
        if source.read(4) != b"\x27\x05\x19\x56":
            raise SystemExit("Whitney kernel is not a legacy uImage")
    if KERNEL_OFFSET + kernel.stat().st_size > P1_START * SECTOR_SIZE:
        raise SystemExit("Whitney kernel overlaps partition 1")


def provision_userstore(disk: BinaryIO) -> None:
    """Create the nested MBR/FAT32 layout expected by recovery-util."""
    inner_sectors = USERSTORE_SECTORS - USERSTORE_INNER_START
    userstore_offset = USERSTORE_START * SECTOR_SIZE
    filesystem_sector = USERSTORE_START + USERSTORE_INNER_START

    inner_mbr = bytearray(SECTOR_SIZE)
    struct.pack_into("<I", inner_mbr, 440, 2)
    inner_mbr[446:462] = partition_entry(
        False,
        0x0B,
        USERSTORE_INNER_START,
        inner_sectors,
        start_chs=b"\x00\x01\x01",
    )
    inner_mbr[510:512] = b"\x55\xaa"
    disk.seek(userstore_offset)
    disk.write(inner_mbr)

    boot = bytearray(SECTOR_SIZE)
    boot[0:3] = b"\xeb\x58\x90"
    boot[3:11] = b"mkdosfs\x00"
    struct.pack_into("<H", boot, 11, SECTOR_SIZE)
    boot[13] = 16
    struct.pack_into("<H", boot, 14, USERSTORE_RESERVED)
    boot[16] = 2
    boot[21] = 0xF8
    struct.pack_into("<H", boot, 24, 32)
    struct.pack_into("<H", boot, 26, 64)
    struct.pack_into("<I", boot, 32, inner_sectors)
    struct.pack_into("<I", boot, 36, USERSTORE_FAT_SECTORS)
    struct.pack_into("<I", boot, 44, 2)
    struct.pack_into("<H", boot, 48, 1)
    struct.pack_into("<H", boot, 50, 6)
    boot[66] = 0x29
    struct.pack_into("<I", boot, 67, 2)
    boot[71:82] = b"Kindle     "
    boot[82:90] = b"FAT32   "
    boot[510:512] = b"\x55\xaa"

    fsinfo = bytearray(SECTOR_SIZE)
    fsinfo[0:4] = b"RRaA"
    fsinfo[484:488] = b"rrAa"
    struct.pack_into("<I", fsinfo, 488, 0xFFFFFFFF)
    struct.pack_into("<I", fsinfo, 492, 2)
    fsinfo[510:512] = b"\x55\xaa"

    disk.seek(filesystem_sector * SECTOR_SIZE)
    disk.write(boot)
    disk.write(fsinfo)
    disk.seek((filesystem_sector + 6) * SECTOR_SIZE)
    disk.write(boot)
    disk.seek((filesystem_sector + 7) * SECTOR_SIZE)
    disk.write(fsinfo)

    fat_prefix = bytes.fromhex("f8ffff0fffffff0ff8ffff0f")
    first_fat = filesystem_sector + USERSTORE_RESERVED
    for fat_sector in (
        first_fat,
        first_fat + USERSTORE_FAT_SECTORS,
    ):
        disk.seek(fat_sector * SECTOR_SIZE)
        disk.write(fat_prefix)


def build(output: Path, kernel: Path, rootfs: Path) -> None:
    """Build a sparse Whitney eMMC image."""
    validate_kernel(kernel)
    with atomic_output(output) as temporary:
        with tempfile.TemporaryDirectory(prefix="whitney-rootfs-") as temp_dir:
            prepared_rootfs = Path(temp_dir) / "rootfs.img"
            rootfs_tools.prepare_whitney(
                rootfs, prepared_rootfs, maximum_size=P1_SIZE
            )

            with temporary.open("w+b") as disk:
                disk.truncate(EMMC_SIZE)
                write_partition_table(disk, disk_signature=2)
                provision_userstore(disk)
                write_kernel_and_rootfs(disk, kernel, prepared_rootfs)

                disk.flush()
                os.fsync(disk.fileno())
