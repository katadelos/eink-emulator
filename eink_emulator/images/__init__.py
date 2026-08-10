"""Reusable firmware-to-disk image builders."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from . import rex, rootfs, tequila, wario, whitney


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
    if builder == "wario":
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
