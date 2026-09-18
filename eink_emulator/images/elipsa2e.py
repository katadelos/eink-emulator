"""Compact Elipsa 2E eMMC, using stock FIT firmware and partition dumps."""
from __future__ import annotations

import shutil
import struct
import subprocess
import zlib
from pathlib import Path

from . import rootfs
from .common import atomic_output
from .forma import write_userstore

DISK_SIZE = 2 * 1024**3
USER_START = 1427456
PARTITIONS = (
    ("bl2", 1024, 1024), ("bootloader", 2048, 2048),
    ("nvram", 36864, 2048), ("boot_image", 38912, 65536),
    ("tee", 104448, 8192), ("hwcfg", 112640, 2048),
    ("ntxfw", 114688, 2048), ("waveform", 116736, 20480),
    ("vendor", 137216, 40960), ("rootfs", 198656, 614400),
    ("recoveryfs", 813056, 614400),
)


def prepare_root(source: Path, output: Path, *, sideloaded: bool) -> None:
    rootfs.copy_source(source, output, maximum_size=300 * 1024**2)
    # The live dump has a coherent, fully flushed inode table but stale journal
    # transactions. Replaying those resurrects old inode mappings over current
    # files. Validate the captured filesystem directly, on our disposable copy.
    rootfs.run(output, "feature -needs_recovery", writable=True)
    subprocess.run([str(rootfs.find_debugfs().with_name("tune2fs")),
                    "-O", "^has_journal", str(output)], check=True)
    result = subprocess.run([str(rootfs.find_debugfs().with_name("e2fsck")),
                             "-fp", str(output)], check=False)
    if result.returncode not in (0, 1):
        raise ValueError("Could not recover the Elipsa 2E root filesystem")
    rootfs.run(output, "rm /etc/udev.tgz", writable=True)
    if sideloaded:
        rootfs.install_overrides(image=output, group="elipsa2e", replacements={
            "/etc/init.d/eink-sideloaded": ("etc/init.d/eink-sideloaded", "0100755"),
        })
        def patch_startup(contents: str) -> str:
            needle = "/usr/local/Kobo/hindenburg &"
            if contents.count(needle) != 1:
                raise ValueError("Unrecognized Elipsa 2E Hindenburg startup")
            return contents.replace(needle, "/etc/init.d/eink-sideloaded\n" + needle)
        rootfs.transform_file(output, "/etc/init.d/rcS", "0100755", patch_startup)
    rootfs.transform_file(output, "/etc/passwd", "0100644", rootfs.blank_root_password)


def write_gpt(disk, region: bytes) -> None:
    """Retain partition UUIDs and offsets, relocating the backup GPT."""
    header = bytearray(region[512:1024])
    if header[:8] != b"EFI PART":
        raise ValueError("Elipsa 2E requires a GPT boot-region dump")
    table_lba, count, entry_size = struct.unpack_from("<QII", header, 72)
    if count != 128 or entry_size != 128 or table_lba != 2:
        raise ValueError("Unexpected Elipsa 2E GPT geometry")
    table = bytearray(region[table_lba * 512:table_lba * 512 + count * entry_size])
    for index, (_, start, sectors) in enumerate(PARTITIONS):
        if struct.unpack_from("<QQ", table, index * 128 + 32) != (start, start + sectors - 1):
            raise ValueError(f"Unexpected Elipsa 2E partition {index + 1}")
    if struct.unpack_from("<Q", table, 11 * 128 + 32)[0] != USER_START:
        raise ValueError("Unexpected Elipsa 2E userstore offset")
    last = DISK_SIZE // 512 - 1
    struct.pack_into("<Q", table, 11 * 128 + 40, last - 33)
    struct.pack_into("<I", header, 88, zlib.crc32(table))
    mbr = bytearray(region[:512])
    struct.pack_into("<I", mbr, 446 + 12, last)
    disk.seek(0)
    disk.write(mbr)
    for current, backup, table_at in ((1, last, 2), (last, 1, last - 32)):
        struct.pack_into("<QQ", header, 24, current, backup)
        struct.pack_into("<Q", header, 48, last - 33)
        struct.pack_into("<Q", header, 72, table_at)
        struct.pack_into("<I", header, 16, 0)
        header_size = struct.unpack_from("<I", header, 12)[0]
        struct.pack_into("<I", header, 16, zlib.crc32(header[:header_size]))
        disk.seek(current * 512)
        disk.write(header)
        disk.seek(table_at * 512)
        disk.write(table)


def build(output: Path, artifacts: dict[str, Path], *, sideloaded: bool = False) -> None:
    prepared = output.with_name("prepared-rootfs.img")
    prepare_root(artifacts["rootfs"], prepared, sideloaded=sideloaded)
    with atomic_output(output) as staging, staging.open("wb") as disk:
        disk.truncate(DISK_SIZE)
        write_gpt(disk, artifacts["boot_region"].read_bytes())
        for role, start, sectors in PARTITIONS:
            source = prepared if role == "rootfs" else artifacts[role]
            if source.stat().st_size > sectors * 512:
                raise ValueError(f"{source.name} exceeds its Elipsa 2E partition")
            disk.seek(start * 512)
            with source.open("rb") as stream:
                shutil.copyfileobj(stream, disk)
        write_userstore(disk, start=USER_START, end=DISK_SIZE // 512 - 33)
