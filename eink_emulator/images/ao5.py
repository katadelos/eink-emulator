"""Compose Amaro and Julep storage from stock AO5 firmware dumps."""

from __future__ import annotations

import tempfile
from pathlib import Path

from . import bellatrix, bellatrix3, bellatrix_waveform, rootfs, scribe_waveform_partition

MIB = 1024**2
ROOTFS_SIZES = {"amaro": 1280 * MIB, "julep": 1536 * MIB}


def partitions(rootfs_size: int) -> list[tuple[str, int]]:
    # Both platforms fix keys=p3, pdata=p5, root=p8, local=p9, user=p10.
    return [
        ("kernel", 64 * MIB),
        ("wfm", 64 * MIB),
        ("keys", 16 * MIB),
        ("reserved0", 64 * MIB),
        ("pdata", 512 * MIB),
        ("snapshot", 1024 * MIB),
        ("miscdata", 512 * MIB),
        ("rootfs", rootfs_size),
        ("varlocal", 512 * MIB),
    ]


def build(
    image: Path, *, board: str, boot_image: Path, rootfs_image: Path,
    waveform_image: Path | None = None,
    size: int = 8 * 1024**3,
) -> None:
    if board not in ROOTFS_SIZES:
        raise ValueError(f"unsupported AO5 board: {board}")
    rootfs_size = ROOTFS_SIZES[board]
    for payload in (boot_image, rootfs_image):
        if not payload.is_file():
            raise ValueError(f"missing {board} firmware: {payload}")
    if rootfs_image.stat().st_size != rootfs_size:
        raise ValueError(f"{board} requires the original {rootfs_size // MIB} MiB rootfs image")
    if board == "julep" and (
        waveform_image is None or not waveform_image.is_file()
        or waveform_image.stat().st_size != 16 * MIB
    ):
        raise ValueError("Julep requires the original 16 MiB waveform partition")
    if size % 512:
        raise ValueError("AO5 disk must be sector-aligned")

    layout = bellatrix.create_image(
        image, size, partitions=partitions(rootfs_size),
        namespace="pw7-amaro" if board == "amaro" else "cs2-julep",
    )
    bellatrix.write_partition(image, layout, "kernel", boot_image)
    with tempfile.TemporaryDirectory(prefix=f".{board}-prepared-", dir=image.parent) as temporary:
        work = Path(temporary)
        prepared = work / "rootfs.img"
        rootfs.prepare_ao5(rootfs_image, prepared, maximum_size=rootfs_size)
        bellatrix.write_partition(image, layout, "rootfs", prepared)
        if board == "amaro":
            waveform = bellatrix_waveform.write_waveform(
                work / "synthetic-waveform", product=board,
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
