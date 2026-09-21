#!/usr/bin/env python3
"""Create or populate a sparse PW4/Rex eMMC user-area image."""

import shutil
import struct
import subprocess
import tempfile
import uuid
import zlib
from pathlib import Path
from typing import BinaryIO

from . import bellatrix, imx6_mmc

SECTOR = 512
ENTRY_COUNT = 128
ENTRY_SIZE = 128
LINUX_FS = uuid.UUID("0fc63daf-8483-4772-8e79-3d69d8477de4")

# Partition numbers are part of the stock PW4 boot contract: U-Boot boots the
# partition named "kernel", hibernation uses p6/p7, and boot.img mounts p8.
PARTITIONS = [
    ("kernel", 32 * 1024**2),
    ("recovery", 32 * 1024**2),
    ("keys", 32 * 1024**2),
    ("diags", 32 * 1024**2),
    ("persist", 16 * 1024**2),
    ("miscdata", 64 * 1024**2),
    ("snapshot", 512 * 1024**2),
    ("rootfs", 512 * 1024**2),
    ("varlocal", 512 * 1024**2),
]


def guid_bytes(value: uuid.UUID) -> bytes:
    return value.bytes_le


def make_header(current: int, backup: int, entries_lba: int,
                first_usable: int, last_usable: int,
                disk_guid: uuid.UUID, entries_crc: int) -> bytes:
    header = bytearray(SECTOR)
    struct.pack_into(
        "<8sIIIIQQQQ16sQIII", header, 0,
        b"EFI PART", 0x00010000, 92, 0, 0,
        current, backup, first_usable, last_usable,
        guid_bytes(disk_guid), entries_lba, ENTRY_COUNT, ENTRY_SIZE,
        entries_crc,
    )
    struct.pack_into("<I", header, 16, zlib.crc32(header[:92]))
    return bytes(header)


def partition_layout(size: int) -> list[tuple[str, int, int]]:
    last_usable = size // SECTOR - 34
    cursor = 2048
    layout = []
    for name, byte_size in PARTITIONS:
        sectors = byte_size // SECTOR
        layout.append((name, cursor, sectors))
        cursor += sectors
    if cursor > last_usable:
        raise SystemExit("eMMC image is too small for the Rex partition layout")
    layout.append(("userstore", cursor, last_usable - cursor + 1))
    return layout


def create_image(path: Path, size: int) -> dict[str, tuple[int, int]]:
    sectors = size // SECTOR
    first_usable = 34
    last_usable = sectors - 34
    layout = partition_layout(size)

    entries = bytearray(ENTRY_COUNT * ENTRY_SIZE)
    for index, (name, start, count) in enumerate(layout):
        unique = uuid.uuid5(uuid.NAMESPACE_DNS, f"eink-emulator-rex-{name}")
        encoded_name = name.encode("utf-16-le")
        struct.pack_into(
            "<16s16sQQQ72s", entries, index * ENTRY_SIZE,
            guid_bytes(LINUX_FS), guid_bytes(unique), start,
            start + count - 1, 0, encoded_name.ljust(72, b"\0"),
        )

    entries_crc = zlib.crc32(entries)
    disk_guid = uuid.uuid5(uuid.NAMESPACE_DNS, "eink-emulator-rex")
    primary = make_header(1, sectors - 1, 2, first_usable, last_usable,
                          disk_guid, entries_crc)
    backup_entries_lba = sectors - 33
    backup = make_header(sectors - 1, 1, backup_entries_lba,
                         first_usable, last_usable, disk_guid, entries_crc)

    mbr = bytearray(SECTOR)
    mbr[446:462] = struct.pack("<B3sB3sII", 0, b"\0\x02\0", 0xEE,
                               b"\xff\xff\xff", 1,
                               min(sectors - 1, 0xFFFFFFFF))
    mbr[510:512] = b"\x55\xaa"

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as image:
        image.truncate(size)
        image.seek(0)
        image.write(mbr)
        image.write(primary)
        image.write(entries)
        image.seek(backup_entries_lba * SECTOR)
        image.write(entries)
        image.write(backup)
    return {name: (start, count) for name, start, count in layout}


def read_layout(path: Path) -> dict[str, tuple[int, int]]:
    with path.open("rb") as image:
        image.seek(SECTOR)
        header = image.read(SECTOR)
        if header[:8] != b"EFI PART":
            raise SystemExit(f"{path}: not a GPT eMMC image")
        entries_lba, count, entry_size = struct.unpack_from("<QII", header, 72)
        if entry_size < ENTRY_SIZE:
            raise SystemExit(f"{path}: unsupported GPT entry size")
        image.seek(entries_lba * SECTOR)
        entries = image.read(count * entry_size)

    layout = {}
    for index in range(count):
        entry = entries[index * entry_size:(index + 1) * entry_size]
        if entry[:16] == bytes(16):
            continue
        start, end = struct.unpack_from("<QQ", entry, 32)
        name = entry[56:128].decode("utf-16-le").rstrip("\0")
        layout[name] = (start, end - start + 1)
    return layout


def open_payload(path: Path) -> BinaryIO:
    return path.open("rb")


def write_partition(image_path: Path, layout: dict[str, tuple[int, int]],
                    name: str, payload_path: Path) -> None:
    if name not in layout:
        raise SystemExit(f"{image_path}: missing required '{name}' partition")
    start, sectors = layout[name]
    limit = sectors * SECTOR
    written = 0
    with open_payload(payload_path) as source, image_path.open("r+b") as image:
        image.seek(start * SECTOR)
        while chunk := source.read(1024 * 1024):
            written += len(chunk)
            if written > limit:
                raise SystemExit(
                    f"{payload_path}: payload is larger than the '{name}' partition"
                )
            image.write(chunk)


def build(
    image: Path,
    *,
    boot_image: Path,
    rootfs_image: Path,
    size: int = 8 * 1024**3,
) -> None:
    """Build or populate a sparse Rex eMMC image."""
    if size % SECTOR or size < 2 * 1024**3:
        raise SystemExit("image size must be sector-aligned and at least 2 GiB")
    for payload in (boot_image, rootfs_image):
        if not payload.is_file():
            raise SystemExit(f"payload does not exist: {payload}")

    if image.exists():
        layout = read_layout(image)
    else:
        layout = create_image(image, size)
    write_partition(image, layout, "kernel", boot_image)
    write_partition(image, layout, "rootfs", rootfs_image)
    # Like Jaeger, Rex uses the kernel's built-in waveform with an empty
    # generated FAT store.
    with image.open("r+b") as disk:
        imx6_mmc.write_waveform_store(disk, layout["recovery"][0] * SECTOR)
    with tempfile.TemporaryDirectory(prefix="eink-rex-") as directory:
        for name, label in (("keys", "keys"), ("varlocal", "LocalVars")):
            filesystem = Path(directory) / f"{name}.img"
            with filesystem.open("wb") as disk:
                disk.truncate(layout[name][1] * SECTOR)
            subprocess.run([
                str(bellatrix.find_tool("mke2fs")), "-q", "-t", "ext3",
                "-F", "-L", label, str(filesystem),
            ], check=True)
            write_partition(image, layout, name, filesystem)
    bellatrix.create_vfat_userstore(image, layout)
