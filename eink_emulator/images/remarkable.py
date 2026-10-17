"""Import reMarkable SWU firmware and assemble its eMMC storage."""
from __future__ import annotations

import gzip
import shutil
import struct
import subprocess
import tarfile
import tempfile
from pathlib import Path

from . import rootfs
from .common import atomic_output

MIB = 1024**2
DISK_SIZE = 4 * 1024**3
ROOT_SIZE = 512 * MIB
# Preserve the stock partition numbers and dual system slots. Updates omit
# the partition table, environment volume and writable home filesystem.
PARTITIONS = (
    (1, 4 * MIB, 16 * MIB, 0x06),
    (2, 20 * MIB, ROOT_SIZE, 0x83),
    (3, 532 * MIB, ROOT_SIZE, 0x83),
    (5, 1045 * MIB, 16 * MIB, 0x83),
    (6, 1062 * MIB, 16 * MIB, 0x83),
    (7, 1079 * MIB, DISK_SIZE - 1079 * MIB, 0x83),
)


def dump_file(image: Path, guest: str, target: Path) -> None:
    rootfs.run(image, f'dump {guest} "{target}"')
    if not target.is_file() or not target.stat().st_size:
        raise ValueError(f"reMarkable firmware is missing {guest}")


def validate_firmware(artifacts: dict[str, Path]) -> None:
    data = artifacts["bootloader"].read_bytes()
    if len(data) < 0x2c or struct.unpack_from("<I", data)[0] != 0x402000d1:
        raise ValueError("reMarkable requires its vendor U-Boot IVT image")
    with artifacts["rootfs"].open("rb") as stream:
        stream.seek(rootfs.EXT_MAGIC_OFFSET)
        if stream.read(2) != b"\x53\xef":
            raise ValueError("reMarkable rootfs must be an ext filesystem")
    if artifacts["rootfs"].stat().st_size > ROOT_SIZE:
        raise ValueError("reMarkable rootfs exceeds its system partition")


def import_update(package: Path, destination: Path, *, model: str = "remarkable1") -> dict[str, Path]:
    """Read the SWU CPIO container without running its installer scripts."""
    if not package.is_file():
        raise SystemExit(f"firmware package does not exist: {package}")
    if destination.exists():
        raise SystemExit(f"firmware destination already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    generation = {"remarkable1": 1, "remarkable2": 2}[model]
    product = f"rm{generation}"
    suffix = ".ext4.gz"
    with tempfile.TemporaryDirectory(prefix=f".rm{generation}-import-", dir=destination.parent) as temporary:
        work = Path(temporary)
        prepared = work / "prepared"
        prepared.mkdir()
        manifest = None
        payload = None
        with package.open("rb") as source:
            while True:
                header = source.read(110)
                if len(header) != 110 or header[:6] not in (b"070701", b"070702"):
                    raise ValueError("reMarkable update must be a complete SWU/CPIO archive")
                fields = [int(header[i:i + 8], 16) for i in range(6, 110, 8)]
                size, name_size = fields[6], fields[11]
                if not 1 <= name_size <= 4096:
                    raise ValueError("reMarkable update has an invalid member name")
                name = source.read(name_size)
                if len(name) != name_size or name[-1] != 0:
                    raise ValueError("reMarkable update has a truncated member name")
                name = name[:-1].decode("utf-8")
                source.seek((-source.tell()) % 4, 1)
                if name == "TRAILER!!!":
                    break
                if source.tell() + size > package.stat().st_size:
                    raise ValueError("reMarkable update has a truncated member")
                if name == "sw-description":
                    if manifest is not None:
                        raise ValueError("reMarkable update repeats its manifest")
                    manifest = source.read(size)
                elif name.endswith(f"-{product}-public{suffix}"):
                    if payload is not None or fields[1] & 0o170000 != 0o100000:
                        raise ValueError("reMarkable update has an invalid root filesystem member")
                    payload = work / "rootfs.gz"
                    with payload.open("wb") as target:
                        remaining = size
                        while remaining:
                            block = source.read(min(remaining, 8 * MIB))
                            if not block:
                                raise ValueError("reMarkable root filesystem is truncated")
                            target.write(block)
                            remaining -= len(block)
                else:
                    source.seek(size, 1)
                source.seek((-source.tell()) % 4, 1)
        manifest_product = f"reMarkable{generation}".encode()
        if manifest is None or manifest_product not in manifest or payload is None:
            raise ValueError(f"SWU does not contain reMarkable {generation} firmware")
        image = prepared / "rootfs.img"
        with gzip.open(payload, "rb") as source, image.open("wb") as target:
            shutil.copyfileobj(source, target)
        dump_file(image, "/boot/u-boot.imx", prepared / "u-boot.imx")
        installed = {"rootfs": image, "bootloader": prepared / "u-boot.imx"}
        validate_firmware(installed)
        prepared.replace(destination)
    return {role: destination / path.name for role, path in installed.items()}


def write_bootfs(disk, files: dict[str, bytes], partitions=PARTITIONS) -> None:
    """FAT16 factory volume with waveform files and Xochitl's setup switch."""
    _, start, size, _ = partitions[0]
    sectors, spc, root_entries = size // 512, 4, 512
    fat_sectors = ((sectors // spc + 2) * 2 + 511) // 512
    boot = bytearray(512)
    boot[:11] = b"\xeb\x3c\x90MSDOS5.0"
    struct.pack_into("<HBHBHHBHHHII", boot, 11, 512, spc, 1, 2, root_entries,
                     sectors if sectors < 65536 else 0, 0xf8, fat_sectors,
                     63, 255, start // 512, sectors if sectors >= 65536 else 0)
    boot[36:39] = b"\x80\0\x29"
    struct.pack_into("<I", boot, 39, 0x524d3031)
    boot[43:54] = b"RMBOOT     "
    boot[54:62] = b"FAT16   "
    boot[510:] = b"\x55\xaa"
    disk.seek(start)
    disk.write(boot)
    fat = bytearray(fat_sectors * 512)
    struct.pack_into("<HH", fat, 0, 0xfff8, 0xffff)
    cluster_size = spc * 512
    root_start = start + (1 + 2 * fat_sectors) * 512
    data_start = root_start + root_entries * 32
    next_cluster = 2

    def allocate(contents: bytes) -> int:
        nonlocal next_cluster
        count = max(1, (len(contents) + cluster_size - 1) // cluster_size)
        first = next_cluster
        next_cluster += count
        if data_start + (next_cluster - 2) * cluster_size > start + size:
            raise ValueError("reMarkable factory files exceed the FAT volume")
        for c in range(first, next_cluster):
            struct.pack_into("<H", fat, c * 2, c + 1 if c + 1 < next_cluster else 0xffff)
        disk.seek(data_start + (first - 2) * cluster_size)
        disk.write(contents)
        return first

    def entry(alias: bytes, cluster: int, length: int, attr=0x20) -> bytes:
        result = bytearray(32)
        result[:11], result[11] = alias, attr
        struct.pack_into("<HI", result, 26, cluster, length)
        return bytes(result)

    def long_entry(name: str, alias: bytes, cluster: int, length: int) -> bytes:
        checksum = 0
        for char in alias:
            checksum = (((checksum & 1) << 7) + (checksum >> 1) + char) & 0xff
        encoded = (name + "\0").encode("utf-16le")
        count = (len(encoded) + 25) // 26
        encoded = encoded.ljust(count * 26, b"\xff")
        result = bytearray()
        for i in range(count, 0, -1):
            part = encoded[(i - 1) * 26:i * 26]
            record = bytearray(32)
            record[0], record[11], record[13] = i | (0x40 if i == count else 0), 0x0f, checksum
            record[1:11], record[14:26], record[28:32] = part[:10], part[10:22], part[22:]
            result.extend(record)
        return bytes(result) + entry(alias, cluster, length)

    directory = bytearray()
    for i, (name, contents) in enumerate(files.items()):
        alias = b"WAVEFORMBIN" if name == "waveform.bin" else f"WF{i:06d}WBF".encode()
        directory.extend(long_entry(name, alias, allocate(contents), len(contents)))
    # Setup is a factory flag; the user settings only select an onboarding page.
    settings = b"[General]\nSetup=false\n"
    settings_cluster = allocate(settings)
    settings_dir = allocate(b"")
    children = entry(b".          ", settings_dir, 0, 0x10) + entry(b"..         ", 0, 0, 0x10)
    children += long_entry("xochitl.conf", b"XOCHITL CON", settings_cluster, len(settings))
    disk.seek(data_start + (settings_dir - 2) * cluster_size)
    disk.write(children)
    directory.extend(entry(b"XOCHITL    ", settings_dir, 0, 0x10))
    if len(directory) > root_entries * 32:
        raise ValueError("Too many reMarkable factory files")
    disk.seek(root_start)
    disk.write(directory)
    for i in range(2):
        disk.seek(start + (1 + i * fat_sectors) * 512)
        disk.write(fat)


def partition_entry(kind: int, start: int, size: int) -> bytes:
    return struct.pack("<B3sB3sII", 0, b"\xfe\xff\xff", kind,
                       b"\xfe\xff\xff", start // 512, size // 512)


def write_partition_table(disk, partitions=PARTITIONS, disk_size=DISK_SIZE) -> None:
    table = bytearray(512)
    extended = any(number > 4 for number, *_ in partitions)
    extended_start = partitions[3][1] - MIB
    primary = partitions[:3] if extended else partitions
    for i, (_, start, size, kind) in enumerate(primary):
        table[446 + i * 16:462 + i * 16] = partition_entry(kind, start, size)
    if extended:
        table[494:510] = partition_entry(0x0f, extended_start, disk_size - extended_start)
    table[510:] = b"\x55\xaa"
    disk.seek(0)
    disk.write(table)
    for i, (_, start, size, kind) in enumerate(partitions[3:] if extended else ()):
        ebr_start = start - MIB
        ebr = bytearray(512)
        ebr[446:462] = partition_entry(kind, MIB, size)
        if i < 2:
            following = partitions[i + 4][1] - MIB
            ebr[462:478] = partition_entry(0x0f, following - extended_start,
                                           disk_size - following)
        ebr[510:] = b"\x55\xaa"
        disk.seek(ebr_start)
        disk.write(ebr)


def build(output: Path, artifacts: dict[str, Path], *, model: str = "remarkable1") -> None:
    validate_firmware(artifacts)
    rm2 = model == "remarkable2"
    disk_size = 8 * 1024**3 if rm2 else DISK_SIZE
    partitions = tuple(
        (number, start, disk_size - start if number == 7 else size, kind)
        for number, start, size, kind in PARTITIONS
    )
    if rm2:
        home_start = 1044 * MIB
        partitions = PARTITIONS[:3] + ((4, home_start, disk_size - home_start, 0x83),)
    prepared = output.with_name("prepared-rootfs.img")
    rootfs.copy_source(artifacts["rootfs"], prepared, maximum_size=ROOT_SIZE)
    with prepared.open("r+b") as stream:
        stream.truncate(ROOT_SIZE)
    subprocess.run([str(rootfs.find_debugfs().with_name("resize2fs")), str(prepared)],
                    check=True, stdout=subprocess.DEVNULL)
    def serial_login(contents: str) -> str:
        command = "ExecStart=-/sbin/agetty -8 -L"
        if contents.count(command) != 1:
            raise ValueError("Unexpected reMarkable serial getty configuration")
        return contents.replace(command, "ExecStart=-/sbin/agetty --autologin root -8 -L")

    rootfs.transform_file(prepared, "/usr/lib/systemd/system/serial-getty@.service",
                           "0100644", serial_login)
    if rm2:
        # Offline boards have no network interface for these socket units.
        # Their device dependencies otherwise delay basic.target for 90 s.
        rootfs.run_many(prepared, [
            f"symlink /etc/systemd/system/{unit} /dev/null"
            for unit in ("dropbear-usb0.socket", "dropbear-usb1.socket",
                         "dropbear-wlan.socket", "wpa_supplicant.service")
        ], writable=True)
    factory_files = {}
    if rm2:
        collection = output.with_name("waveforms.tar.gz")
        dump_file(prepared, "/usr/share/remarkable/waveforms.tar.gz", collection)
        # The emulated ED103TC2M1 panel uses the corresponding factory WBF.
        # Real devices keep one selected waveform, rather than the OTA bundle.
        waveform_name = "320_R259_AFAB21_ED103TC2M1_TC.wbf"
        with tarfile.open(collection) as archive:
            for member in archive:
                if member.isfile() and Path(member.name).name == waveform_name:
                    factory_files[Path(member.name).name] = archive.extractfile(member).read()
        if not factory_files:
            raise ValueError(f"reMarkable 2 firmware is missing {waveform_name}")
    else:
        waveform = output.with_name("waveform.bin")
        dump_file(prepared, "/lib/firmware/imx/epdc/epdc_ES103CS1.fw", waveform)
        factory_files["waveform.bin"] = waveform.read_bytes()
    with atomic_output(output) as staging, staging.open("w+b") as disk:
        disk.truncate(disk_size)
        write_partition_table(disk, partitions, disk_size)
        disk.seek(1024)
        disk.write(artifacts["bootloader"].read_bytes())
        write_bootfs(disk, factory_files, partitions)
        for i in (1, 2):
            disk.seek(partitions[i][1])
            with prepared.open("rb") as source:
                while block := source.read(8 * MIB):
                    if block.strip(b"\0"):
                        disk.write(block)
                    else:
                        disk.seek(len(block), 1)
        for number, start, size, _ in partitions[3:]:
            image = output.with_name(f"partition-{number}.img")
            with image.open("wb") as stream:
                stream.truncate(size)
            subprocess.run([
                str(rootfs.find_debugfs().with_name("mke2fs")), "-q", "-t", "ext4",
                "-F", "-O", "none,has_journal,filetype,extents,sparse_super,large_file,uninit_bg,dir_nlink,extra_isize",
                "-L", "home" if number == partitions[-1][0] else f"reserved{number}", str(image),
            ], check=True)
            disk.seek(start)
            with image.open("rb") as source:
                while block := source.read(8 * MIB):
                    if block.strip(b"\0"):
                        disk.write(block)
                    else:
                        disk.seek(len(block), 1)
