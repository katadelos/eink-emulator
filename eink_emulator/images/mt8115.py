"""Compose MT8115 development storage from immutable imported firmware."""
from __future__ import annotations

import hashlib
import struct
import tempfile
from pathlib import Path

from . import bellatrix, rootfs, scribe_waveform, scribe_waveform_partition

MIB = 1024**2

# Keep existing CS8 disk/partition UUIDs stable across the shared-builder
# refactor. Add platforms only after their recovery/rootfs layout is audited.
PLATFORM_NAMESPACES = {"platcs8": "scribe-colorsoft", "platpa6": "scribe-3"}


def _fdt_property(blob: bytes, path: str, name: str) -> tuple[int, int, bytes]:
    """Locate an inline property in the v17 FDT used by the published FIT."""
    header = struct.unpack_from(">10I", blob)
    if header[0] != 0xD00DFEED or header[5] != 17 or header[1] > len(blob):
        raise ValueError("unsupported MT8115 device tree")
    offset, strings, end = header[2], header[3], header[2] + header[9]
    stack: list[str] = []
    while offset < end:
        start = offset
        token = struct.unpack_from(">I", blob, offset)[0]
        offset += 4
        if token == 1:
            terminator = blob.index(b"\0", offset, end)
            stack.append(blob[offset:terminator].decode())
            offset = (terminator + 4) & ~3
        elif token == 2:
            stack.pop()
        elif token == 3:
            length, string_offset = struct.unpack_from(">2I", blob, offset)
            offset += 8
            key_start = strings + string_offset
            key = blob[key_start:blob.index(b"\0", key_start)].decode()
            value = blob[offset:offset + length]
            offset = (offset + length + 3) & ~3
            if "/".join(stack) == path and key == name:
                return start, offset, value
        elif token == 9:
            break
        elif token != 4:
            raise ValueError("invalid MT8115 device tree token")
    raise ValueError(f"MT8115 device tree is missing {path}/{name}")


def _fdt_replace(blob: bytes, path: str, name: str, value: bytes) -> bytes:
    start, end, _ = _fdt_property(blob, path, name)
    header = list(struct.unpack_from(">10I", blob))
    replacement = (struct.pack(">2I", 3, len(value)) + blob[start + 8:start + 12]
                   + value + b"\0" * (-len(value) % 4))
    delta = len(replacement) - (end - start)
    output = bytearray(blob[:start] + replacement + blob[end:header[1]])
    header[1] += delta
    header[9] += delta
    for index in (2, 3, 4):
        if header[index] >= end:
            header[index] += delta
    struct.pack_into(">10I", output, 0, *header)
    return bytes(output)


def prepare_boot(source: Path, output: Path) -> None:
    """Disable verity for the prepared root and refresh the FIT image hash.

    QEMU's explicit development-mode handoff supplies an unfused U-Boot control
    tree without mandatory production keys. The kernel and recovery binaries
    remain original, and U-Boot still verifies each selected image's hash.
    """
    fit = source.read_bytes()
    node = "/images/fdt-mt8115-pa6-cs8"
    _, _, dtb = _fdt_property(fit, node, "data")
    _, _, arguments = _fdt_property(dtb, "/chosen", "bootargs")
    words = arguments.rstrip(b"\0").split()
    words = [word for word in words if not word.startswith(b"androidboot.veritymode=")]
    words.append(b"androidboot.veritymode=disabled")
    dtb = _fdt_replace(dtb, "/chosen", "bootargs", b" ".join(words) + b"\0")
    _, _, algorithm = _fdt_property(fit, node + "/hash", "algo")
    if algorithm != b"sha256\0":
        raise ValueError("unsupported MT8115 FIT device-tree hash")
    fit = _fdt_replace(fit, node, "data", dtb)
    fit = _fdt_replace(fit, node + "/hash", "value", hashlib.sha256(dtb).digest())
    output.write_bytes(fit)


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
    rootfs_image: Path,
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
    bellatrix.write_partition(image, layout, "firmware", firmware_image)
    with tempfile.TemporaryDirectory(
        prefix=".mt8115-prepared-", dir=image.parent,
    ) as temporary:
        prepared_root = Path(temporary) / "rootfs.img"
        prepared_boot = Path(temporary) / "boot.img"
        rootfs.copy_source(rootfs_image, prepared_root)
        rootfs.transform_file(
            prepared_root, "/etc/shadow", "0100600", rootfs.blank_root_password,
        )
        rootfs.replace_file(
            prepared_root, rootfs.OVERRIDES / "bellatrix3/console.conf",
            "/etc/upstart/console.conf", "0100644",
        )
        rootfs.prepare_usb_network(prepared_root, mass_storage=False)
        prepare_boot(boot_image, prepared_boot)
        bellatrix.write_partition(image, layout, "kernel", prepared_boot)
        bellatrix.write_partition(image, layout, "system", prepared_root)
    # Emulator-specific stimulus, clearly named and reproducible.
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
