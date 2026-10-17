"""PocketBook B288 updates and board-specific eMMC images."""

from __future__ import annotations

import base64
import gzip
import re
import shlex
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
    waveform_name: bytes = b""
    offline_factory: bool = False
    large_applications: bool = False


BOARDS = {
    "pocketbook-618": Board(b"PocketBook618", 80, "", 0xa6c12675, True,
                           ("Photo", "Downloads"), True, offline_factory=True),
    # Index 52 selects the original 628's XCD touch ID 22, not its FT6336 revision.
    "pocketbook-628": Board(b"PocketBook628", 52, "ektf2k_5B.ko", 0xa6c12675,
                           True, ("Photo", "Downloads"), True),
    # 6.11 stores regular Adobe fonts in the factory archive, without /ebrmain links.
    "pocketbook-629": Board(b"PocketBook629", 84, "", 0xa6c12675, False,
                           ("Photo", "Downloads"), True, offline_factory=True,
                           large_applications=True),
    "pocketbook-632": Board(b"PocketBook632", 34, "", 0x19d85675, False, (), False),
    "pocketbook-633": Board(b"PocketBook633", 51, "", 0xa6c12675, True,
                           ("Photo", "Downloads"), True, waveform_name=b"EC060KH1",
                           offline_factory=True),
    "pocketbook-634": Board(b"PocketBook634", 81, "", 0xa6c12675, True,
                           ("Photo", "Downloads"), True, offline_factory=True,
                           large_applications=True),
    "pocketbook-700": Board(b"PocketBook700", 71, "", 0xa6c12675, True,
                           ("Photo", "Downloads"), True, waveform_name=b"ED070_QEMU",
                           offline_factory=True, large_applications=True),
    "pocketbook-740": Board(b"PocketBook740", 31, "cyttsp5.ko", 0x19d85675, False, (), False),
    "pocketbook-740-2": Board(b"PocketBook740-2", 45, "cyttsp5.ko", 0x19d85675,
                             True, ("Photo", "Downloads"), True),
    "pocketbook-741": Board(b"PocketBook741", 53, "cyttsp5.ko", 0xa6c12675,
                           True, ("Photo", "Downloads"), True, waveform_name=b"EC078",
                           offline_factory=True, large_applications=True),
    "pocketbook-970": Board(b"PocketBook970", 67, "", 0xa6c12675, True,
                           ("Photo", "Downloads"), True, offline_factory=True),
    "pocketbook-1040": Board(b"PocketBook1040", 47, "", 0xa6c12675,
                            True, ("Photo", "Downloads"), True),
}


@dataclass(frozen=True)
class IOCPatch:
    release: str
    block_offset: int
    block_size: int
    original: bytes
    replacement: bytes
    file_offset: int = 0xf0a4
    compression: int = 1
    literal: bytes = b""


IOC_PATCHES = {
    "pocketbook-618": IOCPatch("6.9.1044", 124003433, 127950,
                              bytes.fromhex("2ba65c49"), bytes.fromhex("28a65c49"),
                              file_offset=0xf0f8),
    "pocketbook-628": IOCPatch("6.5.2890", 157436504, 127961,
                              bytes.fromhex("6f74ced5"), bytes.fromhex("6c74ced5")),
    "pocketbook-629": IOCPatch("6.11.2020", 195291824, 113541,
                              bytes.fromhex("ff5fd840"), bytes.fromhex("fc5fd840"),
                              file_offset=0x12028, compression=3, literal=bytes.fromhex(
                                  "e19a7f98399a35f48fed4432c4da4900ff5fd840"
                                  "9c1e20de1fcfb7abacacc403f898a1f3")),
    "pocketbook-633": IOCPatch("6.8.2817", 183405925, 128484,
                              bytes.fromhex("dff17371"), bytes.fromhex("dcf17371"),
                              file_offset=0xf0f8, compression=3, literal=bytes.fromhex(
                                  "7aebeb4178c0586b10060f59a47af252dff17371"
                                  "8c6938b7c65243af9ca6f770f302e973")),
    "pocketbook-634": IOCPatch("6.10.3425", 217848953, 128720,
                              bytes.fromhex("4ffb96fb"), bytes.fromhex("4cfb96fb"),
                              file_offset=0xee78, compression=3, literal=bytes.fromhex(
                                  "feefdde84cc5091c30724a96c84e753b4ffb96fb"
                                  "a4a141cec7625fb72c8c2e22c3fd824c")),
    "pocketbook-700": IOCPatch("6.10.3209", 217976364, 128716,
                              bytes.fromhex("2ff2bd37"), bytes.fromhex("2cf2bd37"),
                              file_offset=0xee78, compression=3, literal=bytes.fromhex(
                                  "ee261618e87429c5d0c4036bdc84fec42ff2bd37"
                                  "0c8137abbbd4973ff8ec56540fa6bc05")),
    "pocketbook-741": IOCPatch("6.8.4079", 187215067, 128482,
                              bytes.fromhex("6f7790dd"), bytes.fromhex("6c7790dd"),
                              file_offset=0xf0f8, compression=3, literal=bytes.fromhex(
                                  "ca30fef63078751264cc044324ae48026f7790dd"
                                  "88eafe2a3e5083eaf029ec556bdea666")),
    "pocketbook-970": IOCPatch("6.8.4644", 186382527, 128480,
                              bytes.fromhex("83fd9f3d"), bytes.fromhex("80fd9f3d"),
                              file_offset=0xf0f8, compression=3, literal=bytes.fromhex(
                                  "b68a7af00857273948f80bbcc8511e6583fd9f3d"
                                  "e45199f00a281d83002174d75f555588")),
    "pocketbook-1040": IOCPatch("6.5.2920", 165964900, 127969,
                               bytes.fromhex("07523114"), bytes.fromhex("04523114")),
}


@dataclass(frozen=True)
class FactoryMonitor:
    file_size: int
    rx_size: int
    rx_address: int
    rx_alignment: int
    rw_file_offset: int
    call_file_offset: int
    call_context: bytes = bytes.fromhex("33ff2fe10060a0e15080a0e3000054e3")


MONITOR_610 = FactoryMonitor(677700, 0xa2c28, 0, 0x1000, 0xa2e50, 0x158a4)
FACTORY_MONITORS = {
    b"PocketBook618": FactoryMonitor(673452, 0xa167c, 0x10000, 0x10000,
                                     0xa1ed4, 0x177d8),
    b"PocketBook629": FactoryMonitor(674128, 0xa1ba0, 0, 0x1000,
                                     0xa1e50, 0x17ce0,
                                     bytes.fromhex("33ff2fe100a0a0e150b0a0e3000054e3")),
    b"PocketBook633": FactoryMonitor(358000, 0x543ac, 0x10000, 0x10000,
                                     0x54ed4, 0x17b10),
    b"PocketBook634": MONITOR_610,
    b"PocketBook700": MONITOR_610,
    b"PocketBook741": FactoryMonitor(1083088, 0x1052c0, 0x10000, 0x10000,
                                     0x105ed4, 0x17a20),
    b"PocketBook970": FactoryMonitor(673472, 0xa1618, 0x10000, 0x10000,
                                     0xa1ed4, 0x17a20),
}


def board_partitions(board: Board) -> tuple[tuple[str, int, int, int, int], ...]:
    if not board.large_applications:
        return PARTITIONS
    # Current updates contain a roughly 500 MiB applications filesystem.
    # Keep vendor partition numbering and the boot/root offsets unchanged.
    return PARTITIONS[:4] + (
        ("ebrmain", 8, 129 * MIB, 511 * MIB, 0x83),
        ("secure", 9, 641 * MIB, 15 * MIB, 0x83),
        ("UDISK", 1, 768 * MIB, DISK_SIZE - 768 * MIB, 0x0c),
    )


def validate_firmware(artifacts: dict[str, Path], *, model: str) -> None:
    partitions = board_partitions(BOARDS[model])
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
    for role, limit in (("rootfs", partitions[3][3]), ("applications", partitions[4][3])):
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
        validate_firmware(installed, model=model)
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


def write_partition_tables(disk, partitions: tuple[tuple[str, int, int, int, int], ...]) -> None:
    extended = 60 * MIB
    end = partitions[5][2] + partitions[5][3]
    mbr = bytearray(512)
    for index in (0, 1):
        _, _, start, size, kind = partitions[-1 if index == 0 else 0]
        mbr[446 + index * 16:462 + index * 16] = partition_entry(kind, start, size)
    mbr[478:494] = partition_entry(0x0f, extended, end - extended)
    mbr[510:] = b"\x55\xaa"
    disk.seek(0)
    disk.write(mbr)
    logical = partitions[1:-1]
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
    struct.pack_into("<I8s4I", table, 4, 0x100, b"softw411", 4, 0, len(partitions), 0)
    for i, (name, _, start, size, _) in enumerate(partitions):
        struct.pack_into("<4I16s16s", table, 32 + i * 128, 0,
                         (start - LOGICAL_OFFSET) // 512, 0, size // 512,
                         b"DISK", name.encode())
    for i in range(4):
        struct.pack_into("<I", table, 20, i)
        struct.pack_into("<I", table, 0, zlib.crc32(table[4:]))
        disk.seek(LOGICAL_OFFSET + i * len(table))
        disk.write(table)


def factory_font_cache_seed(applications: Path) -> str:
    """Match the bundled font indexes to the prepared filesystems."""
    with tempfile.TemporaryDirectory(prefix="pocketbook-font-cache-") as temporary:
        archive_path = Path(temporary) / "fsimage.tar.gz"
        rootfs.run(applications, f'dump /fsimage.tar.gz "{archive_path}"')
        with tarfile.open(archive_path) as archive:
            members = archive.getmembers()
            commands = []
            for member in members:
                version = re.search(r"\.cache-(7|8|9)$", member.name)
                if (not member.isfile() or version is None or
                        Path(member.name).parent != Path("system/cache/fontconfig")):
                    continue
                cache = archive.extractfile(member).read()
                if (len(cache) < 40 or struct.unpack_from("<4I", cache) !=
                        (0xfc02fc04, int(version[1]), len(cache), 40)):
                    raise ValueError("PocketBook requires its bundled ARM fontconfig cache")
                directory = cache[40:].split(b"\0", 1)[0].decode()
                if directory.startswith("/ebrmain/"):
                    metadata = subprocess.check_output([
                        str(rootfs.find_debugfs()), "-R",
                        f"stat {directory.removeprefix('/ebrmain')}", str(applications),
                    ], text=True, stderr=subprocess.DEVNULL)
                    modified = re.search(r"^mtime: 0x([0-9a-f]+) --", metadata, re.MULTILINE)
                    if modified is None:
                        raise ValueError(f"PocketBook font directory has no mtime: {directory}")
                    checksum = int(modified[1], 16)
                elif directory.startswith("/mnt/ext1/"):
                    relative = Path(directory.removeprefix("/mnt/ext1/"))
                    names = sorted((Path(item.name).name for item in members
                                    if not item.isdir() and Path(item.name).parent == relative),
                                   reverse=True)
                    # Fontconfig uses a directory-listing checksum on FAT.
                    # Factory font links are copied as regular files (DT_REG=8).
                    checksum = zlib.adler32(b"".join(
                        name.encode() + b"\0" + struct.pack("<I", 8) for name in names))
                else:
                    raise ValueError(f"Unexpected PocketBook font directory: {directory}")
                # ARM v7/v8/v9 caches store the directory checksum and nanoseconds
                # at offsets 28 and 32; the font index itself stays untouched.
                stamp = "".join(f"\\{byte:03o}" for byte in struct.pack("<II", checksum, 0))
                destination = shlex.quote(f"/mnt/ext1/{member.name}")
                commands.append(
                    f"    printf '%b' '{stamp}' | dd of={destination} "
                    "bs=1 seek=28 conv=notrunc 2>/dev/null || exit 1\n")
    return "".join(commands)


def offline_factory_seed(board: Board, *, monitor: FactoryMonitor | None = None,
                         source: str = "/ebrmain/cramfs/bin/monitor.app") -> str:
    """Supply the blank emulator's local, non-contract configuration."""
    if not board.offline_factory:
        return ""
    # These monitors expect a safebox record even before enrolment.
    # The update has neither a provisioned IOC nor its vendor-signed partner
    # configuration. Invoke the native read first; retain every valid record.
    # Only failed reads for serial "000000000000\0" receive a zeroed header,
    # preventing its cache from copying an uninitialized length. For chunk 0,
    # supply 64 zero metadata bytes and an explicit non-contract profile.
    # Missing is_contract/lock_device fields default to locked in stock code.
    # Other failed chunks still return failure. Write/record verification
    # remain untouched. ARM code occupies the monitor's unused RX padding
    # and wraps its native IOC call. Query identity through IOC request 1:
    # the IPC service fork does not initialize the monitor's serialnum BSS.
    # All code and constants are position-independent, including under ASLR.
    # Call ABI: r0=operation/result, r1=chunk, r2=reply, r3=native function.
    # push {r1,r2,r3,lr}; sub sp,#24 saves the arguments and reserves an aligned
    # serial buffer without relying on compiler-specific register allocation.
    # Nonzero reads return directly. Otherwise call r3 with r0=1,r1=0,r2=sp, matching
    # ioc_getserialnumber. Three words plus a NUL identify the emulator.
    # A str/add/cmp loop clears 68 bytes; chunk 0 receives length/payload.
    # The byte-copy loop includes NUL for the stock C-string base64 decoder.
    # add sp,#24; pop {r1,r2,r3,pc} returns; callee-saved registers stay untouched.
    monitor = monitor if monitor is not None else FACTORY_MONITORS[board.update_model]
    configuration = base64.b64encode(
        b'{"is_contract":0,"lock_device":0,"next_check":0,"contract_end":-1}') + b"\0"
    provider = bytearray.fromhex(
        "0e402de918d04de233ff2fe1000050e32800001a1c209de5000052e32500000a"
        "0100a0e30010a0e30d20a0e120309de533ff2fe1000050e30000a0e31d00000a"
        "0d20a0e174c09fe5003092e50c0053e1043092050c005301083092050c005301"
        "0c30d205000053031200001a1c109de50020a0e30030a0e3032081e7043083e2"
        "440053e3fbffff3a18209de5000052e30800001a0020a0e3402081e544c081e2"
        "1c108fe20130d1e40130cce4012052e2fbffff1a0100a0e318d08de20e80bde8"
        "30303030")
    if len(configuration) > 255:
        raise ValueError("PocketBook local configuration exceeds its ARM immediate")
    # mov r2, #length at offset 0x94 supplies both reply length and copy count.
    struct.pack_into("<I", provider, 0x94, 0xe3a02000 | len(configuration))
    provider.extend(configuration)
    if len(provider) > monitor.rw_file_offset - monitor.rx_size:
        raise ValueError("PocketBook factory provider exceeds the monitor's RX padding")
    patches = (
        (0xa4, struct.pack("<II", monitor.rx_size + len(provider), monitor.rx_size + len(provider))),
        (monitor.call_file_offset, struct.pack("<I", 0xeb000000 |
            (((monitor.rx_size - monitor.call_file_offset - 8) // 4) & 0xffffff))),
        (monitor.rx_size, provider),
    )
    commands = [
        f"qemu_monitor={shlex.quote(source)}\n",
        "qemu_monitor_bytes() {\n",
        "    dd if=\"$qemu_monitor\" bs=1 skip=\"$1\" count=\"$2\" 2>/dev/null "
        "| hexdump -v -e '1/1 \"%02x\"'\n",
        "}\n",
        f"[ \"$(wc -c < \"$qemu_monitor\")\" -eq {monitor.file_size} ] || exit 1\n",
    ]
    guards = (
        (0, bytes.fromhex("7f454c46010101000000000000000000")),
        (0x94, struct.pack("<8I", 1, 0, monitor.rx_address, monitor.rx_address,
                          monitor.rx_size, monitor.rx_size, 5, monitor.rx_alignment)),
        (monitor.call_file_offset, monitor.call_context),
    )
    for offset, expected in guards:
        commands.append(
            f"[ \"$(qemu_monitor_bytes {offset} {len(expected)})\" = "
            f"{expected.hex()} ] || exit 1\n")
    commands.extend((
        f"[ -z \"$(qemu_monitor_bytes {monitor.rx_size} "
        f"{monitor.rw_file_offset - monitor.rx_size} | tr -d 0)\" ] || exit 1\n",
        "cp \"$qemu_monitor\" /tmp/qemu-pocketbook-monitor.app || exit 1\n",
    ))
    for offset, replacement in patches:
        octal = "".join(f"\\{byte:03o}" for byte in replacement)
        commands.append(
            f"printf '%b' '{octal}' | dd of=/tmp/qemu-pocketbook-monitor.app "
            f"bs=1 seek={offset} conv=notrunc 2>/dev/null || exit 1\n")
    commands.extend((
        "chmod 755 /tmp/qemu-pocketbook-monitor.app || exit 1\n",
        "mount -o bind /tmp/qemu-pocketbook-monitor.app /ebrmain/cramfs/bin/monitor.app || exit 1\n",
        "unset qemu_monitor\n",
    ))
    return "".join(commands)


def prepare_root(source: Path, output: Path, board: Board, *, applications: Path) -> None:
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
    # Update packages retain font indexes from before their final filesystem
    # timestamps. Reuse those indexes instead of rescanning CJK fonts while the
    # setup wizard waits for the licence application to draw its first page.
    font_cache = factory_font_cache_seed(applications)
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
            + font_copy + make_directories + font_cache
            + "    touch /mnt/ext1/system/.qemu-factory-content || exit 1\n"
            "    sync\n"
            "fi\n" + suspend + offline_factory_seed(board) + marker
        ))
    rootfs.transform_file(output, "/etc/init.d/rcS", "0100755", seed)
    if board.touch_module:
        # The vendor updater selects the hardware variant's touch module.
        rootfs.run_many(output, [f"symlink /lib/modules/tp.ko {board.touch_module}"], writable=True)


def prepare_ioc_applications(source: Path, output: Path, *, model: str,
                             patch: IOCPatch, maximum_size: int) -> None:
    """Let the selected IOC use its existing unprovisioned serial response."""
    rootfs.copy_source(source, output, maximum_size=maximum_size)
    with tempfile.TemporaryDirectory(prefix=f"{model}-ioc-", dir=output.parent) as temporary:
        squashfs = Path(temporary) / "cramfs.img"
        rootfs.run(output, f'dump /cramfs.img "{squashfs}"')
        # The protected ARM word is stored literally in the first libioc.so
        # data block. Change the invalid-pbenv result from fatal (3)
        # to unprovisioned (0), without changing the signed-record checks.
        patch_offset = patch.file_offset
        with squashfs.open("r+b") as stream:
            header = stream.read(32)
            if (header[:4] != b"hsqs" or struct.unpack_from("<I", header, 12)[0] != 131072 or
                    struct.unpack_from("<H", header, 20)[0] != patch.compression):
                raise ValueError(f"{model} requires its original {patch.release} SquashFS")
            stream.seek(patch.block_offset)
            encoded = bytearray(stream.read(patch.block_size))
            if len(encoded) != patch.block_size:
                raise ValueError(f"{model} IOC data block is truncated")
            decoded = bytearray(zlib.decompress(encoded)) if patch.compression == 1 else None
            if decoded is not None:
                if (len(decoded) != 131072 or decoded[:4] != b"\x7fELF" or
                        decoded[patch_offset:patch_offset + 4] != patch.original):
                    raise ValueError(f"{model} IOC guard differs from firmware {patch.release}")
                context = decoded[patch_offset - 16:patch_offset + 20]
            else:
                # LZO stores these encrypted words as one literal run. The
                # release-specific surrounding bytes also guard its location.
                context = patch.literal
                if len(context) != 36 or context[16:20] != patch.original:
                    raise ValueError(f"{model} has an invalid IOC literal patch")
            if encoded.count(context) != 1:
                raise ValueError(f"{model} IOC guard is not a unique literal")
            position = encoded.index(context) + 16
            encoded[position:position + 4] = patch.replacement
            if decoded is not None:
                decoded[patch_offset:patch_offset + 4] = patch.replacement
                encoded[-4:] = struct.pack(">I", zlib.adler32(decoded))
                if zlib.decompress(encoded) != decoded:
                    raise ValueError(f"{model} IOC patch changed unrelated data")
            stream.seek(patch.block_offset)
            stream.write(encoded)
        rootfs.replace_file(output, squashfs, "/cramfs.img", "0100644")


def build_waveform(name: bytes = b"") -> bytes:
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
    if name:
        # The vendor module selects panel timing and color filtering by
        # waveform name: ED070 for the Era, EC078 for the InkPad Color.
        if len(name) > 255 or 0x301 + len(name) > len(waveform):
            raise ValueError("PocketBook B288 waveform name is too long")
        waveform[0x1c:0x1f] = (0x300).to_bytes(3, "little")
        waveform[0x300:0x301 + len(name)] = bytes((len(name),)) + name
    struct.pack_into("<I", waveform, 0, 0)
    struct.pack_into("<I", waveform, 4, len(waveform))
    waveform[0x1f] = sum(waveform[:0x1f]) & 255
    waveform[0x2f] = sum(waveform[0x20:0x2f]) & 255
    struct.pack_into("<I", waveform, 0, zlib.crc32(waveform))
    return bytes(waveform)


def build(output: Path, artifacts: dict[str, Path], *, model: str) -> None:
    board = BOARDS[model]
    partitions = board_partitions(board)
    validate_firmware(artifacts, model=model)
    prepared = output.with_name("prepared-rootfs.img")
    prepare_root(artifacts["rootfs"], prepared, board, applications=artifacts["applications"])
    applications = artifacts["applications"]
    if model in IOC_PATCHES:
        applications = output.with_name("prepared-applications.img")
        prepare_ioc_applications(artifacts["applications"], applications, model=model,
                                 patch=IOC_PATCHES[model], maximum_size=partitions[4][3])
    secure = output.with_name("secure.img")
    with secure.open("wb") as stream:
        stream.truncate(partitions[5][3])
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
    # responses return twelve ASCII zeroes; other profiles return an empty serial.
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
        write_partition_tables(disk, partitions)
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
                              if "waveform" in artifacts else build_waveform(board.waveform_name)),
        }
        write_bootfs(disk, files)
        for image, part in ((prepared, 3), (applications, 4), (secure, 5)):
            disk.seek(partitions[part][2])
            with image.open("rb") as source:
                shutil.copyfileobj(source, disk)
        write_userstore(disk, start=partitions[-1][2] // 512,
                         end=DISK_SIZE // 512, label=b"PocketBook ")
