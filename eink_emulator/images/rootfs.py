"""Shared ext-filesystem preparation for emulated Kindle guests."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from functools import cache
from pathlib import Path
from typing import Callable


ROOT = Path(__file__).resolve().parents[2]
OVERRIDES = ROOT / "guest-overrides"
EXT_MAGIC_OFFSET = 1024 + 56
FRAMEWORK_TIMEOUT_STOCK = "        TO=105\n"
FRAMEWORK_TIMEOUT_EMULATED = "        TO=600\n"


@cache
def find_debugfs() -> Path:
    candidates = (
        os.environ.get("DEBUGFS"),
        shutil.which("debugfs"),
        "/opt/homebrew/opt/e2fsprogs/sbin/debugfs",
        "/usr/local/opt/e2fsprogs/sbin/debugfs",
        "/usr/sbin/debugfs",
        "/sbin/debugfs",
    )
    for candidate in candidates:
        if candidate and os.access(candidate, os.X_OK):
            return Path(candidate)
    raise SystemExit("debugfs is required to prepare Kindle root filesystems")


def run(image: Path, command: str, *, writable: bool = False, check: bool = True) -> None:
    arguments = [str(find_debugfs())]
    if writable:
        arguments.append("-w")
    arguments.extend(["-R", command, str(image)])
    subprocess.run(
        arguments,
        check=check,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def run_many(image: Path, commands: list[str], *, writable: bool = False) -> None:
    """Execute a batch of debugfs commands in one process."""
    with tempfile.NamedTemporaryFile("w", prefix="eink-debugfs-commands-") as batch:
        batch.write("\n".join(commands) + "\n")
        batch.flush()
        arguments = [str(find_debugfs())]
        if writable:
            arguments.append("-w")
        arguments.extend(["-f", batch.name, str(image)])
        subprocess.run(
            arguments,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def copy_source(source: Path, output: Path, *, maximum_size: int | None = None) -> None:
    with source.open("rb") as input_file, output.open("wb") as output_file:
        shutil.copyfileobj(input_file, output_file, 8 * 1024 * 1024)
    if maximum_size is not None and output.stat().st_size > maximum_size:
        raise SystemExit(f"rootfs exceeds its {maximum_size}-byte partition")
    with output.open("rb") as image:
        image.seek(EXT_MAGIC_OFFSET)
        if image.read(2) != b"\x53\xef":
            raise SystemExit("rootfs is not an ext filesystem")


def replace_file(image: Path, source: Path, destination: str, mode: str) -> None:
    run_many(image, [
        f"rm {destination}",
        f"write {source} {destination}",
        f"set_inode_field {destination} mode {mode}",
    ], writable=True)


def transform_file(
    image: Path,
    destination: str,
    mode: str,
    transform: Callable[[str], str],
) -> None:
    with tempfile.TemporaryDirectory(prefix="eink-rootfs-file-") as directory:
        host_file = Path(directory) / Path(destination).name
        run(image, f"dump {destination} {host_file}")
        host_file.write_text(transform(host_file.read_text()))
        replace_file(image, host_file, destination, mode)


def blank_root_password(contents: str) -> str:
    lines = contents.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if line.startswith("root:"):
            fields = line.rstrip("\n").split(":")
            fields[1] = ""
            lines[index] = ":".join(fields) + ("\n" if line.endswith("\n") else "")
            return "".join(lines)
    raise SystemExit("root account is missing from the guest rootfs")


def extend_framework_timeout(contents: str) -> str:
    if contents.count(FRAMEWORK_TIMEOUT_STOCK) != 1:
        raise SystemExit("unexpected framework timeout configuration")
    return contents.replace(FRAMEWORK_TIMEOUT_STOCK, FRAMEWORK_TIMEOUT_EMULATED)


def install_overrides(
    image: Path, group: str, replacements: dict[str, tuple[str, str]]
) -> None:
    commands: list[str] = []
    for destination, (name, mode) in replacements.items():
        commands.extend([
            f"rm {destination}",
            f"write {OVERRIDES / group / name} {destination}",
            f"set_inode_field {destination} mode {mode}",
        ])
    run_many(image, commands, writable=True)


def prepare_wario(source: Path, output: Path) -> None:
    copy_source(source, output)
    install_overrides(image=output, group="wario", replacements={
        "/etc/upstart/perfd.conf": ("perfd.conf", "0100644"),
        "/etc/upstart/kb.conf": ("kb.conf", "0100644"),
        "/etc/upstart/prevent-screensaver.conf": ("prevent-screensaver.conf", "0100644"),
        "/etc/upstart/qemu-wake-gui.conf": ("qemu-wake-gui.conf", "0100644"),
    })
    transform_file(output, "/etc/shadow", "0100600", blank_root_password)


def prepare_heisenberg(source: Path, output: Path) -> None:
    copy_source(source, output)
    install_overrides(image=output, group="heisenberg", replacements={
        "/etc/upstart/perfd.conf": ("perfd.conf", "0100644"),
        "/etc/upstart/kb.conf": ("kb.conf", "0100644"),
        "/etc/upstart/prevent-screensaver.conf": ("prevent-screensaver.conf", "0100644"),
        "/etc/upstart/qemu-wake-gui.conf": ("qemu-wake-gui.conf", "0100644"),
    })
    install_overrides(image=output, group="heisenberg", replacements={
        "/etc/upstart/qemu-disable-kpp-boot.conf": ("qemu-disable-kpp-boot.conf", "0100644"),
        "/etc/upstart/qemu-eanab-offline.conf": ("qemu-eanab-offline.conf", "0100644"),
        "/etc/upstart/testd.conf": ("qemu-disabled-service.conf", "0100644"),
        "/etc/upstart/wifid.conf": ("qemu-disabled-service.conf", "0100644"),
        "/etc/upstart/wifim.conf": ("qemu-disabled-service.conf", "0100644"),
    })
    transform_file(output, "/etc/shadow", "0100600", blank_root_password)


def prepare_whitney(source: Path, output: Path, *, maximum_size: int) -> None:
    copy_source(source, output, maximum_size=maximum_size)
    transform_file(
        output,
        "/etc/upstart/framework_setup.conf",
        "0100644",
        extend_framework_timeout,
    )
    install_overrides(image=output, group="whitney", replacements={
        "/etc/upstart/qemu-wake-gui.conf": ("qemu-wake-gui.conf", "0100644"),
        "/etc/upstart/ttsd.conf": ("ttsd.conf", "0100644"),
    })
    transform_file(output, "/etc/shadow", "0100640", blank_root_password)


def prepare_celeste(source: Path, output: Path, *, maximum_size: int) -> None:
    copy_source(source, output, maximum_size=maximum_size)
    transform_file(
        output,
        "/etc/upstart/framework_setup.conf",
        "0100644",
        extend_framework_timeout,
    )
    install_overrides(image=output, group="celeste", replacements={
        "/etc/upstart/qemu-wake-gui.conf": ("qemu-wake-gui.conf", "0100644"),
        "/etc/upstart/ttsd.conf": ("ttsd.conf", "0100644"),
    })
    transform_file(output, "/etc/shadow", "0100640", blank_root_password)


def prepare_rex(source: Path, output: Path) -> None:
    copy_source(source, output)
    transform_file(
        output,
        "/etc/upstart/framework_setup.conf",
        "0100644",
        extend_framework_timeout,
    )
    transform_file(output, "/etc/shadow", "0100600", blank_root_password)
    install_overrides(image=output, group="rex", replacements={
        "/etc/upstart/qemu-wake-gui.conf": ("qemu-wake-gui.conf", "0100644"),
        "/etc/upstart/qemu-disable-kpp-boot.conf": ("qemu-disable-kpp-boot.conf", "0100644"),
        "/etc/upstart/qemu-seed-locale.conf": ("qemu-seed-locale.conf", "0100644"),
        "/etc/upstart/sshd.conf": ("qemu-disabled-service.conf", "0100644"),
        "/etc/upstart/wifid.conf": ("qemu-disabled-service.conf", "0100644"),
        "/etc/upstart/wifim.conf": ("qemu-disabled-service.conf", "0100644"),
        "/etc/upstart/wifis.conf": ("qemu-disabled-service.conf", "0100644"),
    })
