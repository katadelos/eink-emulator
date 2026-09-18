"""Reusable firmware-to-disk image builders."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from . import (
    bellatrix, bellatrix3, celeste, elipsa2e, forma, heisenberg, mt8115, rex, rootfs,
    tequila, wario, whitney,
)


def build_raw_image(
    definition: dict[str, Any], artifacts: dict[str, Path], output: Path
) -> Path:
    """Build a sparse raw source image and return its path.

    A user-supplied full disk is returned directly, avoiding a redundant and
    potentially non-sparse host copy before QCOW2 conversion.
    """
    builder = definition["builder"]
    if builder == "disk-copy":
        return artifacts["disk"]
    if builder == "forma":
        forma.build(output, artifacts, sideloaded=definition.get("sideloaded", False))
    elif builder == "elipsa2e":
        elipsa2e.build(output, artifacts, sideloaded=definition.get("sideloaded", False))
    elif builder == "bellatrix":
        prepared = output.with_name("prepared-rootfs.img")
        board = definition["machine_properties"]["board"]
        rootfs.prepare_bellatrix(
            artifacts["rootfs"],
            prepared,
            maximum_size=bellatrix.ROOTFS_SIZE,
            board=board,
        )
        bellatrix.build(
            output,
            boot_image=artifacts["boot_image"],
            rootfs_image=prepared,
            waveform_image=artifacts.get("waveform_store"),
            userstore_format="vfat" if board == "cava" else "ext4",
        )
    elif builder == "bellatrix3":
        bellatrix3.build(
            output, board=definition["machine_properties"]["board"],
            boot_image=artifacts["boot_image"], rootfs_image=artifacts["rootfs"],
            waveform_image=artifacts.get("waveform_store"),
        )
    elif builder == "mt8115":
        mt8115.build(
            output, platform=definition["image_platform"],
            boot_image=artifacts["boot_image"],
            firmware_image=artifacts["aux_firmware"],
            rootfs_image=artifacts["rootfs"],
            waveform_image=artifacts.get("waveform_store"),
        )
    elif builder == "wario":
        prepared = output.with_name("prepared-rootfs.img")
        rootfs.prepare_wario(artifacts["rootfs"], prepared)
        wario.build(
            output=output,
            kernel=artifacts["kernel"],
            rootfs=prepared,
            layout=definition["wario_layout"],
            diagnostics_kernel=artifacts.get("diagnostics_kernel"),
            diagnostics=artifacts.get("diagnostics"),
            waveform_store=artifacts.get("waveform_store"),
        )
    elif builder == "heisenberg":
        prepared = output.with_name("prepared-rootfs.img")
        rootfs.prepare_heisenberg(artifacts["rootfs"], prepared)
        heisenberg.build(
            output=output,
            kernel=artifacts["kernel"],
            rootfs=prepared,
        )
    elif builder == "celeste":
        prepared = output.with_name("prepared-rootfs.img")
        rootfs.prepare_celeste(
            artifacts["rootfs"], prepared,
            maximum_size=celeste.ROOTFS_SIZE,
        )
        celeste.build(output, artifacts["kernel"], prepared)
    elif builder == "tequila":
        tequila.build(output, artifacts["kernel"], artifacts["rootfs"])
    elif builder == "whitney":
        whitney.build(output, artifacts["kernel"], artifacts["rootfs"])
    elif builder == "rex":
        prepared = output.with_name("prepared-rootfs.img")
        rootfs.prepare_rex(artifacts["rootfs"], prepared)
        rex.build(
            output,
            boot_image=artifacts["boot_image"],
            rootfs_image=prepared,
            waveform_image=artifacts["waveform_store"],
        )
    else:
        raise ValueError(f"unknown image builder: {builder}")
    return output
