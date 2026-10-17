"""PocketBook B288 updates and board-specific eMMC images."""

from __future__ import annotations

import gzip
import shutil
import struct
import subprocess
import tempfile
import zipfile
import zlib
from dataclasses import dataclass
from pathlib import Path

from . import rootfs
from .common import atomic_output
from .forma import write_userstore
from .pocketbook import build_waveform as neutral_waveform_header

MIB = 1024**2
DISK_SIZE = 2 * 1024**3
LOGICAL_OFFSET = 20 * MIB
# Sunxi's table orders boot first and user storage last. DOS numbering is
# fixed by the vendor kernel, init scripts and /usr/dev.tar.
PARTITIONS = (
    ("boot", 2, 36 * MIB, 24 * MIB, 0x06),
    ("env", 5, 61 * MIB, 1 * MIB, 0x83),
    ("pbenv", 6, 65 * MIB, 15 * MIB, 0x83),
    ("rootfs", 7, 81 * MIB, 47 * MIB, 0x83),
    ("ebrmain", 8, 129 * MIB, 383 * MIB, 0x83),
    ("secure", 9, 513 * MIB, 15 * MIB, 0x83),
    ("UDISK", 1, 640 * MIB, DISK_SIZE - 640 * MIB, 0x0c),
)
IMPORT_FILES = {
    ord("u"): ("bootloader", "u-boot.img"),
    ord("k"): ("kernel", "uImage"),
    ord("c"): ("recoveryfs", "updatefs"),
    ord("r"): ("rootfs", "rootfs.img"),
    ord("e"): ("applications", "applications.img"),
}


@dataclass(frozen=True)
class Board:
    update_model: bytes
    platform_index: int
    touch_module: str
    factory_state: int
    copy_adobe_fonts: bool
    factory_directories: tuple[str, ...]
    disable_suspend: bool


BOARDS = {
    # Index 52 selects the original 628's XCD touch ID 22, not its FT6336 revision.
    "pocketbook-628": Board(b"PocketBook628", 52, "ektf2k_5B.ko", 0xa6c12675,
                           True, ("Photo", "Downloads"), True),
    "pocketbook-632": Board(b"PocketBook632", 34, "", 0x19d85675, False, (), False),
    "pocketbook-740": Board(b"PocketBook740", 31, "cyttsp5.ko", 0x19d85675, False, (), False),
}


@dataclass(frozen=True)
class IOCPatch:
    release: str
    block_offset: int
    block_size: int
    original: bytes
    replacement: bytes


IOC_PATCHES = {
    "pocketbook-628": IOCPatch("6.5.2890", 157436504, 127961,
                              bytes.fromhex("6f74ced5"), bytes.fromhex("6c74ced5")),
}


def validate_firmware(artifacts: dict[str, Path]) -> None:
    with artifacts["bootloader"].open("rb") as stream:
        head = stream.read(64)
    if (len(head) != 64 or head[:13] != b"sunxi-package" or
            struct.unpack_from("<I", head, 16)[0] != 0x89119800 or
            struct.unpack_from("<I", head, 36)[0] != artifacts["bootloader"].stat().st_size):
        raise ValueError("PocketBook B288 requires the complete vendor Sunxi boot package")
    with artifacts["kernel"].open("rb") as stream:
        head = stream.read(64)
    if (len(head) != 64 or head[:4] != b"\x27\x05\x19\x56" or
            struct.unpack_from(">I", head, 12)[0] + 64 != artifacts["kernel"].stat().st_size):
        raise ValueError("PocketBook B288 kernel must be a complete vendor uImage")
    for role, limit in (("rootfs", PARTITIONS[3][3]), ("applications", PARTITIONS[4][3])):
        image = artifacts[role]
        with image.open("rb") as stream:
            stream.seek(1024)
            sb = stream.read(1024)
        if (len(sb) != 1024 or sb[56:58] != b"\x53\xef" or
                image.stat().st_size > limit):
            raise ValueError(f"PocketBook B288 {role} must be an ext filesystem that fits its partition")
        blocks, = struct.unpack_from("<I", sb, 4)
        shift, = struct.unpack_from("<I", sb, 24)
        if not blocks or shift > 2 or blocks * (1024 << shift) > image.stat().st_size:
            raise ValueError(f"PocketBook B288 {role} filesystem is truncated")


def import_update(package: Path, destination: Path, *, model: str) -> dict[str, Path]:
    board = BOARDS[model]
    if not package.is_file():
        raise SystemExit(f"firmware package does not exist: {package}")
    if destination.exists():
        raise SystemExit(f"firmware destination already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f".{model}-import-", dir=destination.parent) as temporary:
        work = Path(temporary)
        container = package
        if zipfile.is_zipfile(container):
            container = work / "SWUPDATE.BIN"
            with zipfile.ZipFile(package) as archive:
                members = [n for n in archive.namelist() if Path(n).name == "SWUPDATE.BIN"]
                if len(members) != 1:
                    raise ValueError("PocketBook ZIP must contain one SWUPDATE.BIN")
                with archive.open(members[0]) as source, container.open("wb") as target:
                    shutil.copyfileobj(source, target)
        with container.open("rb") as stream:
            compressed = stream.read(2) == b"\x1f\x8b"
        if compressed:
            unpacked = work / "update.bin"
            with gzip.open(container, "rb") as source, unpacked.open("wb") as target:
                shutil.copyfileobj(source, target)
            container = unpacked
        prepared = work / "prepared"
        prepared.mkdir()
        installed = {}
        extents = []
        with container.open("rb") as source:
            header = source.read(1024)
            if (len(header) != 1024 or header[:16] != b"PocketBookUpdate" or
                    header[16:36].split(b"\0", 1)[0] != board.update_model):
                raise ValueError(f"PocketBook update does not identify {model}")
            for position in range(0x100, 0x400, 16):
                tag, _, offset, size = struct.unpack_from("<4I", header, position)
                if not tag:
                    break
                offset += 1024
                if not size or offset + size > container.stat().st_size:
                    raise ValueError("PocketBook update section is truncated")
                extents.append((offset, offset + size))
                if tag not in IMPORT_FILES:
                    continue
                role, name = IMPORT_FILES[tag]
                if role in installed:
                    raise ValueError(f"PocketBook update repeats {role}")
                source.seek(offset)
                payload = source.read(size)
                if payload[:2] == b"\x1f\x8b":
                    payload = gzip.decompress(payload)
                installed[role] = prepared / name
                installed[role].write_bytes(payload)
            else:
                raise ValueError("PocketBook section table has no terminator")
        extents.sort()
        if any(a[1] > b[0] for a, b in zip(extents, extents[1:])):
            raise ValueError("PocketBook update contains overlapping sections")
        if set(installed) != {role for role, _ in IMPORT_FILES.values()}:
            raise ValueError("PocketBook update is missing required boot or filesystem payloads")
        validate_firmware(installed)
        prepared.replace(destination)
    return {role: destination / path.name for role, path in installed.items()}


def write_bootfs(disk, files: dict[bytes, bytes]) -> None:
    """Write the vendor's 24 MiB FAT16 boot volume, using 8.3 file names."""
    start, size = PARTITIONS[0][2:4]
    sectors, spc, fat_sectors, root_entries = size // 512, 4, 48, 512
    boot = bytearray(512)
    boot[:11] = b"\xeb\x3c\x90MSDOS5.0"
    struct.pack_into("<HBHBHHBHHHII", boot, 11, 512, spc, 1, 2, root_entries,
                     sectors, 0xf8, fat_sectors, 63, 255, start // 512, 0)
    boot[36:39] = b"\x80\0\x29"
    struct.pack_into("<I", boot, 39, 0x50423734)
    boot[43:54] = b"BOOT       "
    boot[54:62] = b"FAT16   "
    boot[510:] = b"\x55\xaa"
    disk.seek(start)
    disk.write(boot)
    fat = bytearray(fat_sectors * 512)
    struct.pack_into("<HH", fat, 0, 0xfff8, 0xffff)
    directory = bytearray(root_entries * 32)
    data_offset = start + (1 + 2 * fat_sectors) * 512 + len(directory)
    cluster = 2
    for index, (name, data) in enumerate(files.items()):
        if len(name) != 11 or index >= root_entries:
            raise ValueError("Invalid boot volume file name")
        count = (len(data) + spc * 512 - 1) // (spc * 512)
        if data_offset + (cluster - 2 + count) * spc * 512 > start + size:
            raise ValueError("PocketBook B288 boot files exceed the FAT volume")
        for c in range(cluster, cluster + count):
            struct.pack_into("<H", fat, c * 2, c + 1 if c + 1 < cluster + count else 0xffff)
        entry = index * 32
        directory[entry:entry + 11] = name
        directory[entry + 11] = 0x20
        struct.pack_into("<HI", directory, entry + 26, cluster, len(data))
        disk.seek(data_offset + (cluster - 2) * spc * 512)
        disk.write(data)
        cluster += count
    for copy in range(2):
        disk.seek(start + (1 + copy * fat_sectors) * 512)
        disk.write(fat)
    disk.seek(start + (1 + 2 * fat_sectors) * 512)
    disk.write(directory)


def partition_entry(kind: int, start: int, size: int) -> bytes:
    return struct.pack("<B3sB3sII", 0, b"\xfe\xff\xff", kind,
                       b"\xfe\xff\xff", start // 512, size // 512)


def write_partition_tables(disk) -> None:
    extended = 60 * MIB
    end = 528 * MIB
    mbr = bytearray(512)
    for index in (0, 1):
        _, _, start, size, kind = PARTITIONS[-1 if index == 0 else 0]
        mbr[446 + index * 16:462 + index * 16] = partition_entry(kind, start, size)
    mbr[478:494] = partition_entry(0x0f, extended, end - extended)
    mbr[510:] = b"\x55\xaa"
    disk.seek(0)
    disk.write(mbr)
    logical = PARTITIONS[1:-1]
    for i, (_, _, start, size, kind) in enumerate(logical):
        ebr_start = start - MIB
        ebr = bytearray(512)
        ebr[446:462] = partition_entry(kind, MIB, size)
        if i + 1 < len(logical):
            following = logical[i + 1][2] - MIB
            ebr[462:478] = partition_entry(0x0f, following - extended, end - following)
        ebr[510:] = b"\x55\xaa"
        disk.seek(ebr_start)
        disk.write(ebr)
    table = bytearray(16 * 1024)
    struct.pack_into("<I8s4I", table, 4, 0x100, b"softw411", 4, 0, len(PARTITIONS), 0)
    for i, (name, _, start, size, _) in enumerate(PARTITIONS):
        struct.pack_into("<4I16s16s", table, 32 + i * 128, 0,
                         (start - LOGICAL_OFFSET) // 512, 0, size // 512,
                         b"DISK", name.encode())
    for i in range(4):
        struct.pack_into("<I", table, 20, i)
        struct.pack_into("<I", table, 0, zlib.crc32(table[4:]))
        disk.seek(LOGICAL_OFFSET + i * len(table))
        disk.write(table)


def prepare_root(source: Path, output: Path, board: Board) -> None:
    rootfs.copy_source(source, output, maximum_size=PARTITIONS[3][3])
    # The update's compact root has no spare inodes for the updater's tp link.
    with output.open("r+b") as stream:
        stream.truncate(PARTITIONS[3][3])
    subprocess.run([str(rootfs.find_debugfs().with_name("resize2fs")), str(output)],
                    check=True, stdout=subprocess.DEVNULL)
    # The factory archive links these fonts into /ebrmain, but FAT cannot store
    # symlinks. Install the original font contents at the archive's paths.
    exclusion = " --exclude=system/adobe/fonts" if board.copy_adobe_fonts else ""
    font_copy = (
        "    mkdir -p /mnt/ext1/system/adobe/fonts || exit 1\n"
        "    cp -L /ebrmain/adobefonts/* /mnt/ext1/system/adobe/fonts/ || exit 1\n"
        if board.copy_adobe_fonts else ""
    )
    directories = " ".join(f"/mnt/ext1/{name}" for name in board.factory_directories)
    make_directories = f"    mkdir -p {directories} || exit 1\n" if directories else ""
    # Standby and its wakeup sources are not modeled. Keep the stock monitor's
    # suspend request from freezing userspace while retaining its normal loop.
    suspend = "mount -o bind /dev/null /sys/power/state || exit 1\n" if board.disable_suspend else ""

    def seed(contents: str) -> str:
        marker = "\n#RUNNING AP\n"
        if contents.count(marker) != 1:
            raise ValueError("PocketBook B288 has an unexpected startup script")
        return contents.replace(marker, (
            "\nmount -t vfat -o rw,umask=0000,iocharset=utf8 /dev/user_int /mnt/ext1 || exit 1\n"
            "if [ ! -f /mnt/ext1/system/.qemu-factory-content ]; then\n"
            f"    tar xzf /ebrmain/fsimage.tar.gz{exclusion} -C /mnt/ext1 || exit 1\n"
            + font_copy + make_directories
            + "    touch /mnt/ext1/system/.qemu-factory-content || exit 1\n"
            "    sync\n"
            "fi\n" + suspend + marker
        ))
    rootfs.transform_file(output, "/etc/init.d/rcS", "0100755", seed)
    if board.touch_module:
        # The vendor updater selects the hardware variant's touch module.
        rootfs.run_many(output, [f"symlink /lib/modules/tp.ko {board.touch_module}"], writable=True)


def prepare_ioc_applications(source: Path, output: Path, *, model: str) -> None:
    """Let the selected IOC use its existing unprovisioned serial response."""
    patch = IOC_PATCHES[model]
    rootfs.copy_source(source, output, maximum_size=PARTITIONS[4][3])
    with tempfile.TemporaryDirectory(prefix=f"{model}-ioc-", dir=output.parent) as temporary:
        squashfs = Path(temporary) / "cramfs.img"
        rootfs.run(output, f'dump /cramfs.img "{squashfs}"')
        # The first libioc.so data block in this release is a zlib stream.
        # Its protected ARM word at file offset 0xf0a4 is stored literally
        # in a deflate block. Change the invalid-pbenv result from fatal (3)
        # to unprovisioned (0), without changing the signed-record checks.
        patch_offset = 0xf0a4
        with squashfs.open("r+b") as stream:
            header = stream.read(32)
            if (header[:4] != b"hsqs" or struct.unpack_from("<I", header, 12)[0] != 131072 or
                    struct.unpack_from("<H", header, 20)[0] != 1):
                raise ValueError(f"{model} requires its original {patch.release} SquashFS")
            stream.seek(patch.block_offset)
            encoded = bytearray(stream.read(patch.block_size))
            if len(encoded) != patch.block_size:
                raise ValueError(f"{model} IOC data block is truncated")
            decoded = bytearray(zlib.decompress(encoded))
            if (len(decoded) != 131072 or decoded[:4] != b"\x7fELF" or
                    decoded[patch_offset:patch_offset + 4] != patch.original):
                raise ValueError(f"{model} IOC guard differs from firmware {patch.release}")
            context = decoded[patch_offset - 16:patch_offset + 20]
            if encoded.count(context) != 1:
                raise ValueError(f"{model} IOC guard is not a unique literal")
            position = encoded.index(context) + 16
            encoded[position:position + 4] = patch.replacement
            decoded[patch_offset:patch_offset + 4] = patch.replacement
            encoded[-4:] = struct.pack(">I", zlib.adler32(decoded))
            if zlib.decompress(encoded) != decoded:
                raise ValueError(f"{model} IOC patch changed unrelated data")
            stream.seek(patch.block_offset)
            stream.write(encoded)
        rootfs.replace_file(output, squashfs, "/cramfs.img", "0100644")


def build_waveform() -> bytes:
    """Neutral transitions for the emulator's directly rendered EINK output."""
    waveform = bytearray(1024)
    waveform[:0x30] = neutral_waveform_header()[:0x30]
    waveform[0x1c:0x20] = bytes(4)
    waveform[0x20:0x24] = bytes((0x34, 0, 0, 0x34))
    waveform[0x30:0x33] = bytes((0, 35, 85))
    for mode in range(4):
        offset = 0x44 + mode * 8
        waveform[0x34 + mode * 4:0x38 + mode * 4] = bytes((offset, 0, 0, offset))
        for temperature in range(2):
            waveform[offset + temperature * 4:offset + temperature * 4 + 4] = b"\x64\0\0\x64"
    # The vendor module derives shorter modes from the direction of the
    # transitions. Include both polarities and blank lead/trailing frames.
    levels = [0 if old == new else 1 if new < old else 2
              for old in range(16) for new in range(16)]
    frame = bytes(sum(levels[i + j] << (j * 2) for j in range(4))
                  for i in range(0, 256, 4))
    packed = bytes(64) + frame * 8 + bytes(64)
    encoded = bytearray()
    position = 0
    while position < len(packed):
        end = position + 1
        while end < len(packed) and packed[end] == packed[position] and end - position < 256:
            end += 1
        encoded.extend((packed[position], end - position - 1))
        position = end
    encoded.append(255)
    encoded.append(sum(encoded) & 255)
    waveform[0x64:0x64 + len(encoded)] = encoded
    struct.pack_into("<I", waveform, 0, 0)
    struct.pack_into("<I", waveform, 4, len(waveform))
    waveform[0x1f] = sum(waveform[:0x1f]) & 255
    waveform[0x2f] = sum(waveform[0x20:0x2f]) & 255
    struct.pack_into("<I", waveform, 0, zlib.crc32(waveform))
    return bytes(waveform)


def build(output: Path, artifacts: dict[str, Path], *, model: str) -> None:
    board = BOARDS[model]
    validate_firmware(artifacts)
    prepared = output.with_name("prepared-rootfs.img")
    prepare_root(artifacts["rootfs"], prepared, board)
    applications = artifacts["applications"]
    if model in IOC_PATCHES:
        applications = output.with_name("prepared-applications.img")
        prepare_ioc_applications(artifacts["applications"], applications, model=model)
    secure = output.with_name("secure.img")
    with secure.open("wb") as stream:
        stream.truncate(PARTITIONS[5][3])
    subprocess.run([str(rootfs.find_debugfs().with_name("mke2fs")), "-q", "-t", "ext2",
                    "-F", "-O", "none,filetype,sparse_super", str(secure)], check=True)
    secure_commands = [
        "mkdir /pbpk", "mkdir /runonce", "set_inode_field / uid 102",
        "set_inode_field / gid 102", "set_inode_field / mode 040770",
        "set_inode_field /pbpk uid 102", "set_inode_field /pbpk gid 102",
        "set_inode_field /pbpk mode 040770",
        "set_inode_field /runonce uid 102", "set_inode_field /runonce gid 102",
    ]
    # The monitor's callback state includes the eMMC CID. Prepared IOC
    # fallbacks return twelve ASCII zeroes; other profiles return an empty serial.
    # OTA packages omit this provisioned secure-partition file.
    with tempfile.TemporaryDirectory(prefix="pocketbook-b288-factory-") as temporary:
        files = {".freezestatus": struct.pack("<I", board.factory_state)}
        for name, contents in files.items():
            host_file = Path(temporary) / name
            host_file.write_bytes(contents)
            secure_commands.extend([
                f'write "{host_file}" /{name}',
                f"set_inode_field /{name} uid 102",
                f"set_inode_field /{name} gid 102",
                f"set_inode_field /{name} mode 0100660",
            ])
        rootfs.run_many(secure, secure_commands, writable=True)
    with atomic_output(output) as staging, staging.open("w+b") as disk:
        disk.truncate(DISK_SIZE)
        write_partition_tables(disk)
        package = artifacts["bootloader"].read_bytes()
        for sector in (24576, 32800):
            disk.seek(sector * 512)
            disk.write(package)
        files = {
            b"UIMAGE     ": artifacts["kernel"].read_bytes(),
            b"UPDATEFS   ": artifacts["recoveryfs"].read_bytes(),
            # Select the board's entry in the vendor hwlib platform table.
            b"HWCONFIG   ": struct.pack("<Q", (board.platform_index << 4) | 0x0a),
            b"DEFAULT WBF": (artifacts["waveform"].read_bytes()
                              if "waveform" in artifacts else build_waveform()),
        }
        write_bootfs(disk, files)
        for image, part in ((prepared, 3), (applications, 4), (secure, 5)):
            disk.seek(PARTITIONS[part][2])
            with image.open("rb") as source:
                shutil.copyfileobj(source, disk)
        write_userstore(disk, start=PARTITIONS[-1][2] // 512,
                         end=DISK_SIZE // 512, label=b"PocketBook ")
