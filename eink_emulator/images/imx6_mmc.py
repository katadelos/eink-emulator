#!/usr/bin/env python3
"""Build legacy i.MX6 Kindle eMMC user-area images."""

import math
import os
import shutil
import struct
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

SECTOR_SIZE = 512
USER_AREA_OFFSET = 0
KERNEL_OFFSET = 0x41000
DIAGS_KERNEL_OFFSET = 0xE41000
PARTITION_LAYOUTS = {
    # Duet retains the stock system offsets, with a 2 GiB virtual eMMC.
    "duet": (
        (65536, 921600, 0x83, True),
        (987136, 131072, 0x83, False),
        (1118208, 131072, 0x83, False),
        (1249280, 2945024, 0x0B, False),
    ),
    "wario": (
    (65536, 921600, 0x83, True),
    (987136, 131072, 0x83, False),
    (1118208, 131072, 0x83, False),
    (1249280, 6385664, 0x0B, False),
    ),
    "pinot": (
        (65536, 716800, 0x83, True),
        (782336, 131072, 0x83, False),
        (913408, 131072, 0x83, False),
        (1044480, 6688768, 0x0B, False),
    ),
    # Heisenberg is a distinct platform. Its stock bootloader retains the
    # compatible four-partition user-area contract used by these primitives.
    "heisenberg": (
        (65536, 921600, 0x83, True),
        (987136, 131072, 0x83, False),
        (1118208, 131072, 0x83, False),
        (1249280, 6385664, 0x0B, False),
    ),
}
USER_AREA_SECTORS = 7733248
EXT_MAGIC_OFFSET = 1024 + 0x38
WAVEFORM_STORE_OFFSET = 0x1C41000
WAVEFORM_STORE_SIZE = 3836 * 1024


def align_up(value: int, alignment: int) -> int:
    return (value + alignment - 1) // alignment * alignment


def copy_stream(source, target) -> int:
    copied = 0
    while True:
        chunk = source.read(1024 * 1024)
        if not chunk:
            return copied
        target.write(chunk)
        copied += len(chunk)


def make_mbr(partitions) -> bytes:
    mbr = bytearray(SECTOR_SIZE)
    for index, (start, sectors, part_type, bootable) in enumerate(partitions):
        entry = struct.pack(
            "<B3sB3sII",
            0x80 if bootable else 0x00,
            b"\x03\xd0\xff",
            part_type,
            b"\x03\xd0\xff",
            start,
            sectors,
        )
        offset = 446 + index * 16
        mbr[offset:offset + 16] = entry
    mbr[510:512] = b"\x55\xaa"
    return bytes(mbr)


def write_blank_local_partition(disk, output_offset: int) -> None:
    mke2fs = shutil.which("mke2fs") or "/opt/homebrew/opt/e2fsprogs/sbin/mke2fs"
    tune2fs = shutil.which("tune2fs") or "/opt/homebrew/opt/e2fsprogs/sbin/tune2fs"
    if not Path(mke2fs).is_file():
        raise SystemExit("mke2fs is required to create the blank p3 local-data filesystem")
    if not Path(tune2fs).is_file():
        raise SystemExit("tune2fs is required to create the blank p3 local-data filesystem")
    with tempfile.NamedTemporaryFile(prefix="wario-local-", suffix=".img") as image:
        image.truncate(64 * 1024 * 1024)
        image.flush()
        # Match /etc/upstart/filesystems_var_local.conf exactly:
        #   mkfs.ext3 -F -L LocalVars $local
        #   tune2fs -c 0 -i 0 $local
        subprocess.run(
            [mke2fs, "-q", "-t", "ext3", "-F", "-L", "LocalVars",
             image.name],
            check=True,
        )
        subprocess.run(
            [tune2fs, "-c", "0", "-i", "0", image.name],
            stdout=subprocess.DEVNULL,
            check=True,
        )
        image.seek(0)
        disk.seek(output_offset)
        copy_stream(image, disk)


def write_local_partition(disk, output_offset: int,
                          local_partition: Path | None) -> None:
    if not local_partition:
        write_blank_local_partition(disk, output_offset)
        return

    disk.seek(output_offset)
    with local_partition.open("rb") as source:
        copy_stream(source, disk)


@dataclass
class FatNode:
    name: str
    source: Path | None = None
    children: list["FatNode"] = field(default_factory=list)
    first_cluster: int = 0
    clusters: list[int] = field(default_factory=list)

    @property
    def is_dir(self) -> bool:
        return self.source is None

    @property
    def size(self) -> int:
        return 0 if self.source is None else self.source.stat().st_size


def build_fat_tree(source: Path) -> FatNode:
    """Build a deterministic tree, omitting host metadata from the image."""
    root = FatNode("")

    def add_directory(parent: FatNode, directory: Path) -> None:
        for path in sorted(directory.iterdir(), key=lambda item: item.name):
            if path.name == ".DS_Store":
                continue
            node = FatNode(path.name, None if path.is_dir() else path)
            parent.children.append(node)
            if path.is_dir():
                add_directory(node, path)

    payload_root = FatNode(source.name)
    root.children.append(payload_root)
    add_directory(payload_root, source)

    # install.sh creates this before copying the package to the userstore.
    etc = next((node for node in payload_root.children if node.name == "etc"), None)
    if etc:
        config = next((node for node in etc.children if node.name == "config"), None)
        if config:
            etc.children.append(FatNode("config.default", config.source))
            etc.children.sort(key=lambda node: node.name)
    return root


def iter_fat_nodes(root: FatNode):
    yield root
    for child in root.children:
        yield from iter_fat_nodes(child)


def fat_short_name(index: int) -> bytes:
    # Every entry also gets an LFN, so an opaque deterministic alias is enough.
    return f"X{index:07X}".encode("ascii") + b"   "


def write_userstore(disk, output_offset: int, sectors: int,
                    payload: Path | None = None) -> None:
    """Create the nested-MBR p4 and optionally populate its FAT32 userstore."""
    inner_start = 16
    fat_sectors = sectors - inner_start

    # userstore clears the first cylinder before creating the nested MBR.
    # Clear the complete FAT metadata area as well so this function is safe
    # for an in-place repair of an existing, differently formatted p4.
    disk.seek(output_offset)
    disk.write(b"\0" * (inner_start * SECTOR_SIZE))

    inner_mbr = bytearray(SECTOR_SIZE)
    inner_mbr[446:462] = struct.pack(
        "<B3sB3sII",
        0x00,
        b"\x00\x01\x01",
        0x0B,
        b"\x03\xd0\xff",
        inner_start,
        fat_sectors,
    )
    inner_mbr[510:512] = b"\x55\xaa"
    disk.seek(output_offset)
    disk.write(inner_mbr)

    # /etc/upstart/userstore creates this with mkfs.vfat -F 32 -B 4 -s 16.
    # These are the production geometry values made by each stock firmware's
    # mkfs.vfat -F 32 -B 4 -s 16 invocation. The enlarged reserved area aligns
    # the data region; a generic 32-sector FAT header is not equivalent.
    sectors_per_cluster = 16
    fat_count = 2
    geometry = {
        2945024: (5322, 1435),
        6385664: (2134, 3115),
        6688768: (4002, 3263),
    }
    try:
        reserved, sectors_per_fat = geometry[sectors]
    except KeyError as error:
        raise ValueError("unknown Kindle userstore geometry") from error
    clusters = (fat_sectors - reserved - fat_count * sectors_per_fat) // sectors_per_cluster

    boot = bytearray(SECTOR_SIZE)
    boot[0:3] = b"\xeb\x58\x90"
    boot[3:11] = b"mkdosfs\0"
    struct.pack_into("<HBHBHHBHHHII", boot, 11,
                     SECTOR_SIZE, sectors_per_cluster, reserved, fat_count,
                     0, 0, 0xF8, 0, 32, 64, 0, fat_sectors)
    struct.pack_into("<IHHIHH", boot, 36,
                     sectors_per_fat, 0, 0, 2, 1, 6)
    boot[66] = 0x29
    struct.pack_into("<I", boot, 67, 0x61B4AEE5)
    boot[71:82] = b"Kindle     "
    boot[82:90] = b"FAT32   "
    boot[510:512] = b"\x55\xaa"

    fs_offset = output_offset + inner_start * SECTOR_SIZE
    data_start = reserved + fat_count * sectors_per_fat
    cluster_size = sectors_per_cluster * SECTOR_SIZE
    root = build_fat_tree(payload) if payload else FatNode("")

    next_cluster = 2
    short_index = 1
    short_names: dict[int, bytes] = {}
    for node in iter_fat_nodes(root):
        if node is root:
            entry_count = sum(
                len(lfn_entries(child.name, fat_short_name(short_index + index))) + 1
                for index, child in enumerate(node.children)
            )
        elif node.is_dir:
            entry_count = 2 + sum(
                len(lfn_entries(child.name, fat_short_name(short_index + index))) + 1
                for index, child in enumerate(node.children)
            )
        else:
            entry_count = 0

        if node.is_dir:
            count = max(1, math.ceil(entry_count * 32 / cluster_size))
        else:
            count = math.ceil(node.size / cluster_size)
        node.clusters = list(range(next_cluster, next_cluster + count))
        node.first_cluster = node.clusters[0] if node.clusters else 0
        next_cluster += count
        for child in node.children:
            short_names[id(child)] = fat_short_name(short_index)
            short_index += 1

    if next_cluster - 2 > clusters:
        raise SystemExit(f"userstore payload does not fit ({next_cluster - 2} clusters required)")

    fat = bytearray(sectors_per_fat * SECTOR_SIZE)
    struct.pack_into("<II", fat, 0, 0x0FFFFFF8, 0xFFFFFFFF)
    for node in iter_fat_nodes(root):
        for index, cluster in enumerate(node.clusters):
            following = (node.clusters[index + 1]
                         if index + 1 < len(node.clusters) else 0x0FFFFFFF)
            struct.pack_into("<I", fat, cluster * 4, following)

    fsinfo = bytearray(SECTOR_SIZE)
    struct.pack_into("<I", fsinfo, 0, 0x41615252)
    struct.pack_into("<I", fsinfo, 484, 0x61417272)
    struct.pack_into("<II", fsinfo, 488, clusters - (next_cluster - 2), next_cluster)
    struct.pack_into("<I", fsinfo, 508, 0xAA550000)

    disk.seek(fs_offset)
    disk.write(b"\0" * (data_start * SECTOR_SIZE))
    for sector, data in ((0, boot), (1, fsinfo), (6, boot), (7, fsinfo)):
        disk.seek(fs_offset + sector * SECTOR_SIZE)
        disk.write(data)
    for fat_index in range(fat_count):
        disk.seek(fs_offset + (reserved + fat_index * sectors_per_fat) * SECTOR_SIZE)
        disk.write(fat)

    def cluster_offset(cluster: int) -> int:
        return fs_offset + (data_start + (cluster - 2) * sectors_per_cluster) * SECTOR_SIZE

    def write_chain(node: FatNode, data: bytes) -> None:
        for index, cluster in enumerate(node.clusters):
            chunk = data[index * cluster_size:(index + 1) * cluster_size]
            disk.seek(cluster_offset(cluster))
            disk.write(chunk)
            if len(chunk) < cluster_size:
                disk.write(b"\0" * (cluster_size - len(chunk)))

    def write_directory(node: FatNode, parent: FatNode | None) -> None:
        entries: list[bytes] = []
        if parent is not None:
            entries.append(fat_dir_entry(b".          ", 0x10, node.first_cluster))
            entries.append(fat_dir_entry(
                b"..         ", 0x10,
                0 if parent is root else parent.first_cluster,
            ))
        for child in node.children:
            short_name = short_names[id(child)]
            entries.extend(lfn_entries(child.name, short_name))
            entries.append(fat_dir_entry(
                short_name, 0x10 if child.is_dir else 0x20,
                child.first_cluster, child.size,
            ))
        write_chain(node, b"".join(entries))
        for child in node.children:
            if child.is_dir:
                write_directory(child, node)
            elif child.clusters:
                with child.source.open("rb") as source:
                    write_chain(child, source.read())

    write_directory(root, None)


def lfn_checksum(short_name: bytes) -> int:
    checksum = 0
    for byte in short_name:
        checksum = ((checksum & 1) << 7) + (checksum >> 1) + byte
        checksum &= 0xFF
    return checksum


def lfn_entries(name: str, short_name: bytes) -> list[bytes]:
    """Return VFAT long-name entries in their on-disk order."""
    chars = list(name.encode("utf-16le"))
    code_units = [chars[i:i + 2] for i in range(0, len(chars), 2)]
    code_units.append([0, 0])
    while len(code_units) % 13:
        code_units.append([0xFF, 0xFF])

    checksum = lfn_checksum(short_name)
    entries = []
    count = len(code_units) // 13
    for ordinal in range(count, 0, -1):
        chunk = code_units[(ordinal - 1) * 13:ordinal * 13]
        entry = bytearray(32)
        entry[0] = ordinal | (0x40 if ordinal == count else 0)
        entry[11] = 0x0F
        entry[13] = checksum
        encoded = b"".join(bytes(unit) for unit in chunk)
        entry[1:11] = encoded[0:10]
        entry[14:26] = encoded[10:22]
        entry[28:32] = encoded[22:26]
        entries.append(bytes(entry))
    return entries


def fat_dir_entry(short_name: bytes, attributes: int, cluster: int,
                  size: int = 0) -> bytes:
    entry = bytearray(32)
    entry[0:11] = short_name
    entry[11] = attributes
    struct.pack_into("<H", entry, 20, cluster >> 16)
    struct.pack_into("<H", entry, 26, cluster & 0xFFFF)
    struct.pack_into("<I", entry, 28, size)
    return bytes(entry)


def write_waveform_store(disk, output_offset: int) -> None:
    """Create the hidden FAT32 store used by /usr/sbin/wfm_mount."""

    sector_size = 1024
    sectors_per_cluster = 16
    total_sectors = WAVEFORM_STORE_SIZE // sector_size
    reserved = 32
    fat_count = 2
    sectors_per_fat = 1
    data_start = reserved + fat_count * sectors_per_fat
    cluster_size = sector_size * sectors_per_cluster
    cluster_count = (total_sectors - data_start) // sectors_per_cluster

    boot = bytearray(sector_size)
    boot[0:3] = b"\xeb\x58\x90"
    boot[3:11] = b"mkdosfs\0"
    struct.pack_into("<HBHBHHBHHHII", boot, 11,
                     sector_size, sectors_per_cluster, reserved, fat_count,
                     0, 0, 0xF8, 0, 16, 0, WAVEFORM_STORE_OFFSET // sector_size,
                     total_sectors)
    struct.pack_into("<IHHIHH", boot, 36,
                     sectors_per_fat, 0, 0, 2, 1, 6)
    boot[64] = 0x80
    boot[66] = 0x29
    struct.pack_into("<I", boot, 67, 0x57464D31)
    boot[71:82] = b"WAVEFORM   "
    boot[82:90] = b"FAT32   "
    boot[510:512] = b"\x55\xaa"

    used_clusters = 2  # root directory and empty waveform_to_use directory
    fsinfo = bytearray(sector_size)
    struct.pack_into("<I", fsinfo, 0, 0x41615252)
    struct.pack_into("<I", fsinfo, 484, 0x61417272)
    struct.pack_into("<II", fsinfo, 488,
                     cluster_count - used_clusters, 4)
    struct.pack_into("<I", fsinfo, 508, 0xAA550000)

    fat = bytearray(sector_size)
    struct.pack_into("<III", fat, 0, 0x0FFFFFF8, 0xFFFFFFFF, 0x0FFFFFFF)
    struct.pack_into("<I", fat, 3 * 4, 0x0FFFFFFF)

    root = bytearray(cluster_size)
    directory_short = b"WAVEFO~1   "
    root_entries = lfn_entries("waveform_to_use", directory_short)
    root_entries.append(fat_dir_entry(directory_short, 0x10, 3))
    root[0:32 * len(root_entries)] = b"".join(root_entries)

    directory = bytearray(cluster_size)
    directory[0:32] = fat_dir_entry(b".          ", 0x10, 3)
    directory[32:64] = fat_dir_entry(b"..         ", 0x10, 2)

    disk.seek(output_offset)
    disk.write(b"\0" * WAVEFORM_STORE_SIZE)
    for sector, data in ((0, boot), (1, fsinfo), (6, boot), (7, fsinfo)):
        disk.seek(output_offset + sector * sector_size)
        disk.write(data)
    for fat_index in range(fat_count):
        disk.seek(output_offset + (reserved + fat_index * sectors_per_fat) * sector_size)
        disk.write(fat)
    disk.seek(output_offset + data_start * sector_size)
    disk.write(root)
    disk.write(directory)


def build(
    output: Path,
    kernel: Path,
    rootfs: Path | None,
    *,
    layout: str = "wario",
    diagnostics_kernel: Path | None = None,
    diagnostics: Path | None = None,
    local: Path | None = None,
    userstore: Path | None = None,
) -> None:
    """Build a sparse legacy i.MX6 Kindle eMMC user-area image."""
    try:
        partitions = PARTITION_LAYOUTS[layout]
    except KeyError as error:
        raise ValueError(f"unknown i.MX6 Kindle partition layout: {layout}") from error

    kernel_size = kernel.stat().st_size
    p1_offset = partitions[0][0] * SECTOR_SIZE
    if KERNEL_OFFSET + kernel_size > DIAGS_KERNEL_OFFSET:
        raise SystemExit("kernel overlaps the diagnostics-kernel slot")
    if (diagnostics_kernel and
            DIAGS_KERNEL_OFFSET + diagnostics_kernel.stat().st_size > p1_offset):
        raise SystemExit("diagnostics kernel overlaps the partition-1 boundary")

    if diagnostics and diagnostics.stat().st_size != 64 * 1024 * 1024:
        raise SystemExit("diagnostics image must be exactly 64 MiB")
    if local and local.stat().st_size != 64 * 1024 * 1024:
        raise SystemExit("local image must be exactly 64 MiB")
    if userstore and not userstore.is_dir():
        raise SystemExit("userstore must name a directory")

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w+b") as disk:
        kernel_slots = [(kernel, KERNEL_OFFSET)]
        if diagnostics_kernel:
            kernel_slots.append((diagnostics_kernel, DIAGS_KERNEL_OFFSET))
        for kernel_path, kernel_offset in kernel_slots:
            disk.seek(USER_AREA_OFFSET + kernel_offset)
            with kernel_path.open("rb") as kernel:
                shutil.copyfileobj(kernel, disk)

        rootfs_size = 0
        if rootfs:
            rootfs_offset = USER_AREA_OFFSET + p1_offset
            disk.seek(rootfs_offset)
            with rootfs.open("rb") as rootfs_file:
                rootfs_size = copy_stream(rootfs_file, disk)
            if rootfs_size > partitions[0][1] * SECTOR_SIZE:
                raise SystemExit("rootfs exceeds the selected layout's p1")

        if diagnostics:
            disk.seek(USER_AREA_OFFSET + partitions[1][0] * SECTOR_SIZE)
            with diagnostics.open("rb") as diags:
                copy_stream(diags, disk)

        write_waveform_store(disk, USER_AREA_OFFSET + WAVEFORM_STORE_OFFSET)

        write_local_partition(
            disk, USER_AREA_OFFSET + partitions[2][0] * SECTOR_SIZE,
            local,
        )
        write_userstore(
            disk,
            USER_AREA_OFFSET + partitions[3][0] * SECTOR_SIZE,
            partitions[3][1],
            userstore,
        )

        user_size = (4194304 if layout == "duet" else USER_AREA_SECTORS) * SECTOR_SIZE
        disk_size = USER_AREA_OFFSET + user_size
        disk.truncate(disk_size)

        if rootfs:
            disk.seek(rootfs_offset + EXT_MAGIC_OFFSET)
            if disk.read(2) != b"\x53\xef":
                raise SystemExit("rootfs is not an ext filesystem")
        disk.seek(USER_AREA_OFFSET)
        disk.write(make_mbr(partitions))
