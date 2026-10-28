"""Compose Amaro storage from the stock PW7 firmware dump."""

from __future__ import annotations

import tempfile
from pathlib import Path

from . import bellatrix, bellatrix3, bellatrix_waveform, rootfs, scribe_waveform_partition

MIB = 1024**2
ROOTFS_SIZE = 1280 * MIB

# Amaro's platform_variables fixes keys=p3, pdata=p5, root=p8,
# local=p9 and user=p10. Persistent filesystems are created empty.
PARTITIONS = [
    ("kernel", 64 * MIB),
    ("wfm", 64 * MIB),
    ("keys", 16 * MIB),
    ("reserved0", 64 * MIB),
    ("pdata", 512 * MIB),
    ("snapshot", 1024 * MIB),
    ("miscdata", 512 * MIB),
    ("rootfs", ROOTFS_SIZE),
    ("varlocal", 512 * MIB),
]


def build(
    image: Path, *, boot_image: Path, rootfs_image: Path,
    size: int = 8 * 1024**3,
) -> None:
    for payload in (boot_image, rootfs_image):
        if not payload.is_file():
            raise ValueError(f"missing Amaro firmware: {payload}")
    if rootfs_image.stat().st_size != ROOTFS_SIZE:
        raise ValueError("Amaro requires the original 1280 MiB rootfs image")
    if size % 512:
        raise ValueError("Amaro disk must be sector-aligned")

    layout = bellatrix.create_image(
        image, size, partitions=PARTITIONS, namespace="pw7-amaro",
    )
    bellatrix.write_partition(image, layout, "kernel", boot_image)
    with tempfile.TemporaryDirectory(prefix=".pw7-prepared-", dir=image.parent) as temporary:
        work = Path(temporary)
        prepared = work / "rootfs.img"
        rootfs.prepare_pw7(rootfs_image, prepared)
        bellatrix.write_partition(image, layout, "rootfs", prepared)
        waveform = bellatrix_waveform.write_waveform(
            work / "synthetic-waveform", product="amaro",
        )
        waveform_image = work / "waveform.img"
        scribe_waveform_partition.build(
            waveform_image, waveform, partition_start=layout["wfm"][0],
            volume_label="EINK WFM   ",
        )
        bellatrix.write_partition(image, layout, "wfm", waveform_image)
    bellatrix3.initialize_persistent_filesystems(image, layout, rootfs_image)
    bellatrix.initialize_factory_data(image, layout)
    bellatrix.initialize_miscdata(image, layout)
    bellatrix.create_ext4_userstore(image, layout, eager_inode_init=True)
