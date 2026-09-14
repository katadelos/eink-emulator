"""Compose MT8115 storage while retaining each platform's stock AVB rootfs."""
from __future__ import annotations

from pathlib import Path

from . import bellatrix, scribe_waveform, scribe_waveform_partition

MIB = 1024**2

# Keep existing CS8 disk/partition UUIDs stable across the shared-builder
# refactor. Add platforms only after their recovery/rootfs layout is audited.
PLATFORM_NAMESPACES = {"platcs8": "scribe-colorsoft", "platpa6": "scribe-3"}


def partitions(rootfs_size: int) -> list[tuple[str, int]]:
    # Platcs8 and Platpa6 stock platform_variables/recovery agree on slots.
    # Neither update publishes factory geometry for intermediate slots.
    return [
        ("kernel", 64 * MIB),
        ("wfm", 64 * MIB),
        ("firmware", 16 * MIB),
        ("pdata", 128 * MIB),
        ("diags_kernel", 64 * MIB),
        ("diags", 768 * MIB),
        ("keys", 16 * MIB),
        ("reserved0", 16 * MIB),
        ("miscdata", 512 * MIB),
        ("snapshot", 1024 * MIB),
        ("system", rootfs_size),
        ("varlocal", 512 * MIB),
    ]


def initialize_factory_data(image: Path, layout: dict[str, tuple[int, int]]) -> None:
    bellatrix.initialize_factory_data(image, layout)
    # U-Boot's parser requires every key even for a fresh cold-boot disk.
    keys = (
        "type", "force_splash", "splash_middle", "splash_reverse",
        "working_buffer_addr", "waveform_addr", "waveform_offset",
        "waveform_size", "splash_offset", "splash_size",
        "working_buffer_offset", "working_buffer_size",
    )
    config = "".join(f"{key}=0\n" for key in keys).encode()
    with image.open("r+b") as stream:
        stream.seek(layout["miscdata"][0] * 512)
        stream.write(config.ljust(4096, b"\0"))


def build(
    image: Path, *, platform: str, boot_image: Path, firmware_image: Path,
    rootfs_image: Path, waveform_image: Path | None = None,
    size: int = 8 * 1024**3,
) -> None:
    if platform not in PLATFORM_NAMESPACES:
        raise ValueError(f"unsupported MT8115 image platform: {platform}")
    for payload in (boot_image, firmware_image, rootfs_image):
        if not payload.is_file():
            raise ValueError(f"missing {platform} firmware: {payload}")
    rootfs_size = rootfs_image.stat().st_size
    if rootfs_size % 512 or rootfs_size < 64:
        raise ValueError(f"{platform} rootfs must be a sector-aligned AVB image")
    with rootfs_image.open("rb") as stream:
        stream.seek(-64, 2)
        if stream.read(4) != b"AVBf":
            raise ValueError(f"{platform} rootfs is missing its stock AVB footer")
    if size % 512:
        raise ValueError("disk size must be sector-aligned")
    layout = bellatrix.create_image(
        image, size, partitions=partitions(rootfs_size),
        namespace=PLATFORM_NAMESPACES[platform],
    )
    bellatrix.write_partition(image, layout, "kernel", boot_image)
    bellatrix.write_partition(image, layout, "firmware", firmware_image)
    # Exact partition size keeps AVB's footer at the end of the block device.
    bellatrix.write_partition(image, layout, "system", rootfs_image)
    if waveform_image is None:
        # Emulator-specific stimulus, clearly named and reproducible. The
        # stock update does not contain the factory waveform partition.
        waveform_directory = image.parent / "synthetic-waveform"
        waveform = scribe_waveform.write_waveform(
            waveform_directory, product=platform.removeprefix("plat"),
        )
        waveform_image = image.with_suffix(".waveform.img")
        scribe_waveform_partition.build(
            waveform_image, waveform, partition_start=layout["wfm"][0],
        )
    bellatrix.write_partition(image, layout, "wfm", waveform_image)
    initialize_factory_data(image, layout)
    bellatrix.create_ext4_userstore(image, layout)
