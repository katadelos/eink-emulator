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
COLORSOFT_FRAMEWORK_MARKER = "Colorsoft QEMU: skip recursive permission repair"
COLORSOFT_WATCHDOG_MARKER = "Colorsoft QEMU: wait indefinitely under TCG"
COLORSOFT_STACK_DUMP_MARKER = "Colorsoft QEMU: skip native stack dumps under TCG"
COLORSOFT_USERSTORE_MARKER = "Colorsoft QEMU: coalesce emulated userstore writes"
COLORSOFT_VARLOCAL_MARKER = "Colorsoft QEMU: coalesce emulated var-local writes"
COLORSOFT_JAVA_MARKER = "Colorsoft QEMU: trust the immutable firmware class path"
COLORSOFT_HIBERNATE_MARKER = "Colorsoft QEMU: skip absent hibernate payload"


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


def colorsoft_patch_framework(contents: str) -> str:
    if COLORSOFT_FRAMEWORK_MARKER in contents:
        return contents

    start = contents.find("  set +e\n  DIRLIST=")
    end_token = "  set -e\n  f_log I framework starting"
    end = contents.find(end_token, start)
    if start < 0 or end < 0:
        raise SystemExit("stock framework.conf permission-repair block was not found")

    replacement = (
        "  set +e\n"
        f"  # {COLORSOFT_FRAMEWORK_MARKER}; the prepared image already has correct ownership.\n"
        "  set -e\n"
    )
    return contents[:start] + replacement + contents[end + len("  set -e\n") :]


def colorsoft_patch_framework_setup(contents: str) -> str:
    if COLORSOFT_WATCHDOG_MARKER in contents:
        return contents
    old = "        TO=105\n"
    if contents.count(old) != 1:
        raise SystemExit(
            "stock framework_setup.conf watchdog assignment was not found exactly once"
        )
    return contents.replace(
        old,
        f"        TO=0  # {COLORSOFT_WATCHDOG_MARKER}\n",
        1,
    )


def colorsoft_patch_dump_stack(contents: str) -> str:
    if COLORSOFT_STACK_DUMP_MARKER in contents:
        return contents
    shebang = "#!/bin/sh\n"
    if not contents.startswith(shebang):
        raise SystemExit("unexpected /usr/bin/dump-stack interpreter")
    replacement = (
        shebang
        + f"# {COLORSOFT_STACK_DUMP_MARKER}; guest gdb can monopolize an "
        "emulated CPU for minutes.\n"
        + "exit 0\n"
    )
    return replacement + contents[len(shebang) :]


def colorsoft_patch_userstore_mount(contents: str) -> str:
    if COLORSOFT_USERSTORE_MARKER in contents:
        return contents
    old = (
        "        mount -t ext4 ${MNTUS_LOOP_DEV} ${userstore_mount_point} "
        "-o defaults,errors=remount-ro\n"
    )
    if contents.count(old) != 1:
        raise SystemExit("stock userstore ext4 mount command was not found exactly once")
    new = (
        f"        # {COLORSOFT_USERSTORE_MARKER}.\n"
        "        mount -t ext4 ${MNTUS_LOOP_DEV} ${userstore_mount_point} "
        "-o defaults,errors=remount-ro,noatime,nodiratime,nobarrier,commit=60\n"
    )
    return contents.replace(old, new, 1)


def colorsoft_patch_varlocal_mount(contents: str) -> str:
    if COLORSOFT_VARLOCAL_MARKER in contents:
        return contents
    old = "     mount -t ext4 -o rw $local $mount_point\n"
    if contents.count(old) != 1:
        raise SystemExit("stock var-local ext4 mount command was not found exactly once")
    new = (
        f"     # {COLORSOFT_VARLOCAL_MARKER}.\n"
        "     mount -t ext4 -o rw,noatime,nodiratime,nobarrier,commit=60 "
        "$local $mount_point\n"
    )
    return contents.replace(old, new, 1)


def colorsoft_patch_java_verification(contents: str) -> str:
    if COLORSOFT_JAVA_MARKER in contents:
        return contents
    old = 'else\n  VERIFY="-Xverify:remote"\nfi\n'
    if contents.count(old) != 1:
        raise SystemExit("stock framework Java verification setting was not found exactly once")
    new = (
        "else\n"
        f"  # {COLORSOFT_JAVA_MARKER}.\n"
        '  VERIFY="-Xverify:none"\n'
        "fi\n"
    )
    return contents.replace(old, new, 1)


def colorsoft_patch_filesystems_setup(contents: str) -> str:
    if COLORSOFT_HIBERNATE_MARKER in contents:
        return contents
    old = (
        "  if [[ -e $FIRST_BOOT_AFTER_UPDATE_FILE ]]; then\n"
        "    blast_hibernate_partition\n"
        "  fi\n"
    )
    if contents.count(old) != 1:
        raise SystemExit("stock Colorsoft hibernate blast block was not found exactly once")
    new = (
        "  if [[ -e $FIRST_BOOT_AFTER_UPDATE_FILE ]]; then\n"
        f"    f_log I filesystems_setup \"{COLORSOFT_HIBERNATE_MARKER}\"\n"
        "  fi\n"
    )
    return contents.replace(old, new, 1)


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


def prepare_colorsoft(source: Path, output: Path, *, maximum_size: int) -> None:
    copy_source(source, output, maximum_size=maximum_size)
    transforms = (
        ("/etc/upstart/framework.conf", "0100644", colorsoft_patch_framework),
        (
            "/etc/upstart/framework_setup.conf",
            "0100644",
            colorsoft_patch_framework_setup,
        ),
        ("/usr/bin/dump-stack", "0100755", colorsoft_patch_dump_stack),
        (
            "/usr/sbin/mntus_functions_ext4",
            "0100755",
            colorsoft_patch_userstore_mount,
        ),
        (
            "/etc/upstart/varlocal_functions",
            "0100755",
            colorsoft_patch_varlocal_mount,
        ),
        ("/etc/upstart/framework", "0100755", colorsoft_patch_java_verification),
        (
            "/etc/upstart/filesystems_setup.conf",
            "0100644",
            colorsoft_patch_filesystems_setup,
        ),
        ("/etc/shadow", "0100600", blank_root_password),
    )
    for destination, mode, transform in transforms:
        transform_file(output, destination, mode, transform)

    install_overrides(image=output, group="colorsoft", replacements={
        "/etc/upstart/prevent-screensaver.conf": (
            "prevent-screensaver.conf",
            "0100644",
        ),
        "/etc/upstart/qemu-skip-oobe.conf": (
            "qemu-skip-oobe.conf",
            "0100644",
        ),
        "/etc/upstart/tzd.conf": ("tzd.conf", "0100644"),
        "/etc/upstart/registrationd.conf": ("registrationd.conf", "0100644"),
        "/etc/upstart/minerva_service.conf": (
            "qemu-disabled-service.conf",
            "0100644",
        ),
        "/etc/upstart/minervad.conf": (
            "qemu-disabled-service.conf",
            "0100644",
        ),
        "/etc/upstart/wmt.conf": (
            "qemu-disabled-service.conf",
            "0100644",
        ),
        "/etc/upstart/wifid.conf": (
            "qemu-disabled-service.conf",
            "0100644",
        ),
        "/etc/upstart/wifim.conf": (
            "qemu-disabled-service.conf",
            "0100644",
        ),
        "/etc/upstart/wifis.conf": (
            "qemu-disabled-service.conf",
            "0100644",
        ),
    })
