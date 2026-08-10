"""Shared Kindle 4 and Kindle Touch eMMC layout primitives."""

from __future__ import annotations

import shutil
import struct
from pathlib import Path
from typing import BinaryIO


SECTOR_SIZE = 512
EMMC_SIZE = 2 * 1024 * 1024 * 1024
KERNEL_OFFSET = 0x41000
P1_START = 0x10000
PARTITIONS = (
    (True, 0x83, P1_START, 0xAF000),
    (False, 0x83, 0xBF000, 0x20000),
    (False, 0x83, 0xDF000, 0x10000),
    (False, 0x0B, 0xEF000, 0x311000),
)


def partition_entry(
    bootable: bool,
    partition_type: int,
    start: int,
    sectors: int,
    start_chs: bytes = b"\x03\xd0\xff",
    end_chs: bytes = b"\x03\xd0\xff",
) -> bytes:
    return struct.pack(
        "<B3sB3sII",
        0x80 if bootable else 0,
        start_chs,
        partition_type,
        end_chs,
        start,
        sectors,
    )


def write_partition_table(
    disk: BinaryIO, *, disk_signature: int | None = None,
    chs: bytes = b"\x03\xd0\xff",
) -> None:
    mbr = bytearray(SECTOR_SIZE)
    if disk_signature is not None:
        struct.pack_into("<I", mbr, 440, disk_signature)
    for index, partition in enumerate(PARTITIONS):
        offset = 446 + index * 16
        mbr[offset:offset + 16] = partition_entry(
            *partition, start_chs=chs, end_chs=chs
        )
    mbr[510:512] = b"\x55\xaa"
    disk.seek(0)
    disk.write(mbr)


def write_kernel_and_rootfs(
    disk: BinaryIO, kernel: Path, rootfs: Path
) -> None:
    disk.seek(KERNEL_OFFSET)
    with kernel.open("rb") as source:
        shutil.copyfileobj(source, disk, 8 * 1024 * 1024)
    disk.seek(P1_START * SECTOR_SIZE)
    with rootfs.open("rb") as source:
        shutil.copyfileobj(source, disk, 8 * 1024 * 1024)
