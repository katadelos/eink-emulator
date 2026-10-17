"""Paper Pro development-mode eMMC and factory provisioning."""
from __future__ import annotations

import hashlib
import struct
import subprocess
import tempfile
from pathlib import Path

from . import bellatrix, rootfs
from .common import atomic_output

MIB = 1024**2
DISK_SIZE = 64 * 1024**3
ROOT_SIZE = 640 * MIB
PARTITIONS = [("data", 32 * MIB), ("root_a", ROOT_SIZE),
              ("root_b", ROOT_SIZE), ("swap", 1536 * MIB)]
PERSIST_OFFSET = 5186 * 512
PERSIST_SIZE = 3002 * 512


def validate_firmware(artifacts: dict[str, Path]) -> None:
    boot = artifacts["bootloader"].read_bytes()
    if len(boot) < 0x40 or struct.unpack_from("<I", boot)[0] != 0x412000d1:
        raise ValueError("Paper Pro requires its original imx-boot package")
    with artifacts["rootfs"].open("rb") as source:
        source.seek(rootfs.EXT_MAGIC_OFFSET)
        if source.read(2) != b"\x53\xef":
            raise ValueError("Paper Pro rootfs must be an ext filesystem")
    if artifacts["rootfs"].stat().st_size > ROOT_SIZE:
        raise ValueError("Paper Pro rootfs exceeds its system partition")
    if artifacts["factory"].stat().st_size != 4 * MIB:
        raise ValueError("Paper Pro factory image must be one eMMC boot partition")
    if artifacts["hwmon"].stat().st_size < 0x110:
        raise ValueError("Paper Pro hardware-monitor firmware is truncated")


def create_factory(output: Path) -> None:
    """Provision the boot1 persist filesystem and native devconfig table."""
    with tempfile.TemporaryDirectory(prefix="eink-ferrari-factory-") as temporary:
        work = Path(temporary)
        tree = work / "tree"
        tree.mkdir()
        persist = work / "persist.img"
        with persist.open("wb") as stream:
            stream.truncate(PERSIST_SIZE)
        subprocess.run([
            str(bellatrix.find_tool("mke2fs")), "-q", "-F", "-t", "ext4",
            "-b", "1024", "-O", "none,filetype,extents,sparse_super,large_file",
            "-L", "persist", "-d", str(tree), str(persist),
        ], check=True)
        config = bytearray(2048)
        struct.pack_into("<I", config, 0, 0xdeadc03f)
        # The stock lock-reset token provisions an unfused board in its
        # post-factory, unlocked state through the vendor bootloader.
        config[4:53] = b"R" * 49
        struct.pack_into("<I", config, 61, 1)
        for offset, serial in (
            (65, "BATQEMU00000000000000"), (105, "RM3QEMU00000000000000"),
            (145, "TC118AAB0CX5311000000000000 -0.50"),
            (185, "FERRARIQEMU0000000000"), (237, "ELANQEMU0000000000000"),
            (277, "FRONTQEMU000000000000"), (317, "WLCQEMU00000000000000"),
            (357, "remarkable-paper-pro"),
        ):
            encoded = serial.encode()
            config[offset:offset + len(encoded)] = encoded
        config[225:237] = bytes.fromhex("02524d03000102524d030002")
        # devconfig's on-device format requires this digest.
        config[2016:] = hashlib.sha256(config[:2016]).digest()
        with output.open("wb") as target:
            target.truncate(4 * MIB)
            target.seek(PERSIST_OFFSET)
            target.write(persist.read_bytes())
            target.seek(4 * MIB - len(config))
            target.write(config)


def build(output: Path, artifacts: dict[str, Path]) -> None:
    validate_firmware(artifacts)
    with tempfile.TemporaryDirectory(prefix="eink-ferrari-image-", dir=output.parent) as temporary:
        work = Path(temporary)
        prepared = work / "rootfs.img"
        rootfs.copy_source(artifacts["rootfs"], prepared, maximum_size=ROOT_SIZE)
        data_tree = work / "data-files"
        data_tree.mkdir()
        # Paper Pro's InsecureSettings uses /data, independently of the
        # factory persist filesystem and the user's onboarding page setting.
        (data_tree / "xochitl.conf").write_text("[General]\nSetup=false\n")

        def mounts(contents: str) -> str:
            encrypted = "/dev/mapper/home-encrypted-disk"
            if contents.count(encrypted) != 1:
                raise ValueError("Unexpected Paper Pro home mount")
            return contents.replace(encrypted, "/dev/mmcblk0p5")

        rootfs.transform_file(prepared, "/etc/fstab", "0100644", mounts)

        def login(contents: str) -> str:
            command = "ExecStart=-/sbin/agetty -8 -L"
            if contents.count(command) != 1:
                raise ValueError("Unexpected Paper Pro serial getty")
            return contents.replace(command, "ExecStart=-/sbin/agetty --autologin root -8 -L")

        rootfs.transform_file(prepared, "/usr/lib/systemd/system/serial-getty@.service",
                              "0100644", login)

        def keystore_dependency(contents: str) -> str:
            dependency = "After=data.mount dbus.socket"
            if contents.count(dependency) != 1:
                raise ValueError("Unexpected Paper Pro Xochitl dependencies")
            return contents.replace(dependency,
                dependency + " keystore.service\nRequires=keystore.service")

        rootfs.transform_file(prepared, "/usr/lib/systemd/system/xochitl.service",
                              "0100644", keystore_dependency)
        rootfs.run_many(prepared, [
            f"symlink /etc/systemd/system/{unit} /dev/null"
            for unit in ("homecryptor.service", "swapcryptor.service",
                         "growpart-home.service", "growfs-home.service",
                         "dropbear-usb0.socket", "dropbear-usb1.socket", "dropbear-wlan.socket",
                         "wpa_supplicant.service")
        ], writable=True)
        with atomic_output(output) as staging:
            layout = bellatrix.create_image(staging, DISK_SIZE, partitions=PARTITIONS,
                                             namespace="ferrari", user_partition="home")
            for name in ("root_a", "root_b"):
                bellatrix.write_partition(staging, layout, name, prepared)
            for name in ("data", "home"):
                image = work / f"{name}.img"
                with image.open("wb") as stream:
                    stream.truncate(layout[name][1] * 512)
                command = [
                    str(bellatrix.find_tool("mke2fs")), "-q", "-F", "-t", "ext4",
                    "-O", "none,has_journal,filetype,extents,sparse_super,large_file,uninit_bg,dir_nlink,extra_isize",
                    "-L", name,
                ]
                if name == "data":
                    command += ["-d", str(data_tree)]
                subprocess.run(command + [str(image)], check=True)
                bellatrix.write_partition(staging, layout, name, image)
