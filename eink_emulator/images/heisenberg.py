"""Heisenberg-platform image recipe."""

from __future__ import annotations

from pathlib import Path

from . import imx6_mmc


def build(*, output: Path, kernel: Path, rootfs: Path) -> None:
    """Build the Eanab user area using Heisenberg's explicit layout profile."""
    imx6_mmc.build(
        output=output,
        kernel=kernel,
        rootfs=rootfs,
        layout="heisenberg",
    )
