"""Build compact Duet and Zelda eMMC images from Oasis recovery packages."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from . import bellatrix, imx6_mmc

MIB = 1024**2
DISK_SIZE = 2 * 1024**3

# Zelda recovery addresses p1/p4/p5/p6/p7 directly. Keep its absolute
# hibernate region (0x10100000) outside the filesystems and its keys area
# at PERSISTENT_KEYS_MMC_OFFSET (0x13500000).
ZELDA_PARTITIONS = [
    ("kernel", 32 * MIB),
    ("tz", 276 * MIB),
    ("keys", 8 * MIB),
    ("wfm", 8 * MIB),
    ("system", 512 * MIB),
    ("cache", 64 * MIB),
]


def build_duet(output: Path, *, kernel: Path, rootfs: Path) -> None:
    imx6_mmc.build(output, kernel, rootfs, layout="duet")


def build_zelda(output: Path, *, boot_image: Path, rootfs: Path) -> None:
    layout = bellatrix.create_image(
        output, DISK_SIZE, partitions=ZELDA_PARTITIONS, namespace="zelda"
    )
    bellatrix.write_partition(output, layout, "kernel", boot_image)
    bellatrix.write_partition(output, layout, "system", rootfs)
    with tempfile.TemporaryDirectory(prefix="eink-zelda-") as directory:
        for name, label in (("keys", "keys"), ("cache", "LocalVars")):
            filesystem = Path(directory) / f"{name}.img"
            with filesystem.open("wb") as image:
                image.truncate(layout[name][1] * 512)
            subprocess.run([
                str(bellatrix.find_tool("mke2fs")), "-q", "-t", "ext3",
                "-F", "-L", label, str(filesystem),
            ], check=True)
            bellatrix.write_partition(output, layout, name, filesystem)
    bellatrix.create_vfat_userstore(output, layout)
