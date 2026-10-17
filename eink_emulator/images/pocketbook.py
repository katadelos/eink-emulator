"""Import PocketBook i.MX updates and assemble their internal storage."""

from __future__ import annotations

import gzip
import io
import shutil
import struct
import subprocess
import tarfile
import tempfile
import zipfile
import zlib
from dataclasses import dataclass
from pathlib import Path

from . import rootfs
from .common import atomic_output
from .forma import write_userstore

MIB = 1024**2
SECTOR_SIZE = 512
DISK_SIZE = 2032 * MIB
UBOOT_OFFSET = 0x400
HEADER_SIZE = 0x400
IMPORT_FILES = {
    ord("u"): ("bootloader", "u-boot.bin"),
    ord("k"): ("kernel", "uImage"),
    ord("r"): ("rootfs", "rootfs.img"),
    ord("e"): ("applications", "applications.img"),
}
LOGO_FILES = {
    "logo_header": ("logo-header.bin", 1025 * SECTOR_SIZE),
    "boot_logo": ("bootlogo.bmp", 1026 * SECTOR_SIZE),
    "low_battery_logo": ("battery-low.bmp", 3074 * SECTOR_SIZE),
}


@dataclass(frozen=True)
class Layout:
    disk_size: int
    env_offset: int
    kernel_offset: int
    kernel_size: int
    vcom_offset: int
    vcom: bytes
    waveform_offset: int
    user_device: str
    partitions: tuple[tuple[int, int, int], ...]
    logo_offsets: dict[str, int]
    logo_limit: int


# The EP7/EP8 loader misdecodes sector-addressed MMC capacity and the exact
# 2 GiB CSD boundary. A 2032 MiB byte-addressed user area avoids both bugs.
# Filesystem updates omit a physical card's MBR, so retain raw boot offsets
# and partition numbers while allocating space for the supplied images.
MX50_LAYOUT = Layout(
    disk_size=DISK_SIZE,
    env_offset=320 * 1024,
    kernel_offset=0x280400,
    kernel_size=0x300000,
    vcom_offset=0x580400,
    vcom=b"-1250000",
    waveform_offset=0x580600,
    user_device="/dev/mmcblk1p4",
    partitions=(
        (16 * MIB, 16 * MIB, 0x83),
        (32 * MIB, 256 * MIB, 0x83),
        (288 * MIB, 16 * MIB, 0x83),
        (304 * MIB, DISK_SIZE - 304 * MIB, 0x0C),
    ),
    logo_offsets={role: offset for role, (_, offset) in LOGO_FILES.items()},
    logo_limit=MIB,
)
@dataclass(frozen=True)
class Board:
    update_model: bytes
    layout: Layout
    logo_sources: dict[int, dict[str, str]]
    logo_dimensions: tuple[int, int]
    logo_depth: int
    secure_pbpk_mode: str
    factory_state: int
    raw_settings: tuple[tuple[int, bytes], ...]
    factory_tar_excludes: tuple[str, ...]
    factory_directories: tuple[str, ...]
    waveform_file: str


BOARDS = {
    "pocketbook-613": Board(
        update_model=b"PocketBook613",
        layout=MX50_LAYOUT,
        logo_sources={6: {
            "logo_header": "misc/logo_header.bin",
            "boot_logo": "misc/bootlogo_613_rot270.bmp",
            "low_battery_logo": "misc/battery_low_rot270.bmp",
        }},
        logo_dimensions=(800, 600),
        logo_depth=8,
        secure_pbpk_mode="040755",
        factory_state=0x19D85675,
        raw_settings=(),
        factory_tar_excludes=(),
        factory_directories=(),
        waveform_file="",
    ),
    "pocketbook-622": Board(
        update_model=b"PocketBook622",
        layout=MX50_LAYOUT,
        logo_sources={
            5: {"low_battery_logo": "misc/622_battery_low_rot90.bmp"},
            8: {
                "logo_header": "misc/logo_header.bin",
                "boot_logo": "misc/bootlogo_622_rot90.bmp",
            },
        },
        logo_dimensions=(800, 600),
        logo_depth=8,
        secure_pbpk_mode="040770",
        factory_state=0x3AC10E17,
        raw_settings=(),
        factory_tar_excludes=(),
        factory_directories=(),
        waveform_file="",
    ),
}


def validate_firmware(artifacts: dict[str, Path], board: Board) -> None:
    """Check the stock i.MX loader, uImage and matching ext filesystems."""
    layout = board.layout
    with artifacts["bootloader"].open("rb") as stream:
        if stream.read(4) != b"\xd1\x00\x20\x40":
            raise ValueError("PocketBook U-Boot is missing its i.MX IVT")
    if artifacts["bootloader"].stat().st_size > layout.env_offset - UBOOT_OFFSET:
        raise ValueError("PocketBook U-Boot overlaps the environment region")
    with artifacts["kernel"].open("rb") as stream:
        header = stream.read(64)
    if len(header) != 64 or header[:4] != b"\x27\x05\x19\x56":
        raise ValueError("PocketBook kernel must be a legacy uImage")
    if struct.unpack_from(">I", header, 12)[0] + 64 != artifacts["kernel"].stat().st_size:
        raise ValueError("PocketBook kernel uImage is truncated or has trailing data")
    if artifacts["kernel"].stat().st_size > layout.kernel_size:
        raise ValueError("PocketBook kernel exceeds its raw boot region")
    for index, role in enumerate(("rootfs", "applications")):
        image = artifacts[role]
        if image.stat().st_size > layout.partitions[index][1]:
            raise ValueError(f"PocketBook {role} exceeds its partition")
        with image.open("rb") as stream:
            stream.seek(1024)
            superblock = stream.read(1024)
        if len(superblock) != 1024 or superblock[56:58] != b"\x53\xef":
            raise ValueError(f"PocketBook {role} is not an ext filesystem")
        blocks = struct.unpack_from("<I", superblock, 4)[0]
        block_shift = struct.unpack_from("<I", superblock, 24)[0]
        if (not blocks or block_shift > 2 or
                blocks * (1024 << block_shift) > image.stat().st_size):
            raise ValueError(f"PocketBook {role} filesystem is truncated")
    for role in layout.logo_offsets.keys() & artifacts.keys():
        validate_logo(role, artifacts[role].read_bytes(), board)


def validate_logo(role: str, data: bytes, board: Board) -> None:
    if role == "logo_header":
        if len(data) != SECTOR_SIZE:
            raise ValueError("PocketBook logo header must occupy one sector")
        return
    if len(data) < 54 or data[:2] != b"BM":
        raise ValueError(f"PocketBook {role} must be a BMP image")
    size, = struct.unpack_from("<I", data, 2)
    width, height, planes, depth, compression = struct.unpack_from("<iiHHI", data, 18)
    if (size != len(data) or len(data) > board.layout.logo_limit or
            (width, height, planes, depth, compression) !=
            (*board.logo_dimensions, 1, board.logo_depth, 0)):
        expected_width, expected_height = board.logo_dimensions
        raise ValueError(f"PocketBook {role} must be a complete "
                         f"{expected_width}x{expected_height} {board.logo_depth}-bit BMP")


def extract_logos(
    script: bytes, destination: Path, members: dict[str, str],
    board: Board,
) -> dict[str, Path]:
    """Read named original logo assets without executing the update script."""
    _, marker, payload = script.partition(b"\n__ARCHIVE_BELOW__\n")
    if not script.startswith(b"#!/bin/sh\n") or not marker:
        raise ValueError("PocketBook logo stage has no embedded archive")
    images: dict[str, bytes] = {}
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as archive:
        for role, member_name in members.items():
            member = archive.getmember(member_name)
            if not member.isfile() or member.size > board.layout.logo_limit:
                raise ValueError(f"PocketBook logo archive has an invalid {member_name}")
            source = archive.extractfile(member)
            if source is None:
                raise ValueError(f"PocketBook logo archive is missing {member_name}")
            with source:
                data = source.read()
            validate_logo(role, data, board)
            images[role] = data
    installed = {}
    for role, data in images.items():
        path = destination / LOGO_FILES[role][0]
        path.write_bytes(data)
        installed[role] = path
    return installed


def import_update(package: Path, destination: Path, *, model: str) -> dict[str, Path]:
    """Install original boot/filesystem payloads and logos for the chosen board."""
    board = BOARDS[model]
    if not package.is_file():
        raise SystemExit(f"firmware package does not exist: {package}")
    if destination.exists():
        raise SystemExit(f"firmware destination already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=f".{destination.name}-import-", dir=destination.parent,
    ) as temporary:
        workspace = Path(temporary)
        container = package
        if zipfile.is_zipfile(package):
            container = workspace / "SWUPDATE.BIN"
            with zipfile.ZipFile(package) as archive:
                members = [member for member in archive.infolist()
                           if member.filename.upper() == "SWUPDATE.BIN" and not member.is_dir()]
                if len(members) != 1:
                    raise ValueError("PocketBook update ZIP must contain one SWUPDATE.BIN")
                with archive.open(members[0]) as source, container.open("wb") as target:
                    shutil.copyfileobj(source, target)
        with container.open("rb") as source:
            compressed = source.read(2) == b"\x1f\x8b"
        if compressed:
            expanded = workspace / "update.bin"
            with gzip.open(container, "rb") as source, expanded.open("wb") as target:
                shutil.copyfileobj(source, target)
            container = expanded

        prepared = workspace / "prepared"
        prepared.mkdir()
        installed: dict[str, Path] = {}
        logo_scripts = {}
        extents = []
        container_size = container.stat().st_size
        with container.open("rb") as source:
            header = source.read(HEADER_SIZE)
            if len(header) != HEADER_SIZE or header[:16] != b"PocketBookUpdate":
                raise ValueError("PocketBook update has an invalid header")
            if header[16:36].split(b"\0", 1)[0] != board.update_model:
                raise ValueError(f"PocketBook update is not for {model}")
            for position in range(0x100, HEADER_SIZE, 16):
                tag, _, relative, size = struct.unpack_from("<IIII", header, position)
                if not tag:
                    break
                offset = HEADER_SIZE + relative
                if not size or offset > container_size or size > container_size - offset:
                    raise ValueError("PocketBook update section lies outside its container")
                extents.append((offset, offset + size))
                stage = (position - 0x100) // 16
                if stage in board.logo_sources and tag == ord("@"):
                    source.seek(offset)
                    logo_scripts[stage] = source.read(size)
                if tag not in IMPORT_FILES:
                    continue
                role, name = IMPORT_FILES[tag]
                if role in installed:
                    raise ValueError(f"PocketBook update repeats its {role} payload")
                source.seek(offset)
                with (prepared / name).open("wb") as target:
                    remaining = size
                    while remaining:
                        data = source.read(min(remaining, 8 * MIB))
                        if not data:
                            raise ValueError(f"PocketBook update has a truncated {role} payload")
                        target.write(data)
                        remaining -= len(data)
                installed[role] = prepared / name
            else:
                raise ValueError("PocketBook update section table has no terminator")
        extents.sort()
        if any(left[1] > right[0] for left, right in zip(extents, extents[1:])):
            raise ValueError("PocketBook update contains overlapping sections")
        missing = {role for role, _ in IMPORT_FILES.values()} - installed.keys()
        if missing:
            raise ValueError(f"PocketBook update is missing: {', '.join(sorted(missing))}")
        for stage, script in logo_scripts.items():
            installed.update(extract_logos(
                script, prepared, board.logo_sources[stage], board,
            ))
        validate_firmware(installed, board)
        prepared.replace(destination)
    return {role: destination / path.name for role, path in installed.items()}


def prepare_root(source: Path, output: Path, board: Board) -> None:
    rootfs.copy_source(source, output, maximum_size=board.layout.partitions[0][1])
    exclusions = "".join(f" --exclude={name}" for name in board.factory_tar_excludes)
    directories = " ".join(f"/mnt/ext1/{name}" for name in board.factory_directories)
    make_directories = f"    mkdir -p {directories} || exit 1\n" if directories else ""

    def seed_userstore(contents: str) -> str:
        marker = "\n#RUNNING AP\n"
        if contents.count(marker) != 1:
            raise ValueError("PocketBook rootfs has an unexpected startup script")
        return contents.replace(marker, (
            "\n# Install the bundled factory content on a fresh user partition.\n"
            f"mount -t vfat -o rw,umask=0000,iocharset=utf8 {board.layout.user_device} /mnt/ext1 || exit 1\n"
            "if [ ! -f /mnt/ext1/system/.qemu-factory-content ]; then\n"
            f"    tar xzf /ebrmain/fsimage.tar.gz{exclusions} -C /mnt/ext1 || exit 1\n"
            + make_directories
            + "    sync\n"
            "    touch /mnt/ext1/system/.qemu-factory-content || exit 1\n"
            "    sync\n"
            "fi\n"
            + marker
        ))

    rootfs.transform_file(output, "/etc/init.d/rcS", "0100755", seed_userstore)


def build_waveform() -> bytes:
    """Create a neutral V110 waveform for QEMU's directly rendered EPDC."""
    # This is a complete emulator fixture, not physical panel calibration.
    # Four modes share one temperature range and one neutral transition frame.
    waveform = bytearray(0x5E)
    fields = {
        0x08: b"QEMU", 0x0C: bytes((1, 3)), 0x10: bytes((1, 1)),
        0x13: bytes((0x15, 0x3C, 0x33)), 0x17: b"\x50", 0x1C: b"\x33",
        0x20: bytes((0x3A, 0, 0, 1)), 0x25: bytes((3, 1)),
        0x28: bytes((0xFF, 0xFC)), 0x30: bytes((0, 35, 35)),
        0x33: bytes((5, 0, 0, 0, 0, 0, 5)),
        0x5A: bytes((0, 63, 0xFF, 62)),
    }
    for offset, value in fields.items():
        waveform[offset:offset + len(value)] = value
    struct.pack_into("<I", waveform, 4, len(waveform))
    for mode in range(4):
        # 24-bit pointers followed by their additive checksum.
        waveform[0x3A + 4 * mode] = waveform[0x3D + 4 * mode] = 0x4A + 4 * mode
        waveform[0x4A + 4 * mode] = waveform[0x4D + 4 * mode] = 0x5A
    waveform[0x1F] = sum(waveform[:0x1F]) & 0xFF
    waveform[0x2F] = sum(waveform[0x20:0x2F]) & 0xFF
    struct.pack_into("<I", waveform, 0, zlib.crc32(waveform))
    return bytes(waveform)


def build(output: Path, artifacts: dict[str, Path], *, model: str) -> None:
    """Keep the stock bootloader/kernel/filesystems and create writable storage."""
    board = BOARDS[model]
    layout = board.layout
    partitions = layout.partitions
    validate_firmware(artifacts, board)
    prepared = output.with_name("prepared-rootfs.img")
    prepare_root(artifacts["rootfs"], prepared, board)
    secure = output.with_name("secure.img")
    with secure.open("wb") as stream:
        stream.truncate(partitions[2][1])
    subprocess.run([
        str(rootfs.find_debugfs().with_name("mke2fs")), "-q", "-F", "-t", "ext3",
        "-O", "none,has_journal", "-L", "secure", str(secure),
    ], check=True)
    # Match the original update's S49-fix-secure-chmod.sh for sreader (102).
    secure_commands = ["mkdir /pbpk", "mkdir /runonce"]
    for directory, mode in (("/", "040770"), ("/pbpk", board.secure_pbpk_mode),
                            ("/runonce", "040755")):
        secure_commands.extend([
            f"set_inode_field {directory} uid 102",
            f"set_inode_field {directory} gid 102",
            f"set_inode_field {directory} mode {mode}",
        ])
    # Stock monitors require identity-dependent callback state omitted by OTA
    # updates. PB613/PB623 use an empty IOC serial plus QEMU's MMC CID 0xdeadbeef;
    # PB512/PB611/PB622 use the modeled 20 zero serial, without the MMC term.
    # PB650/PB801 use the provisioned 20 ASCII zero serial and the same MMC CID.
    with tempfile.NamedTemporaryFile(prefix=f"{model}-factory-state-") as state:
        state.write(struct.pack("<I", board.factory_state))
        state.flush()
        secure_commands.extend([
            f'write "{state.name}" /.freezestatus',
            "set_inode_field /.freezestatus uid 102",
            "set_inode_field /.freezestatus gid 102",
            "set_inode_field /.freezestatus mode 0100660",
        ])
        rootfs.run_many(secure, secure_commands, writable=True)

    mbr = bytearray(SECTOR_SIZE)
    for index, (offset, size, kind) in enumerate(partitions):
        struct.pack_into("<B3sB3sII", mbr, 446 + index * 16,
                         0, b"\xfe\xff\xff", kind, b"\xfe\xff\xff",
                         offset // SECTOR_SIZE, size // SECTOR_SIZE)
    mbr[510:512] = b"\x55\xaa"
    with atomic_output(output) as temporary, temporary.open("w+b") as disk:
        disk.truncate(layout.disk_size)
        disk.write(mbr)
        for source, offset in (
            (artifacts["bootloader"], UBOOT_OFFSET),
            (artifacts["kernel"], layout.kernel_offset),
            (prepared, partitions[0][0]),
            (artifacts["applications"], partitions[1][0]),
            (secure, partitions[2][0]),
        ):
            disk.seek(offset)
            with source.open("rb") as stream:
                shutil.copyfileobj(stream, disk)
        if layout.vcom:
            disk.seek(layout.vcom_offset)
            disk.write(layout.vcom)
        for offset, data in board.raw_settings:
            disk.seek(offset)
            disk.write(data)
        for role, offset in layout.logo_offsets.items():
            if role in artifacts:
                disk.seek(offset)
                disk.write(artifacts[role].read_bytes())
        disk.seek(layout.waveform_offset)
        disk.write(build_waveform())
        write_userstore(disk, start=partitions[3][0] // SECTOR_SIZE,
                        end=layout.disk_size // SECTOR_SIZE, label=b"POCKETBOOK ")
