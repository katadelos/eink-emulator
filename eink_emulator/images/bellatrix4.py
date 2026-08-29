"""Build a sparse Bellatrix4 disk image from firmware components."""

from __future__ import annotations

import errno
import os
import shutil
import struct
import subprocess
import tempfile
import uuid
import zlib
from pathlib import Path
from typing import BinaryIO


SECTOR_SIZE = 512
ENTRY_COUNT = 128
ENTRY_SIZE = 128
LINUX_FS = uuid.UUID("0fc63daf-8483-4772-8e79-3d69d8477de4")
PRECHARGE_DATA_SIZE = 6
PRECHARGE_MAGIC = 0xFACE
USERSTORE_FS_OFFSET = 8192
USERSTORE_RESERVED_BLOCKS = 89600
ROOTFS_SIZE = 768 * 1024**2

# Recovery userspace identifies p1/p2/p8/p9/p10 directly, and boot.img mounts
# p8 as root. Stock U-Boot also looks up wfm, snapshot, reserved0, and miscdata
# by GPT name. The vendor update does not publish the factory p3-p7 geometry,
# so the intermediate sizes reserve space for those contracts.
PARTITIONS = [
    ("kernel", 64 * 1024**2),
    ("wfm", 64 * 1024**2),
    ("diags_kernel", 64 * 1024**2),
    ("diags", 768 * 1024**2),
    ("snapshot", 1024 * 1024**2),
    ("reserved0", 16 * 1024**2),
    ("miscdata", 512 * 1024**2),
    ("rootfs", ROOTFS_SIZE),
    ("varlocal", 512 * 1024**2),
]


def guid_bytes(value: uuid.UUID) -> bytes:
    return value.bytes_le


def make_header(
    current: int,
    backup: int,
    entries_lba: int,
    first_usable: int,
    last_usable: int,
    disk_guid: uuid.UUID,
    entries_crc: int,
) -> bytes:
    header = bytearray(SECTOR_SIZE)
    struct.pack_into(
        "<8sIIIIQQQQ16sQIII",
        header,
        0,
        b"EFI PART",
        0x00010000,
        92,
        0,
        0,
        current,
        backup,
        first_usable,
        last_usable,
        guid_bytes(disk_guid),
        entries_lba,
        ENTRY_COUNT,
        ENTRY_SIZE,
        entries_crc,
    )
    struct.pack_into("<I", header, 16, zlib.crc32(header[:92]))
    return bytes(header)


def partition_layout(size: int) -> list[tuple[str, int, int]]:
    last_usable = size // SECTOR_SIZE - 34
    cursor = 2048
    layout: list[tuple[str, int, int]] = []
    for name, byte_size in PARTITIONS:
        sectors = byte_size // SECTOR_SIZE
        layout.append((name, cursor, sectors))
        cursor += sectors
    if cursor > last_usable:
        raise SystemExit("image is too small for the Bellatrix4 partition layout")
    layout.append(("userstore", cursor, last_usable - cursor + 1))
    return layout


def create_image(path: Path, size: int) -> dict[str, tuple[int, int]]:
    sectors = size // SECTOR_SIZE
    first_usable = 34
    last_usable = sectors - 34
    layout = partition_layout(size)

    entries = bytearray(ENTRY_COUNT * ENTRY_SIZE)
    for index, (name, start, count) in enumerate(layout):
        unique = uuid.uuid5(uuid.NAMESPACE_DNS, f"eink-emulator-bellatrix4-{name}")
        encoded_name = name.encode("utf-16-le")
        struct.pack_into(
            "<16s16sQQQ72s",
            entries,
            index * ENTRY_SIZE,
            guid_bytes(LINUX_FS),
            guid_bytes(unique),
            start,
            start + count - 1,
            0,
            encoded_name.ljust(72, b"\0"),
        )

    entries_crc = zlib.crc32(entries)
    disk_guid = uuid.uuid5(uuid.NAMESPACE_DNS, "eink-emulator-bellatrix4")
    primary = make_header(
        1,
        sectors - 1,
        2,
        first_usable,
        last_usable,
        disk_guid,
        entries_crc,
    )
    backup_entries_lba = sectors - 33
    backup = make_header(
        sectors - 1,
        1,
        backup_entries_lba,
        first_usable,
        last_usable,
        disk_guid,
        entries_crc,
    )

    mbr = bytearray(SECTOR_SIZE)
    mbr[446:462] = struct.pack(
        "<B3sB3sII",
        0,
        b"\0\x02\0",
        0xEE,
        b"\xff\xff\xff",
        1,
        min(sectors - 1, 0xFFFFFFFF),
    )
    mbr[510:512] = b"\x55\xaa"

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as image:
        image.truncate(size)
        image.seek(0)
        image.write(mbr)
        image.write(primary)
        image.write(entries)
        image.seek(backup_entries_lba * SECTOR_SIZE)
        image.write(entries)
        image.write(backup)
    return {name: (start, count) for name, start, count in layout}


def find_tool(name: str) -> Path:
    configured = os.environ.get(name.upper())
    candidates = (
        configured,
        shutil.which(name),
        f"/opt/homebrew/opt/e2fsprogs/sbin/{name}",
        f"/usr/local/opt/e2fsprogs/sbin/{name}",
        f"/usr/sbin/{name}",
        f"/sbin/{name}",
    )
    for candidate in candidates:
        if candidate and Path(candidate).is_file() and os.access(candidate, os.X_OK):
            return Path(candidate)
    raise SystemExit(f"{name} is required (install e2fsprogs or set {name.upper()})")


def copy_sparse(source_path: Path, destination: BinaryIO, destination_offset: int) -> None:
    payload_size = source_path.stat().st_size
    with source_path.open("rb", buffering=0) as source:
        source_fd = source.fileno()
        position = 0
        while position < payload_size:
            try:
                data_start = os.lseek(source_fd, position, os.SEEK_DATA)
            except OSError as error:
                if error.errno == errno.ENXIO:
                    break
                if error.errno in (errno.EINVAL, errno.ENOTSUP):
                    data_start = position
                else:
                    raise
            try:
                data_end = os.lseek(source_fd, data_start, os.SEEK_HOLE)
            except OSError as error:
                if error.errno in (errno.EINVAL, errno.ENOTSUP):
                    data_end = payload_size
                else:
                    raise
            data_end = min(data_end, payload_size)
            source.seek(data_start)
            destination.seek(destination_offset + data_start)
            remaining = data_end - data_start
            while remaining:
                chunk = source.read(min(1024 * 1024, remaining))
                if not chunk:
                    raise SystemExit(f"short read from {source_path}")
                destination.write(chunk)
                remaining -= len(chunk)
            position = data_end


def write_partition(
    image_path: Path,
    layout: dict[str, tuple[int, int]],
    name: str,
    payload_path: Path,
) -> None:
    start, sectors = layout[name]
    if payload_path.stat().st_size > sectors * SECTOR_SIZE:
        raise SystemExit(f"{payload_path}: payload is larger than the '{name}' partition")
    with image_path.open("r+b", buffering=0) as image:
        copy_sparse(payload_path, image, start * SECTOR_SIZE)


def initialize_factory_data(
    image_path: Path, layout: dict[str, tuple[int, int]]
) -> None:
    start, _ = layout["reserved0"]
    offset = start * SECTOR_SIZE
    with image_path.open("r+b") as image:
        image.seek(offset)
        current = image.read(PRECHARGE_DATA_SIZE)
        if current == bytes(PRECHARGE_DATA_SIZE):
            image.seek(offset)
            image.write(struct.pack("<BBHBB", 0, 0, PRECHARGE_MAGIC, 0, 0))


def create_userstore(
    image_path: Path, layout: dict[str, tuple[int, int]]
) -> None:
    start, sectors = layout["userstore"]
    filesystem_size = sectors * SECTOR_SIZE - USERSTORE_FS_OFFSET
    if filesystem_size <= USERSTORE_RESERVED_BLOCKS * 4096:
        raise SystemExit("userstore partition is too small")

    mke2fs = find_tool("mke2fs")
    tune2fs = find_tool("tune2fs")
    with tempfile.TemporaryDirectory(
        prefix="bellatrix4-userstore-", dir=image_path.parent
    ) as temporary:
        filesystem = Path(temporary) / "userstore.ext4"
        with filesystem.open("wb") as image:
            image.truncate(filesystem_size)
        subprocess.run(
            [
                mke2fs,
                "-q",
                "-t",
                "ext4",
                "-F",
                "-i",
                "32768",
                "-O",
                "encrypt,^metadata_csum_seed,^orphan_file",
                "-b",
                "4096",
                filesystem,
            ],
            check=True,
        )
        subprocess.run(
            [
                tune2fs,
                "-i",
                "0",
                "-c",
                "0",
                "-r",
                str(USERSTORE_RESERVED_BLOCKS),
                "-e",
                "remount-ro",
                filesystem,
            ],
            check=True,
            stdout=subprocess.DEVNULL,
        )
        with image_path.open("r+b", buffering=0) as image:
            copy_sparse(
                filesystem,
                image,
                start * SECTOR_SIZE + USERSTORE_FS_OFFSET,
            )


def build(
    image: Path,
    *,
    boot_image: Path,
    rootfs_image: Path,
    waveform_image: Path,
    size: int = 8 * 1024**3,
) -> None:
    """Compose the QEMU disk from the supplied firmware components."""
    if size % SECTOR_SIZE or size < 4 * 1024**3:
        raise SystemExit("image size must be sector-aligned and at least 4 GiB")
    for payload in (boot_image, rootfs_image, waveform_image):
        if not payload.is_file():
            raise SystemExit(f"payload does not exist: {payload}")

    layout = create_image(image, size)
    write_partition(image, layout, "kernel", boot_image)
    write_partition(image, layout, "rootfs", rootfs_image)
    write_partition(image, layout, "wfm", waveform_image)
    initialize_factory_data(image, layout)
    create_userstore(image, layout)
