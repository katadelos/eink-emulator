"""Build a Clara HD SD card with a fresh, exactly 1 GiB FAT32 userstore."""
from __future__ import annotations

import shutil
import struct
import subprocess
from dataclasses import dataclass
from pathlib import Path

from . import rootfs
from .common import atomic_output
from .forma import write_userstore
from .kobo import prepare_network

SECTOR_SIZE = 512
USERSTORE_SIZE = 1024**3
HWCFG_OFFSET = 512 * 1024


@dataclass(frozen=True)
class Partition:
    start: int
    sectors: int
    type: int

    @property
    def end(self) -> int:
        """The first sector after this partition."""
        return self.start + self.sectors


def parse_layout(mbr: bytes) -> tuple[Partition, Partition, Partition]:
    """Validate Clara's three primary partitions without reading userstore."""
    if len(mbr) != SECTOR_SIZE or mbr[510:512] != b"\x55\xaa":
        raise ValueError("Clara HD requires a valid 512-byte MBR")
    partitions = []
    previous_end = 1
    for index, types in enumerate(({0x83}, {0x83}, {0x0b, 0x0c})):
        entry = mbr[446 + index * 16:462 + index * 16]
        start, sectors = struct.unpack_from("<II", entry, 8)
        partition = Partition(start, sectors, entry[4])
        if entry[0] not in (0, 0x80) or partition.type not in types:
            raise ValueError(f"Unexpected Clara HD partition {index + 1} type or status")
        if not sectors or start < previous_end or partition.end > 2**32:
            raise ValueError(f"Invalid or overlapping Clara HD partition {index + 1}")
        partitions.append(partition)
        previous_end = partition.end
    if any(mbr[494:510]):
        raise ValueError("Clara HD requires an unused fourth MBR partition")
    return tuple(partitions)


def prepare_root(source: Path, output: Path, *, size: int) -> None:
    rootfs.copy_source(source, output, maximum_size=size)
    result = subprocess.run([str(rootfs.find_debugfs().with_name("e2fsck")),
                             "-p", str(output)], check=False)
    if result.returncode not in (0, 1):
        raise ValueError("Could not recover the Clara HD root filesystem")
    rootfs.run(output, "rm /etc/udev.tgz", writable=True)
    prepare_network(output)


def build(output: Path, artifacts: dict[str, Path]) -> None:
    region = artifacts["boot_region"].read_bytes()
    root, recovery, user = parse_layout(region[:SECTOR_SIZE])
    if len(region) != root.start * SECTOR_SIZE:
        raise ValueError("Clara HD requires the complete region before partition 1")
    hwconfig = region[HWCFG_OFFSET:HWCFG_OFFSET + SECTOR_SIZE]
    if (len(hwconfig) != SECTOR_SIZE or hwconfig[:10] != b"HW CONFIG " or
            hwconfig[15] < 1 or hwconfig[16] != 74):
        raise ValueError("Clara HD boot region requires the PCB 74 hardware configuration")
    for role, partition in (("rootfs", root), ("recoveryfs", recovery)):
        source = artifacts[role]
        if source.stat().st_size != partition.sectors * SECTOR_SIZE:
            raise ValueError(f"{source.name} must match its complete Clara HD partition")
        with source.open("rb") as stream:
            stream.seek(rootfs.EXT_MAGIC_OFFSET)
            if stream.read(2) != b"\x53\xef":
                raise ValueError(f"{source.name} is not an ext filesystem")
    prepared = output.with_name("prepared-rootfs.img")
    prepare_root(artifacts["rootfs"], prepared, size=root.sectors * SECTOR_SIZE)
    user_end = user.start + USERSTORE_SIZE // SECTOR_SIZE
    # QEMU's SD card requires a power-of-two capacity. Leave any padding
    # unpartitioned; partition 3 itself remains exactly 1 GiB.
    disk_size = 1 << ((user_end * SECTOR_SIZE - 1).bit_length())
    with atomic_output(output) as staging, staging.open("wb") as disk:
        disk.truncate(disk_size)
        disk.write(region)
        disk.seek(446 + 2 * 16 + 12)
        disk.write(struct.pack("<I", USERSTORE_SIZE // SECTOR_SIZE))
        for source, partition in ((prepared, root), (artifacts["recoveryfs"], recovery)):
            disk.seek(partition.start * SECTOR_SIZE)
            with source.open("rb") as stream:
                shutil.copyfileobj(stream, disk)
        write_userstore(disk, start=user.start, end=user_end)
