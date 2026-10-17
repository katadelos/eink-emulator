"""Import MT8113 updates and assemble Tolino development storage.

The update supplies U-Boot, Linux and the root filesystem. Factory calibration
partitions are absent; the hardware configuration and waveform below are
explicit emulator fixtures, not a recovered physical-device image.
"""
from __future__ import annotations

import gzip
import hashlib
import re
import shutil
import struct
import subprocess
import tarfile
import tempfile
import uuid
import zipfile
import zlib
from pathlib import Path
from typing import BinaryIO

from . import bellatrix, bellatrix_waveform, rootfs
from .common import atomic_output
from .forma import write_userstore
from ..ssh import ensure_login_key

MIB = 1024**2
DISK_SIZE = 4 * 1024**3
ROOTFS_SIZE = 1024 * MIB
ROOT_UUID = uuid.UUID("936e1662-2b63-435d-859d-1b9e5a838335")
IMPORT_FILES = {
    "bootloader": ("uboot.img", "uboot.img"),
    "rootfs": ("rootfs.img", "rootfs.img"),
    "bl2": ("bl2.img", "bl2.img"),
    "tee": ("tee.img", "tee.img"),
}
UPDATE_SOC_DIRECTORY = "aud8113tp1/"
ZSTD_MAGIC = b"\x28\xb5\x2f\xfd"
SPA_FIELDS = {
    1: 12,   # No page-button keypad
    7: 14,   # Cypress CYTT21X touch
    9: 30, 10: 6, # MT8113T + SY7636; 6-inch panel
    11: 0,   # No accelerometer
    14: 14,  # PR-284983N 1500 mAh battery
    16: 3,   # 512 MiB RAM
    31: 5,   # 1448 x 1072 panel timing
}
PROFILES = {
    "monza": {
        "model": "tolino-vision-color",
        "colour": True,
        "fields": {
            0: 111,  # E70T00 (E70T04 PCB family)
            1: 26,   # Page-up/page-down buttons
            7: 19,   # EKTH6 touch
            9: 31, 10: 36, # MT8113T + JD9930; 7-inch panel
            11: 6,   # KX122 accelerometer
            14: 26,  # EVE188595QH 2050 mAh battery
            16: 4,   # 1 GiB RAM
            31: 16,  # 1680 x 1264 panel timing
            64: 8, 72: 2, 76: 1, # CFA enabled, Kaleido 3, rotation 0
        },
    },
    "spa-bw": {
        "model": "tolino-shine-5",
        "colour": False,
        "fields": SPA_FIELDS | {0: 113}, # E60T00/E60T04
    },
    "spa-colour": {
        "model": "tolino-shine-color",
        "colour": True,
        "fields": SPA_FIELDS | {0: 113, 64: 8, 72: 2, 76: 1},
    },
    "spa-tpv-bw": {
        "model": "tolino-shine-5-tpv",
        "colour": False,
        # E60V00 uses the DT's LM3697 main backlight, not the NTX LM3630
        # calibration-table route. The stock hwcfg utility has no LM3697 enum.
        "fields": SPA_FIELDS | {0: 160, 32: 0, 38: 0, 45: 0},
    },
}

# The public update names partitions, while stock fstab and U-Boot require
# waveform=p8, system_a=p10, recovery=p11, userdata=p12. Factory sector counts
# are not published; retain the shared MT8113 boot-area offsets and allocate
# space for the 1 GiB rootfs and an unpopulated recovery slot.
PARTITIONS = (
    ("bl2", 1024, 1024), ("UBOOT", 2048, 2048),
    ("nvram", 36864, 2048), ("boot_a", 38912, 65536),
    ("tee_a", 104448, 8192), ("hwcfg", 112640, 2048),
    ("ntxfw", 114688, 2048), ("waveform", 116736, 20480),
    ("vendor", 137216, 40960), ("system_a", 198656, ROOTFS_SIZE // 512),
    ("recovery", 198656 + ROOTFS_SIZE // 512, ROOTFS_SIZE // 512),
)
USER_START = 198656 + 2 * ROOTFS_SIZE // 512


def import_files(profile: str) -> dict[str, tuple[str, str]]:
    if profile not in PROFILES:
        raise ValueError(f"unsupported Tolino image profile: {profile}")
    return IMPORT_FILES | {"boot_image": (f"{profile}/kernel.img", "kernel.img")}


def member_names(relative: str) -> tuple[str, ...]:
    # 5.13 moved the shared boot files into the SoC's directory.
    return (relative, UPDATE_SOC_DIRECTORY + relative)


def read_manifest(contents: bytes) -> dict[str, str]:
    """Parse the update's zstd-compressed sha2-256sums."""
    if contents.startswith(ZSTD_MAGIC):
        contents = subprocess.run(
            [shutil.which("zstd") or "zstd", "--decompress", "--stdout", "--quiet"],
            input=contents, check=True, capture_output=True,
        ).stdout
    manifest = {}
    for line in contents.decode().splitlines():
        digest, _, name = line.partition("\t")
        if name:
            manifest[name.removeprefix("./")] = digest.lower()
    return manifest


def verify_manifest(manifest: dict[str, str], digests: dict[str, str]) -> None:
    for name, digest in digests.items():
        if manifest.get(name) != digest:
            raise SystemExit(f"Tolino update {name} does not match its sha2-256sums entry")


def update_directory_files(
    directory: Path, files: dict[str, tuple[str, str]],
) -> dict[str, Path]:
    sources: dict[str, Path] = {}
    digests: dict[str, str] = {}
    for relative, _ in files.values():
        found = [name for name in member_names(relative) if (directory / name).is_file()]
        if len(found) != 1:
            raise SystemExit(f"Tolino update is missing {relative}")
        sources[relative] = directory / found[0]
        digest = hashlib.sha256()
        with sources[relative].open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        digests[found[0]] = digest.hexdigest()
    if (directory / "sha2-256sums").is_file():
        verify_manifest(read_manifest((directory / "sha2-256sums").read_bytes()), digests)
    return sources


def open_update(package: Path) -> BinaryIO:
    """Open an update tar, unwrapping the single-member zip Kobo serves."""
    if zipfile.is_zipfile(package):
        archive = zipfile.ZipFile(package)
        if archive.namelist() != ["update.tar"]:
            raise SystemExit("Tolino update zip does not contain only update.tar")
        return archive.open("update.tar")
    return package.open("rb")


def extract_update(
    package: Path, files: dict[str, tuple[str, str]], directory: Path,
) -> dict[str, Path]:
    """Copy the named regular files out of an update and verify them."""
    wanted = {name: relative for relative, _ in files.values() for name in member_names(relative)}
    sources: dict[str, Path] = {}
    digests: dict[str, str] = {}
    manifest = None
    # Stream the archive once; never extract archive paths, symlinks, device
    # nodes or the vendor's executable scripts.
    with open_update(package) as stream, tarfile.open(fileobj=stream, mode="r|") as archive:
        for member in archive:
            name = member.name.removeprefix("./")
            if not member.isfile():
                continue
            if name == "sha2-256sums":
                manifest = read_manifest(archive.extractfile(member).read())
                continue
            relative = wanted.get(name)
            if relative is None:
                continue
            if relative in sources:
                raise SystemExit(f"Tolino update contains more than one {relative}")
            target = directory / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            digest = hashlib.sha256()
            with archive.extractfile(member) as source, target.open("wb") as output:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    digest.update(chunk)
                    output.write(chunk)
            sources[relative] = target
            digests[name] = digest.hexdigest()
    for relative, _ in files.values():
        if relative not in sources:
            raise SystemExit(f"Tolino update is missing {relative}")
    if manifest is None:
        raise SystemExit("Tolino update is missing sha2-256sums")
    verify_manifest(manifest, digests)
    return sources


def import_update(package: Path, destination: Path, *, profile: str) -> dict[str, Path]:
    """Install decompressed stock inputs from an update directory, tar or zip."""
    files = import_files(profile)
    zstd = shutil.which("zstd")
    if not zstd:
        raise SystemExit("zstd is required to import Tolino firmware")
    if not package.exists():
        raise SystemExit(f"firmware package does not exist: {package}")
    if destination.exists():
        raise SystemExit(f"firmware destination already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=f".{destination.name}-import-", dir=destination.parent,
    ) as temporary:
        workspace = Path(temporary)
        prepared = workspace / "prepared"
        prepared.mkdir()
        if package.is_dir():
            sources = update_directory_files(package, files)
        else:
            sources = extract_update(package, files, workspace / "compressed")
        for relative, output_name in files.values():
            source = sources[relative]
            subprocess.run([
                zstd, "--decompress", "--quiet", "--sparse", str(source),
                "-o", str(prepared / output_name),
            ], check=True)
        for name in ("uboot.img", "kernel.img", "tee.img"):
            image = prepared / name
            with image.open("rb") as stream:
                header = stream.read(8)
            if len(header) != 8:
                raise SystemExit(f"{name} is truncated")
            magic, size = struct.unpack(">II", header)
            if magic != 0xD00DFEED or size > image.stat().st_size:
                raise SystemExit(f"{name} is not a complete FIT image")
        with (prepared / "rootfs.img").open("rb") as image:
            image.seek(rootfs.EXT_MAGIC_OFFSET)
            if image.read(2) != b"\x53\xef":
                raise SystemExit("Tolino rootfs is not an ext filesystem")
        prepared.replace(destination)
    return {role: destination / output for role, (_, output) in files.items()}


def prepare_root(source: Path, output: Path, *, profile: str) -> None:
    """Prepare a disposable stock rootfs copy for console and keyed USB SSH."""
    rootfs.copy_source(source, output, maximum_size=ROOTFS_SIZE)
    rootfs.transform_file(output, "/etc/shadow", "0100600", rootfs.blank_root_password)
    rootfs.install_overrides(image=output, group="tolino", replacements={
        "/etc/init.d/qemu-usb-network": ("etc/init.d/qemu-usb-network", "0100755"),
    })

    def startup(contents: str) -> str:
        needle = "/usr/local/Kobo/hindenburg &"
        if contents.count(needle) != 1:
            raise ValueError("Unrecognized Tolino rc.local Hindenburg startup")
        return contents.replace(needle, "/etc/init.d/qemu-usb-network\n" + needle)

    def ssh_config(contents: str) -> str:
        contents, count = re.subn(
            r"(?m)^AuthorizedKeysFile\s+.*$",
            "AuthorizedKeysFile /etc/eink-ssh/authorized_keys", contents,
        )
        if count != 1:
            raise ValueError("Unrecognized Tolino SSH authorized-keys configuration")
        contents = re.sub(r"(?m)^#?PasswordAuthentication\s+.*$",
                          "PasswordAuthentication no", contents)
        return contents

    def ssh_startup(contents: str) -> str:
        guard = "if [ -e /mnt/onboard/.kobo/ssh-enabled ] || [ -e /etc/dev-image ]; then"
        if contents.count(guard) != 1:
            raise ValueError("Unrecognized Tolino SSH enablement guard")
        return contents.replace(guard, "if [ -s /etc/eink-ssh/authorized_keys ]; then")

    def display_startup(contents: str) -> str:
        needle = "/usr/local/Kobo/pickel init"
        if contents.count(needle) != 1:
            raise ValueError("Unrecognized Tolino display initialization")
        # The update omits the physical panel's CFA calibration LUT. Select
        # the stock driver's built-in conversion for its ABGR32 framebuffer.
        return contents.replace(needle, needle + (
            "\n# QEMU: use uncalibrated built-in CFA conversion.\n"
            "printf 'NTX_SF\\n' > /sys/devices/platform/14000000.hwtcon/cfa_mode"
        ))

    rootfs.transform_file(output, "/etc/rc.local", "0100755", startup)
    if PROFILES[profile]["colour"]:
        rootfs.transform_file(output, "/etc/init.d/display-init.sh", "0100755", display_startup)
    rootfs.transform_file(output, "/etc/ssh/sshd_config", "0100600", ssh_config)
    rootfs.transform_file(output, "/etc/default/ssh", "0100644", ssh_startup)
    key = ensure_login_key()
    rootfs.run_many(output, [
        "mkdir /etc/eink-ssh",
        "set_inode_field /etc/eink-ssh mode 040700",
        f'write "{key}" /etc/eink-ssh/authorized_keys',
        "set_inode_field /etc/eink-ssh/authorized_keys mode 0100600",
        "set_inode_field /etc/eink-ssh/authorized_keys uid 0",
        "set_inode_field /etc/eink-ssh/authorized_keys gid 0",
    ], writable=True)


def ntx_bin(payload: bytes) -> bytes:
    """Wrap an NTX payload in the stock 512-byte storage header."""
    header = bytearray(512)
    header[496:500] = b"\xff\xf5\xaf\xff"
    struct.pack_into("<I", header, 504, len(payload))
    return header + payload


def hardware_config(*, profile: str) -> bytes:
    """Synthetic board identity using stock ntx_hwconfig enums."""
    payload = bytearray(110)
    payload[:16] = b"HW CONFIG v3.8\0" + bytes([77])
    fields = {
        4: 17, 5: 11,  # MT8113T Wi-Fi / Bluetooth
        8: 3, 12: 2,   # Capacitive touch; no auxiliary MCU
        13: 33, 17: 2, # Tolino branding; eMMC
        19: 2, 20: 25, # ext4, p10 system / p11 recovery
        27: 16, 28: 1, 29: 12, # MT8113T, customer UI, LPDDR4
        32: 1,         # Frontlight present
        38: 4, 44: 6, 45: 2, 46: 6, # LM3630 lighting, BD71828 PMIC/RTC
    } | PROFILES[profile]["fields"]
    for field, value in fields.items():
        payload[16 + field] = value
    image = bytearray(4096)
    image[:512 + len(payload)] = ntx_bin(payload)
    # Deliberately synthetic identity; no device-specific secret or calibration.
    serial = b"SN-TQEMU0000000001"
    image[2048:2048 + len(serial)] = serial
    return bytes(image)


def empty_ntx_firmware() -> bytes:
    """A complete NTX container with no factory calibration entries."""
    header = struct.pack("<10s36sH4B", b"{NTXFW-->",
                         b"SYNTHETIC_EMPTY_EMULATOR", 0, 0, 0, 0, 0)
    return ntx_bin(header + b"<--NTXFW}\0")


def write_gpt(disk, *, profile: str) -> dict[str, tuple[int, int]]:
    last = DISK_SIZE // 512 - 1
    partitions = (*PARTITIONS, ("userdata", USER_START, last - 33 - USER_START + 1))
    entries = bytearray(128 * 128)
    for index, (name, start, count) in enumerate(partitions):
        identity = ROOT_UUID if name == "system_a" else uuid.uuid5(
            uuid.NAMESPACE_DNS, f"eink-emulator-{PROFILES[profile]['model']}-{name}",
        )
        struct.pack_into("<16s16sQQQ72s", entries, index * 128,
                         bellatrix.LINUX_FS.bytes_le, identity.bytes_le,
                         start, start + count - 1, 0, name.encode("utf-16-le"))
    mbr = bytearray(512)
    mbr[446:462] = struct.pack("<B3sB3sII", 0, b"\0\x02\0", 0xEE,
                               b"\xff\xff\xff", 1, last)
    mbr[510:] = b"\x55\xaa"
    disk.seek(0)
    disk.write(mbr)
    disk_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"eink-emulator-{PROFILES[profile]['model']}")
    for current, backup, table_at in ((1, last, 2), (last, 1, last - 32)):
        disk.seek(current * 512)
        disk.write(bellatrix.make_header(current, backup, table_at, 34,
                                        last - 33, disk_id, zlib.crc32(entries)))
        disk.seek(table_at * 512)
        disk.write(entries)
    return {name: (start, count) for name, start, count in partitions}


def build_waveform(output: Path, *, profile: str) -> None:
    """Create the mounted HWTCON waveform fixture; no panel calibration."""
    waveform = bytearray(bellatrix_waveform.build_waveform("elipsa2e"))
    name = f"SYNTHETIC_{PROFILES[profile]['model'].upper().replace('-', '_')}_EMULATOR_ONLY"
    waveform[:0x50] = name.encode("ascii").ljust(0x50, b"\0")
    # The shared driver uses 0x72 for CFA (including GCC16/GLRC16) and 0x58
    # for monochrome panels; Elipsa's 0x59 has no entry in its mode table.
    waveform[0x50] = 0x72 if PROFILES[profile]["colour"] else 0x58
    with tempfile.TemporaryDirectory(prefix="eink-tolino-waveform-") as temporary:
        seed = Path(temporary)
        (seed / "wf_lut.gz").write_bytes(gzip.compress(waveform, mtime=0))
        with output.open("wb") as image:
            image.truncate(10 * MIB)
        subprocess.run([
            str(bellatrix.find_tool("mke2fs")), "-q", "-F", "-t", "ext4",
            "-O", "^metadata_csum,^orphan_file", "-d", str(seed), str(output),
        ], check=True)
    rootfs.run_many(output, [
        "set_inode_field /wf_lut.gz uid 0",
        "set_inode_field /wf_lut.gz gid 0",
        "set_inode_field /wf_lut.gz mode 0100644",
    ], writable=True)


def build(output: Path, artifacts: dict[str, Path], *, profile: str) -> None:
    if profile not in PROFILES:
        raise ValueError(f"unsupported Tolino image profile: {profile}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".tolino-prepared-", dir=output.parent) as temporary:
        directory = Path(temporary)
        prepared, waveform = directory / "rootfs.img", directory / "waveform.img"
        prepare_root(artifacts["rootfs"], prepared, profile=profile)
        build_waveform(waveform, profile=profile)
        with atomic_output(output) as staging, staging.open("w+b") as disk:
            disk.truncate(DISK_SIZE)
            layout = write_gpt(disk, profile=profile)
            sources = {
                "UBOOT": artifacts["bootloader"], "boot_a": artifacts["boot_image"],
                "bl2": artifacts["bl2"], "tee_a": artifacts["tee"],
                "system_a": prepared, "waveform": waveform,
            }
            for partition, source in sources.items():
                start, sectors = layout[partition]
                if source.stat().st_size > sectors * 512:
                    raise ValueError(f"{source.name} exceeds its Tolino {partition} partition")
                bellatrix.copy_sparse(source, disk, start * 512)
            disk.seek(layout["hwcfg"][0] * 512)
            disk.write(hardware_config(profile=profile))
            disk.seek(layout["ntxfw"][0] * 512)
            # A valid empty NTX firmware table declares that factory light and
            # panel calibration tables are unavailable in the public update.
            disk.write(empty_ntx_firmware())
            write_userstore(disk, start=USER_START, end=DISK_SIZE // 512 - 33)
