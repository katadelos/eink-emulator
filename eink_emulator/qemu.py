"""QEMU build orchestration used by the command-line interface."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
QEMU_ROOT = ROOT / "qemu"
BUILD_ROOT = QEMU_ROOT / "build"
TARGETS = ("qemu-system-arm", "qemu-img")


def run(command: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None) -> None:
    subprocess.run(command, cwd=cwd, env=env, check=True)


def configure() -> None:
    environment = os.environ.copy()
    for variable, candidate in (("AR", "/usr/bin/ar"), ("RANLIB", "/usr/bin/ranlib")):
        if Path(candidate).is_file():
            environment[variable] = candidate
    run([
        "./configure",
        "--target-list=arm-softmmu",
        "--disable-docs",
        "--disable-werror",
        "--enable-slirp",
        "-Dforce_fallback_for=slirp",
    ], cwd=QEMU_ROOT, env=environment)


def sign_macos_binaries() -> None:
    xattr = shutil.which("xattr")
    codesign = shutil.which("codesign")
    if not codesign:
        raise SystemExit("codesign is required to prepare QEMU on macOS")
    for target in TARGETS:
        binary = BUILD_ROOT / target
        if xattr:
            for attribute in ("com.apple.FinderInfo", "com.apple.ResourceFork"):
                subprocess.run(
                    [xattr, "-d", attribute, str(binary)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
        run([codesign, "--force", "--sign", "-", str(binary)])


def build() -> None:
    """Initialise, configure, and build only the QEMU targets this project uses."""
    run(["git", "-C", str(ROOT), "submodule", "update", "--init", "qemu"])
    if not (BUILD_ROOT / "build.ninja").is_file():
        configure()
    run(["ninja", "-C", str(BUILD_ROOT), *TARGETS])
    if sys.platform == "darwin":
        sign_macos_binaries()
