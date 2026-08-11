"""Wario-platform image recipe."""

from __future__ import annotations

from pathlib import Path

from . import imx6_mmc


def build(
    *,
    output: Path,
    kernel: Path,
    rootfs: Path,
    layout: str,
    diagnostics_kernel: Path | None = None,
    diagnostics: Path | None = None,
    waveform_store: Path | None = None,
) -> None:
    imx6_mmc.build(
        output=output,
        kernel=kernel,
        rootfs=rootfs,
        layout=layout,
        diagnostics_kernel=diagnostics_kernel,
        diagnostics=diagnostics,
        waveform_store=waveform_store,
    )
