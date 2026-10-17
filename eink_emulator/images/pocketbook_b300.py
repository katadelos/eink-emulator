"""PocketBook B300 updates and native GPT/eMMC images."""

from __future__ import annotations

import gzip
import shutil
import struct
import subprocess
import tempfile
import uuid
import zipfile
import zlib
from pathlib import Path

from . import rootfs
from .common import atomic_output
from .forma import write_userstore
from .pocketbook_b288 import (
    Board, FactoryMonitor, IOCPatch, factory_font_cache_seed, offline_factory_seed,
    partition_entry, prepare_ioc_applications,
)

MIB = 1024**2
DISK_SIZE = 2 * 1024**3
LOGICAL_OFFSET = 20 * MIB
# U-Boot mounts root at p4; rcS/fstab and the IOC require p1/p2/p3/p5/p6.
# Unlike B288, the raw environment/IOC area occupies a single partition.
# GPT reserves its final 33 sectors after the user volume.
PARTITIONS = (
    ("boot", 2, 36 * MIB, 24 * MIB, 0x83),
    ("env", 3, 61 * MIB, 15 * MIB, 0x83),
    ("rootfs", 4, 77 * MIB, 47 * MIB, 0x83),
    ("ebrmain", 5, 125 * MIB, 511 * MIB, 0x83),
    ("secure", 6, 637 * MIB, 15 * MIB, 0x83),
    ("UDISK", 1, 768 * MIB, DISK_SIZE - 768 * MIB - 33 * 512, 0x0c),
)
IMPORT_FILES = {
    ord("u"): ("bootloader", "u-boot.img"),
    ord("k"): ("kernel", "uImage"),
    ord("c"): ("recoveryfs", "updatefs"),
    ord("r"): ("rootfs", "rootfs.img"),
    ord("e"): ("applications", "applications.img"),
}
BOARDS = {
    "pocketbook-743k3": Board(b"PocketBook743k3", 86, "", 0xa6c12675, True,
                             ("Photo", "Downloads"), True, offline_factory=True),
}
IOC_PATCHES = {
    "pocketbook-743k3": IOCPatch("6.10.2854", 216266204, 128698,
        bytes.fromhex("abfe0223"), bytes.fromhex("a8fe0223"),
        file_offset=0xeea8, compression=3, literal=bytes.fromhex(
            "d67d83f3f483724c74be7cecbc159abeabfe0223"
            "a0cc2c841f16a679a470b8b1372d9045")),
}
FACTORY_MONITORS = {
    b"PocketBook743k3": FactoryMonitor(1079104, 0x10493c, 0, 0x1000,
                                       0x104e50, 0x158ac),
}


def validate_firmware(artifacts: dict[str, Path], *, model: str) -> None:
    BOARDS[model]
    with artifacts["bootloader"].open("rb") as stream:
        head = stream.read(64)
    if (len(head) != 64 or head[:13] != b"sunxi-package" or
            struct.unpack_from("<I", head, 16)[0] != 0x89119800 or
            struct.unpack_from("<I", head, 36)[0] != artifacts["bootloader"].stat().st_size):
        raise ValueError("PocketBook B300 requires the complete vendor Sunxi boot package")
    with artifacts["kernel"].open("rb") as stream:
        head = stream.read(64)
    if (len(head) != 64 or head[:4] != b"\x27\x05\x19\x56" or
            struct.unpack_from(">I", head, 12)[0] + 64 != artifacts["kernel"].stat().st_size):
        raise ValueError("PocketBook B300 kernel must be a complete vendor uImage")
    for role, index in (("rootfs", 2), ("applications", 3)):
        image = artifacts[role]
        with image.open("rb") as stream:
            stream.seek(1024)
            sb = stream.read(1024)
        if (len(sb) != 1024 or sb[56:58] != b"\x53\xef" or
                image.stat().st_size > PARTITIONS[index][3]):
            raise ValueError(f"PocketBook B300 {role} must be an ext filesystem that fits its partition")
        blocks, = struct.unpack_from("<I", sb, 4)
        shift, = struct.unpack_from("<I", sb, 24)
        if not blocks or shift > 2 or blocks * (1024 << shift) > image.stat().st_size:
            raise ValueError(f"PocketBook B300 {role} filesystem is truncated")


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
        validate_firmware(installed, model=model)
        prepared.replace(destination)
    return {role: destination / path.name for role, path in installed.items()}


def write_partition_tables(disk, *, model: str) -> None:
    """Write native GPT numbering and the bootloader's redundant Sunxi table."""
    sectors = DISK_SIZE // 512
    mbr = bytearray(512)
    mbr[446:462] = partition_entry(0xee, 512, DISK_SIZE - 512)
    mbr[510:] = b"\x55\xaa"
    disk.seek(0)
    disk.write(mbr)
    entries = bytearray(128 * 128)
    namespace = uuid.uuid5(uuid.NAMESPACE_DNS, model)
    for name, number, start, size, kind in PARTITIONS:
        type_id = uuid.UUID("ebd0a0a2-b9e5-4433-87c0-68b6b72699c7" if kind in (6, 12)
                            else "0fc63daf-8483-4772-8e79-3d69d8477de4")
        struct.pack_into("<16s16sQQQ72s", entries, (number - 1) * 128,
                         type_id.bytes_le, uuid.uuid5(namespace, name).bytes_le,
                         start // 512, (start + size) // 512 - 1, 0,
                         name.encode("utf-16-le"))
    for current, backup, entry_sector in ((1, sectors - 1, 2),
                                          (sectors - 1, 1, sectors - 33)):
        header = bytearray(512)
        struct.pack_into("<8s4I4Q16sQ3I", header, 0, b"EFI PART", 0x10000, 92, 0, 0,
                         current, backup, 34, sectors - 34, namespace.bytes_le,
                         entry_sector, 128, 128, zlib.crc32(entries))
        struct.pack_into("<I", header, 16, zlib.crc32(header[:92]))
        disk.seek(entry_sector * 512)
        disk.write(entries)
        disk.seek(current * 512)
        disk.write(header)
    table = bytearray(16 * 1024)
    struct.pack_into("<I8s4I", table, 4, 0x100, b"softw411", 4, 0, len(PARTITIONS), 0)
    for index, (name, _, start, size, _) in enumerate(PARTITIONS):
        struct.pack_into("<4I16s16s", table, 32 + index * 128, 0,
                         (start - LOGICAL_OFFSET) // 512, 0, size // 512,
                         b"DISK", name.encode())
    for index in range(4):
        struct.pack_into("<I", table, 20, index)
        struct.pack_into("<I", table, 0, zlib.crc32(table[4:]))
        disk.seek(LOGICAL_OFFSET + index * len(table))
        disk.write(table)


def prepare_root(source: Path, output: Path, board: Board, *, applications: Path) -> None:
    rootfs.copy_source(source, output, maximum_size=PARTITIONS[2][3])
    with output.open("r+b") as stream:
        stream.truncate(PARTITIONS[2][3])
    subprocess.run([str(rootfs.find_debugfs().with_name("resize2fs")), str(output)],
                   check=True, stdout=subprocess.DEVNULL)
    font_cache = factory_font_cache_seed(applications)
    monitor_source = "/ebrmain/cramfs/bin/monitor.app"
    layout = ""
    factory = offline_factory_seed(board, monitor=FACTORY_MONITORS[board.update_model],
                                   source=monitor_source)

    def seed(contents: str) -> str:
        devpts = "mount -t devpts devpts /dev/pts\n"
        if contents.count(devpts) != 1:
            raise ValueError("PocketBook B300 has an unexpected devpts mount")
        # Native devtmpfs hides the root image's /dev directory at boot.
        contents = contents.replace(devpts, "mkdir -p /dev/pts\n" + devpts)
        mali = "insmod /lib/modules/mali.ko\n"
        if contents.count(mali) != 1:
            raise ValueError("PocketBook B300 has an unexpected Mali startup")
        # Optional 3D acceleration is independent of the CPU/e-paper UI path.
        contents = contents.replace(mali, "")
        marker = "\ncd /ebrmain\n"
        if contents.count(marker) != 1:
            raise ValueError("PocketBook B300 has an unexpected startup script")
        return contents.replace(marker, (
            "\nmount -t vfat -o rw,umask=0000,iocharset=utf8 /dev/user_int /mnt/ext1 || exit 1\n"
            "if [ ! -f /mnt/ext1/system/.qemu-factory-content ]; then\n"
            "    tar xzf /ebrmain/fsimage.tar.gz --exclude=system/adobe/fonts -C /mnt/ext1 || exit 1\n"
            "    mkdir -p /mnt/ext1/system/adobe/fonts /mnt/ext1/Photo /mnt/ext1/Downloads || exit 1\n"
            "    cp -L /ebrmain/adobefonts/* /mnt/ext1/system/adobe/fonts/ || exit 1\n"
            + font_cache + "    touch /mnt/ext1/system/.qemu-factory-content || exit 1\n"
            "    sync\n"
            "fi\n"
            "mount -o bind /dev/null /sys/power/state || exit 1\n"
            + layout + factory + marker
        ))
    rootfs.transform_file(output, "/etc/init.d/rcS", "0100755", seed)


def prepare_boot(output: Path, artifacts: dict[str, Path], board: Board) -> None:
    # The original U-Boot uses ext4load mmc 2:2, including for recovery.
    # Its ext reader accepts this ext2 volume without a journal or modern features.
    with output.open("wb") as stream:
        stream.truncate(PARTITIONS[0][3])
    subprocess.run([str(rootfs.find_debugfs().with_name("mke2fs")), "-q", "-t", "ext2",
                    "-F", "-L", "BOOT", "-O", "none,filetype,sparse_super", str(output)],
                   check=True)
    with tempfile.TemporaryDirectory(prefix="pocketbook-b300-boot-") as temporary:
        work = Path(temporary)
        hardware = work / "hwconfig"
        hardware.write_bytes(struct.pack("<Q", (board.platform_index << 4) | 0x0a))
        waveform = artifacts.get("waveform", work / "default.awf")
        if "waveform" not in artifacts:
            waveform.write_bytes(build_waveform())
        files = ((artifacts["kernel"], "uImage"), (artifacts["recoveryfs"], "updatefs"),
                 (hardware, "hwconfig"), (waveform, "default.awf"))
        rootfs.run_many(output, [command for source, name in files for command in (
            f'write "{source}" /{name}', f"set_inode_field /{name} mode 0100644",
        )], writable=True)


def build_waveform() -> bytes:
    """Native AWF tables for all sixteen gray levels and all update modes."""
    waveform = bytearray(0xe0)
    waveform[1:8] = b"B300K3\0"
    waveform[0x80:0x82] = bytes((0, 85))
    frames = bytearray()
    for frame in range(16):
        for old5 in range(32):
            for new5 in range(32):
                old, new = old5 >> 1, new5 >> 1
                frames.append((1 if old > new else 2) if frame < abs(new - old) else 0)

    def mode(lead: int) -> int:
        start = len(waveform)
        waveform.extend(struct.pack("<32I", *([128] * 32)))
        waveform.extend(struct.pack("<HH", 16 + lead, 0))
        waveform.extend(bytes(1024 * lead))
        waveform.extend(frames)
        return start

    # A newly enabled pipe decodes once before the native IRQ publishes its new
    # index. Prime it with a neutral frame and retain the trailing neutral frame
    # for the extra end scans. A2 skips floor(DU_frames * 65 / 100), so 32 leading
    # neutral frames in its 48-frame table leave one guard plus the 16-frame body.
    ordinary, du = mode(1), mode(32)
    struct.pack_into("<16I", waveform, 0xa0,
                     *(du if index == 3 else ordinary for index in range(16)))
    return bytes(waveform)


def build(output: Path, artifacts: dict[str, Path], *, model: str) -> None:
    board = BOARDS[model]
    validate_firmware(artifacts, model=model)
    prepared = output.with_name("prepared-rootfs.img")
    prepare_root(artifacts["rootfs"], prepared, board, applications=artifacts["applications"])
    applications = output.with_name("prepared-applications.img")
    prepare_ioc_applications(artifacts["applications"], applications, model=model,
                             patch=IOC_PATCHES[model], maximum_size=PARTITIONS[3][3])
    boot = output.with_name("boot.img")
    prepare_boot(boot, artifacts, board)
    secure = output.with_name("secure.img")
    with secure.open("wb") as stream:
        stream.truncate(PARTITIONS[4][3])
    subprocess.run([str(rootfs.find_debugfs().with_name("mke2fs")), "-q", "-t", "ext2",
                    "-F", "-O", "none,filetype,sparse_super", str(secure)], check=True)
    with tempfile.TemporaryDirectory(prefix="pocketbook-b300-factory-") as temporary:
        state = Path(temporary) / ".freezestatus"
        state.write_bytes(struct.pack("<I", board.factory_state))
        rootfs.run_many(secure, [
            "mkdir /pbpk", "mkdir /runonce", "set_inode_field / uid 102",
            "set_inode_field / gid 102", "set_inode_field / mode 040770",
            "set_inode_field /pbpk uid 102", "set_inode_field /pbpk gid 102",
            "set_inode_field /pbpk mode 040770",
            "set_inode_field /runonce uid 102", "set_inode_field /runonce gid 102",
            f'write "{state}" /.freezestatus',
            "set_inode_field /.freezestatus uid 102",
            "set_inode_field /.freezestatus gid 102",
            "set_inode_field /.freezestatus mode 0100660",
        ], writable=True)
    with atomic_output(output) as staging, staging.open("w+b") as disk:
        disk.truncate(DISK_SIZE)
        write_partition_tables(disk, model=model)
        package = artifacts["bootloader"].read_bytes()
        for sector in (24576, 32800):
            disk.seek(sector * 512)
            disk.write(package)
        for image, index in ((boot, 0), (prepared, 2), (applications, 3), (secure, 4)):
            disk.seek(PARTITIONS[index][2])
            with image.open("rb") as source:
                shutil.copyfileobj(source, disk)
        write_userstore(disk, start=PARTITIONS[-1][2] // 512,
                         end=(PARTITIONS[-1][2] + PARTITIONS[-1][3]) // 512,
                         label=b"PocketBook ")
