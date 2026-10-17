"""PocketBook A13 updates and stock-kernel internal storage images."""

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
from .pocketbook import build_waveform as waveform_header
from .pocketbook_b288 import factory_font_cache_seed, partition_entry, write_bootfs

MIB = 1024**2
DISK_SIZE = 2 * 1024**3
# The stock fstab and startup script require these DOS partition numbers.
# Keep the same boot FAT geometry as the other Sunxi PocketBook images.
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
    ord("k"): ("kernel", "Image"),
    ord("c"): ("recoveryfs", "updatefs"),
    ord("r"): ("rootfs", "rootfs.img"),
    ord("e"): ("applications", "applications.img"),
}


@dataclass(frozen=True)
class Board:
    update_model: bytes
    platform_index: int
    kernel_size: int
    factory_state: int


BOARDS = {
    # Index 30 is the original XH7/Elan touchscreen revision (touch ID 8).
    # The unmodified A13 IOC exposes an empty serial, selecting this factory word.
    "pocketbook-627": Board(b"PocketBook627", 30, 4023412, 0x19d85675),
}


def validate_firmware(artifacts: dict[str, Path], *, model: str) -> None:
    board = BOARDS[model]
    kernel = artifacts["kernel"]
    with kernel.open("rb") as stream:
        head = stream.read(16)
    # The vendor supplies an uncompressed Image with its own ARM entry stub,
    # machine ID 0xDA8 and ATAGS pointer 0x40000000, rather than a zImage/uImage.
    if (kernel.stat().st_size != board.kernel_size or
            head != bytes.fromhex("0000a0e3010000eaa80d000000000040")):
        raise ValueError("PocketBook 627 requires its complete 6.5.2898 ARM Image")
    recovery = artifacts["recoveryfs"]
    with recovery.open("rb") as stream:
        head = stream.read(8)
    if (len(head) != 8 or head[:4] != bytes.fromhex("453dcd28") or
            struct.unpack_from("<I", head, 4)[0] != recovery.stat().st_size):
        raise ValueError("PocketBook A13 recovery must be a complete cramfs image")
    for role, partition in (("rootfs", 3), ("applications", 4)):
        image = artifacts[role]
        with image.open("rb") as stream:
            stream.seek(1024)
            sb = stream.read(1024)
        if (len(sb) != 1024 or sb[56:58] != b"\x53\xef" or
                image.stat().st_size > PARTITIONS[partition][3]):
            raise ValueError(f"PocketBook A13 {role} must be an ext filesystem that fits its partition")
        blocks, = struct.unpack_from("<I", sb, 4)
        shift, = struct.unpack_from("<I", sb, 24)
        if not blocks or shift > 2 or blocks * (1024 << shift) > image.stat().st_size:
            raise ValueError(f"PocketBook A13 {role} filesystem is truncated")


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


def write_partition_tables(disk) -> None:
    extended = 60 * MIB
    end = PARTITIONS[5][2] + PARTITIONS[5][3]
    mbr = bytearray(512)
    for index, partition in enumerate((PARTITIONS[-1], PARTITIONS[0])):
        _, _, start, size, kind = partition
        mbr[446 + index * 16:462 + index * 16] = partition_entry(kind, start, size)
    mbr[478:494] = partition_entry(0x0f, extended, end - extended)
    mbr[510:] = b"\x55\xaa"
    disk.seek(0)
    disk.write(mbr)
    logical = PARTITIONS[1:-1]
    for index, (_, _, start, size, kind) in enumerate(logical):
        ebr_start = start - MIB
        ebr = bytearray(512)
        ebr[446:462] = partition_entry(kind, start - ebr_start, size)
        if index + 1 < len(logical):
            next_start = logical[index + 1][2] - MIB
            ebr[462:478] = partition_entry(0x0f, next_start - extended, end - next_start)
        ebr[510:] = b"\x55\xaa"
        disk.seek(ebr_start)
        disk.write(ebr)


def prepare_root(source: Path, output: Path, *, applications: Path) -> None:
    rootfs.copy_source(source, output, maximum_size=PARTITIONS[3][3])
    with output.open("r+b") as stream:
        stream.truncate(PARTITIONS[3][3])
    subprocess.run([str(rootfs.find_debugfs().with_name("resize2fs")), str(output)],
                   check=True, stdout=subprocess.DEVNULL)
    font_cache = factory_font_cache_seed(applications)

    def seed(contents: str) -> str:
        marker = "\n#RUNNING AP\n"
        if contents.count(marker) != 1:
            raise ValueError("PocketBook A13 has an unexpected startup script")
        return contents.replace(marker, (
            "\nmount -t vfat -o rw,umask=0000,iocharset=utf8 /dev/user_int /mnt/ext1 || exit 1\n"
            "if [ ! -f /mnt/ext1/system/.qemu-factory-content ]; then\n"
            "    tar xzf /ebrmain/fsimage.tar.gz --exclude=system/adobe/fonts -C /mnt/ext1 || exit 1\n"
            "    mkdir -p /mnt/ext1/system/adobe/fonts /mnt/ext1/Photo /mnt/ext1/Downloads || exit 1\n"
            "    cp -L /ebrmain/adobefonts/* /mnt/ext1/system/adobe/fonts/ || exit 1\n"
            + font_cache + "    touch /mnt/ext1/system/.qemu-factory-content || exit 1\n"
            "    sync\n"
            "fi\n"
            "mount -o bind /dev/null /sys/power/state || exit 1\n" + marker
        ))
    rootfs.transform_file(output, "/etc/init.d/rcS", "0100755", seed)


def build_waveform() -> bytes:
    """Create two-bit panel transitions for the native A13 software decoder."""
    # Native WJ pair indices are (new << 4) | old, packed low two bits first.
    # Code 1 darkens and code 2 lightens by one of the 16 gray levels.
    # Fifteen unit drives span black (0) through white (15); the stock parser
    # pads this odd frame count with one neutral frame for its DMA interleave.
    packed = bytearray()
    for frame in range(15):
        for new in range(16):
            for old_group in range(0, 16, 4):
                value = 0
                for lane in range(4):
                    old = old_group + lane
                    drive = (1 if old > new else 2) if frame < abs(new - old) else 0
                    value |= drive << (lane * 2)
                packed.append(value)
    encoded = bytearray()
    position = 0
    while position < len(packed):
        end = position + 1
        while end < len(packed) and packed[end] == packed[position] and end - position < 256:
            end += 1
        if packed[position] in (0xff, 0xfc):
            raise ValueError("PocketBook A13 transition collides with a waveform marker")
        encoded.extend((packed[position], end - position - 1))
        position = end
    encoded.append(0xff)
    encoded.append(sum(encoded) & 255)
    waveform = bytearray(max(1024, 0x70 + len(encoded)))
    waveform[:0x30] = waveform_header()[:0x30]
    waveform[0x1c:0x1f] = (0x33).to_bytes(3, "little")
    waveform[0x20:0x24] = bytes((0x40, 0, 0, 1))
    waveform[0x30:0x33] = bytes((0, 35, 35))
    for mode in range(4):
        table = 0x50 + mode * 8
        for offset, value in ((0x40 + mode * 4, table), (table, 0x70), (table + 4, 0x70)):
            pointer = value.to_bytes(3, "little")
            waveform[offset:offset + 4] = pointer + bytes((sum(pointer) & 255,))
    waveform[0x70:0x70 + len(encoded)] = encoded
    struct.pack_into("<I", waveform, 0, 0)
    struct.pack_into("<I", waveform, 4, len(waveform))
    waveform[0x1f] = sum(waveform[8:0x1f]) & 255
    waveform[0x2f] = sum(waveform[0x20:0x2f]) & 255
    struct.pack_into("<I", waveform, 0, zlib.crc32(waveform))
    return bytes(waveform)


def build(output: Path, artifacts: dict[str, Path], *, model: str) -> None:
    board = BOARDS[model]
    validate_firmware(artifacts, model=model)
    prepared = output.with_name("prepared-rootfs.img")
    prepare_root(artifacts["rootfs"], prepared, applications=artifacts["applications"])
    secure = output.with_name("secure.img")
    with secure.open("wb") as stream:
        stream.truncate(PARTITIONS[5][3])
    subprocess.run([str(rootfs.find_debugfs().with_name("mke2fs")), "-q", "-t", "ext2",
                    "-F", "-O", "none,filetype,sparse_super", str(secure)], check=True)
    with tempfile.TemporaryDirectory(prefix="pocketbook-a13-factory-") as temporary:
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
    files = {
        b"UIMAGE     ": artifacts["kernel"].read_bytes(),
        b"UPDATEFS   ": artifacts["recoveryfs"].read_bytes(),
        b"HWCONFIG   ": struct.pack("<Q", (board.platform_index << 4) | 0x0a),
        b"DEFAULT WBF": (artifacts["waveform"].read_bytes()
                          if "waveform" in artifacts else build_waveform()),
    }
    with atomic_output(output) as staging, staging.open("w+b") as disk:
        disk.truncate(DISK_SIZE)
        write_partition_tables(disk)
        write_bootfs(disk, files)
        for image, partition in ((prepared, 3), (artifacts["applications"], 4), (secure, 5)):
            disk.seek(PARTITIONS[partition][2])
            with image.open("rb") as source:
                shutil.copyfileobj(source, disk)
        write_userstore(disk, start=PARTITIONS[-1][2] // 512,
                        end=DISK_SIZE // 512, label=b"PocketBook ")
