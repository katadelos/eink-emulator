"""Build a compact eMMC image for KT4 (Jaeger)."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from . import bellatrix, imx6_mmc

MIB = 1024**2
DISK_SIZE = 2 * 1024**3

# Jaeger U-Boot boots p1 by name and recovery/p2 carries waveforms.
# The shipped initramfs and rootfs use p3/p6/p7/p8/p9/p10 directly.
# lastk sits near the end of the first 16 MiB of miscdata; retain that
# reserved space and a full RAM-sized snapshot region.
JAEGER_PARTITIONS = [
    ("kernel", 32 * MIB),
    ("recovery", 8 * MIB),
    ("keys", 8 * MIB),
    ("diags", 32 * MIB),
    ("reserved", 16 * MIB),
    ("miscdata", 64 * MIB),
    ("snapshot", 512 * MIB),
    ("rootfs", 512 * MIB),
    ("varlocal", 64 * MIB),
]


def build(output: Path, *, boot_image: Path, rootfs_image: Path) -> None:
    layout = bellatrix.create_image(
        output, DISK_SIZE, partitions=JAEGER_PARTITIONS, namespace="jaeger"
    )
    bellatrix.write_partition(output, layout, "kernel", boot_image)
    bellatrix.write_partition(output, layout, "rootfs", rootfs_image)
    # Recovery mounts p2 directly as VFAT, using the same waveform_to_use
    # directory as the older i.MX Kindle store. The kernel ships a default
    # waveform for the virtual panel; no per-panel download is needed.
    with output.open("r+b") as image:
        imx6_mmc.write_waveform_store(image, layout["recovery"][0] * 512, None)
    with tempfile.TemporaryDirectory(prefix="eink-jaeger-") as directory:
        for name, label in (("keys", "keys"), ("varlocal", "LocalVars")):
            filesystem = Path(directory) / f"{name}.img"
            with filesystem.open("wb") as image:
                image.truncate(layout[name][1] * 512)
            subprocess.run([
                str(bellatrix.find_tool("mke2fs")), "-q", "-t", "ext3",
                "-F", "-L", label, str(filesystem),
            ], check=True)
            bellatrix.write_partition(output, layout, name, filesystem)
    bellatrix.create_vfat_userstore(output, layout)
