"""Carve and rebuild supported Kobo SD cards without copying their userstore."""
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
class Board:
    model: str
    description: str
    pcb: int
    ram_base: int
    bootloader_name: str
    rom_plugin: bool


BOARDS = {
    "kobo-clara-hd": Board("kobo-clara-hd", "Clara HD", 74, 0x80000000,
                           "u-boot.imx", False),
    "kobo-aura-hd": Board("kobo-aura-hd", "Aura HD", 28, 0x70000000,
                          "u-boot.bin", True),
}


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
    """Validate two Linux partitions followed by a FAT32 userstore."""
    if len(mbr) != SECTOR_SIZE or mbr[510:512] != b"\x55\xaa":
        raise ValueError("Kobo SD image requires a valid 512-byte MBR")
    partitions = []
    previous_end = 1
    for index, types in enumerate(({0x83}, {0x83}, {0x0b, 0x0c})):
        entry = mbr[446 + index * 16:462 + index * 16]
        start, sectors = struct.unpack_from("<II", entry, 8)
        partition = Partition(start, sectors, entry[4])
        if entry[0] not in (0, 0x80) or partition.type not in types:
            raise ValueError(f"Unexpected Kobo partition {index + 1} type or status")
        if not sectors or start < previous_end or partition.end > 2**32:
            raise ValueError(f"Invalid or overlapping Kobo partition {index + 1}")
        partitions.append(partition)
        previous_end = partition.end
    if any(mbr[494:510]):
        raise ValueError("Kobo SD image requires an unused fourth MBR partition")
    return tuple(partitions)


def identify_board(hwconfig: bytes) -> Board:
    if (len(hwconfig) != SECTOR_SIZE or hwconfig[:10] != b"HW CONFIG " or
            hwconfig[15] < 1):
        raise ValueError("Missing Netronix hardware configuration")
    pcb = hwconfig[16]
    for board in BOARDS.values():
        if board.pcb == pcb:
            return board
    raise ValueError(f"Unsupported Kobo hardware configuration: PCB {pcb}")


def extract_uboot(region: bytes, board: Board) -> bytes:
    """Follow the ROM's IVT/boot-data chain, including i.MX50 plug-in images."""
    limit = min(HWCFG_OFFSET, len(region))

    def header(offset: int) -> tuple[int, int, int, int, int, int]:
        if (offset < 0 or offset + 0x20 > limit or
                region[offset:offset + 4] != b"\xd1\x00\x20\x40"):
            raise ValueError(f"Missing i.MX U-Boot IVT at byte {offset:#x}")
        entry = struct.unpack_from("<I", region, offset + 4)[0]
        boot_data, address = struct.unpack_from("<II", region, offset + 0x10)
        data_offset = offset + boot_data - address
        if not offset + 0x20 <= data_offset <= limit - 12:
            raise ValueError("U-Boot boot-data pointer lies outside its image")
        start, size, plugin = struct.unpack_from("<III", region, data_offset)
        return entry, address, start, size, plugin, data_offset

    ivt = 0x400
    entry, address, start, size, plugin, data_offset = header(ivt)
    if plugin != int(board.rom_plugin):
        raise ValueError(f"Unexpected {board.description} U-Boot ROM plug-in flag")
    if board.rom_plugin:
        # The i.MX50 DDR plug-in's boot data is immediately followed by the
        # SDRAM U-Boot IVT. Retain the binary prefix expected by its loader.
        ivt = data_offset + 12
        entry, address, start, size, plugin, data_offset = header(ivt)
        begin = ivt - (address - start)
        end = begin + size
        load_address = start
    else:
        # i.MX6SLL uses the IVT-start .imx artifact passed to its board loader.
        begin = ivt
        end = ivt + size - (address - start)
        load_address = address
    if (plugin or address < start or begin < 0 or begin > ivt or
            end < max(ivt + 0x20, data_offset + 12) or end > limit or
            not board.ram_base <= load_address < load_address + end - begin <= board.ram_base + 512 * 1024**2 or
            not load_address <= entry < load_address + end - begin):
        raise ValueError(f"Invalid {board.description} U-Boot extent or entry point")
    return region[begin:end]


def prepare_root(source: Path, output: Path, *, size: int, board: Board,
                 sideloaded: bool) -> None:
    rootfs.copy_source(source, output, maximum_size=size)
    result = subprocess.run([str(rootfs.find_debugfs().with_name("e2fsck")),
                             "-p", str(output)], check=False)
    if result.returncode not in (0, 1):
        raise ValueError(f"Could not recover the {board.description} root filesystem")
    rootfs.run(output, "rm /etc/udev.tgz", writable=True)
    if sideloaded:
        rootfs.install_overrides(image=output, group="elipsa2e", replacements={
            "/etc/init.d/eink-sideloaded": ("etc/init.d/eink-sideloaded", "0100755"),
        })

        def startup(contents: str) -> str:
            marker = "/etc/init.d/eink-sideloaded\n"
            if marker in contents:
                return contents
            needle = "/usr/local/Kobo/hindenburg &"
            if contents.count(needle) != 1:
                raise ValueError(f"Unrecognized {board.description} Hindenburg startup")
            return contents.replace(needle, marker + needle)

        rootfs.transform_file(output, "/etc/init.d/rcS", "0100755", startup)
    prepare_network(output)


def build(output: Path, artifacts: dict[str, Path], *, model: str,
          sideloaded: bool = False) -> None:
    if sideloaded and model != "kobo-aura-hd":
        raise ValueError(f"Sideloaded mode is not supported by {model}")
    region = artifacts["boot_region"].read_bytes()
    root, recovery, user = parse_layout(region[:SECTOR_SIZE])
    if len(region) != root.start * SECTOR_SIZE:
        raise ValueError("Kobo SD image requires the complete region before partition 1")
    board = identify_board(region[HWCFG_OFFSET:HWCFG_OFFSET + SECTOR_SIZE])
    if board.model != model:
        raise ValueError(f"Expected {model} hardware configuration, found {board.model}")
    for role, partition in (("rootfs", root), ("recoveryfs", recovery)):
        source = artifacts[role]
        if source.stat().st_size != partition.sectors * SECTOR_SIZE:
            raise ValueError(f"{source.name} must match its complete {board.description} partition")
        with source.open("rb") as stream:
            stream.seek(rootfs.EXT_MAGIC_OFFSET)
            if stream.read(2) != b"\x53\xef":
                raise ValueError(f"{source.name} is not an ext filesystem")
    prepared = output.with_name("prepared-rootfs.img")
    prepare_root(artifacts["rootfs"], prepared, size=root.sectors * SECTOR_SIZE,
                 board=board, sideloaded=sideloaded)
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
