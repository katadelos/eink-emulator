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
BELLATRIX3_FRAMEWORK_MARKER = "Bellatrix3 QEMU: inherit initialized runtime permissions"
BELLATRIX_FRAMEWORK_MARKER = "Bellatrix QEMU: skip recursive permission repair"
BELLATRIX_WATCHDOG_MARKER = "Bellatrix QEMU: wait indefinitely under TCG"
BELLATRIX_STACK_DUMP_MARKER = "Bellatrix QEMU: skip native stack dumps under TCG"
BELLATRIX_USERSTORE_MARKER = "Bellatrix QEMU: coalesce emulated userstore writes"
BELLATRIX_VARLOCAL_MARKER = "Bellatrix QEMU: coalesce emulated var-local writes"
BELLATRIX_JAVA_MARKER = "Bellatrix QEMU: trust the immutable firmware class path"
BELLATRIX_HIBERNATE_MARKER = "Bellatrix QEMU: skip absent hibernate payload"
BELLATRIX_LOOPBACK_MARKER = "Bellatrix QEMU: create packaged loopback mountpoints"


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


def bellatrix_patch_framework(contents: str) -> str:
    if BELLATRIX_FRAMEWORK_MARKER in contents:
        return contents

    start = contents.find("  set +e\n  DIRLIST=")
    end_token = "  set -e\n  f_log I framework starting"
    end = contents.find(end_token, start)
    if start < 0 or end < 0:
        raise SystemExit("stock framework.conf permission-repair block was not found")

    replacement = (
        "  set +e\n"
        f"  # {BELLATRIX_FRAMEWORK_MARKER}; the prepared image already has correct ownership.\n"
        "  set -e\n"
    )
    return contents[:start] + replacement + contents[end + len("  set -e\n") :]


def bellatrix_patch_framework_setup(contents: str) -> str:
    if BELLATRIX_WATCHDOG_MARKER in contents:
        return contents
    old = "        TO=105\n"
    if contents.count(old) != 1:
        raise SystemExit(
            "stock framework_setup.conf watchdog assignment was not found exactly once"
        )
    return contents.replace(
        old,
        f"        TO=0  # {BELLATRIX_WATCHDOG_MARKER}\n",
        1,
    )


def bellatrix_patch_dump_stack(contents: str) -> str:
    if BELLATRIX_STACK_DUMP_MARKER in contents:
        return contents
    shebang = "#!/bin/sh\n"
    if not contents.startswith(shebang):
        raise SystemExit("unexpected /usr/bin/dump-stack interpreter")
    replacement = (
        shebang
        + f"# {BELLATRIX_STACK_DUMP_MARKER}; guest gdb can monopolize an "
        "emulated CPU for minutes.\n"
        + "exit 0\n"
    )
    return replacement + contents[len(shebang) :]


def bellatrix_patch_userstore_mount(contents: str) -> str:
    if BELLATRIX_USERSTORE_MARKER in contents:
        return contents
    old = (
        "        mount -t ext4 ${MNTUS_LOOP_DEV} ${userstore_mount_point} "
        "-o defaults,errors=remount-ro\n"
    )
    if contents.count(old) != 1:
        raise SystemExit("stock userstore ext4 mount command was not found exactly once")
    new = (
        f"        # {BELLATRIX_USERSTORE_MARKER}.\n"
        "        mount -t ext4 ${MNTUS_LOOP_DEV} ${userstore_mount_point} "
        "-o defaults,errors=remount-ro,noatime,nodiratime,nobarrier,commit=60\n"
    )
    return contents.replace(old, new, 1)


def bellatrix_patch_varlocal_mount(contents: str) -> str:
    if BELLATRIX_VARLOCAL_MARKER in contents:
        return contents
    old = "     mount -t ext4 -o rw $local $mount_point\n"
    if contents.count(old) != 1:
        raise SystemExit("stock var-local ext4 mount command was not found exactly once")
    new = (
        f"     # {BELLATRIX_VARLOCAL_MARKER}.\n"
        "     mount -t ext4 -o rw,noatime,nodiratime,nobarrier,commit=60 "
        "$local $mount_point\n"
    )
    return contents.replace(old, new, 1)


def bellatrix_patch_ext3_varlocal_mount(contents: str) -> str:
    if BELLATRIX_VARLOCAL_MARKER in contents:
        return contents
    old = "     mount -t ext3 -o rw $local $mount_point\n"
    if contents.count(old) != 1:
        raise SystemExit("stock Bellatrix var-local ext3 mount command was not found exactly once")
    new = (
        f"     # {BELLATRIX_VARLOCAL_MARKER}.\n"
        "     mount -t ext3 -o rw,noatime,nodiratime,nobarrier,commit=60 "
        "$local $mount_point\n"
    )
    return contents.replace(old, new, 1)


def bellatrix_patch_java_verification(contents: str) -> str:
    if BELLATRIX_JAVA_MARKER in contents:
        return contents
    old = 'else\n  VERIFY="-Xverify:remote"\nfi\n'
    if contents.count(old) != 1:
        raise SystemExit("stock framework Java verification setting was not found exactly once")
    new = (
        "else\n"
        f"  # {BELLATRIX_JAVA_MARKER}.\n"
        '  VERIFY="-Xverify:none"\n'
        "fi\n"
    )
    return contents.replace(old, new, 1)


def bellatrix_patch_filesystems_setup(contents: str) -> str:
    if BELLATRIX_HIBERNATE_MARKER in contents:
        return contents
    old = (
        "  if [[ -e $FIRST_BOOT_AFTER_UPDATE_FILE ]]; then\n"
        "    blast_hibernate_partition\n"
        "  fi\n"
    )
    if contents.count(old) != 1:
        raise SystemExit("stock Bellatrix hibernate blast block was not found exactly once")
    new = (
        "  if [[ -e $FIRST_BOOT_AFTER_UPDATE_FILE ]]; then\n"
        f"    f_log I filesystems_setup \"{BELLATRIX_HIBERNATE_MARKER}\"\n"
        "  fi\n"
    )
    return contents.replace(old, new, 1)


def bellatrix_patch_loopback_mounts(contents: str) -> str:
    if BELLATRIX_LOOPBACK_MARKER in contents:
        return contents
    old = "      if [ -d ${lbmountpt} ]; then\n"
    if contents.count(old) != 1:
        raise SystemExit("stock Bellatrix loopback mountpoint check was not found")
    new = (
        f"      # {BELLATRIX_LOOPBACK_MARKER}.\n"
        "      if [ -f ${lbmountpt}.${LOOPBACKFSEXT} ]; then\n"
        "        mkdir -p ${lbmountpt}\n"
        "      fi\n"
        "      if [ -d ${lbmountpt} ]; then\n"
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


def prepare_kt4(source: Path, output: Path) -> None:
    copy_source(source, output, maximum_size=512 * 1024**2)
    install_overrides(image=output, group="oasis", replacements={
        "/etc/upstart/console.conf": ("console.conf", "0100644"),
        "/etc/upstart/prevent-screensaver.conf": ("prevent-screensaver.conf", "0100644"),
        "/etc/upstart/qemu-wake-gui.conf": ("qemu-wake-gui.conf", "0100644"),
        "/etc/upstart/qemu-disable-kpp-boot.conf": ("qemu-disable-kpp-boot.conf", "0100644"),
    })
    install_overrides(image=output, group="rex", replacements={
        "/etc/upstart/qemu-seed-locale.conf": ("qemu-seed-locale.conf", "0100644"),
    })
    install_overrides(image=output, group="bellatrix", replacements={
        "/etc/upstart/qemu-skip-oobe.conf": ("qemu-skip-oobe.conf", "0100644"),
    })
    transform_file(output, "/etc/shadow", "0100600", blank_root_password)


def prepare_koa3(source: Path, output: Path) -> None:
    copy_source(source, output, maximum_size=512 * 1024**2)
    install_overrides(image=output, group="oasis", replacements={
        "/etc/upstart/console.conf": ("console.conf", "0100644"),
        "/etc/upstart/prevent-screensaver.conf": ("prevent-screensaver.conf", "0100644"),
        "/etc/upstart/qemu-wake-gui.conf": ("qemu-wake-gui.conf", "0100644"),
        "/etc/upstart/qemu-disable-kpp-boot.conf": ("qemu-disable-kpp-boot.conf", "0100644"),
    })
    install_overrides(image=output, group="rex", replacements={
        "/etc/upstart/qemu-seed-locale.conf": ("qemu-seed-locale.conf", "0100644"),
    })
    install_overrides(image=output, group="bellatrix", replacements={
        "/etc/upstart/qemu-skip-oobe.conf": ("qemu-skip-oobe.conf", "0100644"),
    })
    transform_file(output, "/etc/shadow", "0100600", blank_root_password)


def prepare_oasis(source: Path, output: Path, *, wifi: bool) -> None:
    copy_source(source, output)
    install_overrides(image=output, group="oasis", replacements={
        "/etc/upstart/perfd.conf": ("perfd.conf", "0100644"),
        "/etc/upstart/kb.conf": ("kb.conf", "0100644"),
        "/etc/upstart/console.conf": ("console.conf", "0100644"),
        "/etc/upstart/prevent-screensaver.conf": ("prevent-screensaver.conf", "0100644"),
        "/etc/upstart/qemu-wake-gui.conf": ("qemu-wake-gui.conf", "0100644"),
    })
    install_overrides(image=output, group="oasis", replacements={
        "/etc/upstart/qemu-disable-kpp-boot.conf": ("qemu-disable-kpp-boot.conf", "0100644"),
        "/etc/upstart/testd.conf": ("qemu-disabled-service.conf", "0100644"),
    })
    if not wifi:
        install_overrides(image=output, group="oasis", replacements={
            "/etc/upstart/qemu-oasis-offline.conf": ("qemu-oasis-offline.conf", "0100644"),
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


def prepare_bellatrix(
    source: Path, output: Path, *, maximum_size: int, board: str
) -> None:
    if board not in {"cava", "malbec", "rossini", "sangria", "sangria-color"}:
        raise ValueError(f"unsupported Bellatrix board: {board}")
    copy_source(source, output, maximum_size=maximum_size)
    transforms = [
        ("/etc/upstart/framework.conf", "0100644", bellatrix_patch_framework),
        (
            "/etc/upstart/framework_setup.conf",
            "0100644",
            bellatrix_patch_framework_setup,
        ),
        (
            "/etc/upstart/varlocal_functions",
            "0100755",
            bellatrix_patch_ext3_varlocal_mount
            if board in {"cava", "malbec"}
            else bellatrix_patch_varlocal_mount,
        ),
        ("/etc/upstart/framework", "0100755", bellatrix_patch_java_verification),
        (
            "/etc/upstart/filesystems_setup.conf",
            "0100644",
            bellatrix_patch_filesystems_setup,
        ),
        ("/etc/shadow", "0100600", blank_root_password),
    ]
    if board not in {"cava", "malbec"}:
        transforms.insert(
            2,
            (
                "/usr/sbin/mntus_functions_ext4",
                "0100755",
                bellatrix_patch_userstore_mount,
            ),
        )
    if board == "sangria-color":
        transforms.insert(
            2,
            ("/usr/bin/dump-stack", "0100755", bellatrix_patch_dump_stack),
        )
    if board == "sangria":
        transforms.insert(
            2,
            (
                "/etc/upstart/system_cramfs_loopbacks.conf",
                "0100644",
                bellatrix_patch_loopback_mounts,
            ),
        )
    for destination, mode, transform in transforms:
        transform_file(output, destination, mode, transform)

    install_overrides(image=output, group="bellatrix", replacements={
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


def bellatrix3_patch_framework(contents: str) -> str:
    """Move stock permission setup before producers; keep restarts constant cost."""
    if BELLATRIX3_FRAMEWORK_MARKER in contents:
        return contents
    start = contents.find("  set +e\n  DIRLIST=")
    end = contents.find("  set -e\n  f_log I framework starting", start)
    if start < 0 or end < 0:
        raise SystemExit("stock Bellatrix3 runtime permission block was not found")
    if contents[start:end].count("'{}' \\;") != 5:
        raise SystemExit("expected five stock Bellatrix3 find -exec actions")
    replacement = (
        f"  # {BELLATRIX3_FRAMEWORK_MARKER}.\n"
        "  /usr/sbin/qemu-runtime-permissions framework\n"
    )
    return contents[:start] + replacement + contents[end:]


def bellatrix3_patch_system_permissions(contents: str) -> str:
    marker = "  f_log I sytem mounted_tmpfs\n"
    if contents.count(marker) != 1:
        raise SystemExit("stock Bellatrix3 tmpfs readiness boundary was not found")
    return contents.replace(
        marker, "  /usr/sbin/qemu-runtime-permissions runtime\n" + marker, 1,
    )


def bellatrix3_patch_varlocal_permissions(contents: str) -> str:
    old = "  chgrp -R javausers /var/local/ || true\n"
    if contents.count(old) != 1:
        raise SystemExit("stock Bellatrix3 var-local ownership boundary was not found")
    return contents.replace(
        old,
        "  # Display's starting job migrates existing descendants once.\n"
        "  chgrp javausers /var/local/ || true\n"
        "  chmod g=u,g+s /var/local/ || true\n",
        1,
    )


def prepare_bellatrix3(
    source: Path, output: Path, *, board: str, waveform: Path | None,
) -> None:
    """Install the Scribe development boot jobs in a generated rootfs copy.

    These Linux 4.9 roots have no dm-verity. Keep their stock storage cleanup
    and account identity handling intact; USB Ethernet is
    the development network while unsupported radio services are excluded.
    """
    if board not in {"barolo", "pisco"}:
        raise ValueError(f"unsupported Bellatrix3 board: {board}")
    copy_source(source, output, maximum_size=768 * 1024**2)
    # Published /etc/deviceTypes.conf maps production serial codes to these
    # product types. DVT serial tattoos are absent; liblab126utils supports
    # /var/local/deviceType.txt as its explicit override before serial lookup.
    product_type = {
        "barolo": "A12KI9K1KHHBVF",
        "pisco": "A3TY6T3X94EBV6",
    }[board]
    with tempfile.NamedTemporaryFile("w", prefix="eink-device-type-") as device_type:
        device_type.write(product_type)
        device_type.flush()
        replace_file(
            output, Path(device_type.name), "/etc/qemu-device-type", "0100644",
        )
    transform_file(
        output, "/etc/upstart/framework.conf", "0100644",
        bellatrix3_patch_framework,
    )
    transform_file(
        output, "/etc/upstart/system.conf", "0100644",
        bellatrix3_patch_system_permissions,
    )
    transform_file(
        output, "/etc/upstart/filesystems_var_local.conf", "0100644",
        bellatrix3_patch_varlocal_permissions,
    )
    transform_file(
        output, "/etc/upstart/framework_setup.conf", "0100644",
        extend_framework_timeout,
    )

    def stop_successful_sysctl(contents: str) -> str:
        old = "\nrespawn\n"
        if contents.count(old) != 1:
            raise SystemExit("stock sysctl respawn declaration was not found exactly once")
        return contents.replace(old, "\nrespawn\nnormal exit 0\n", 1)

    transform_file(
        output, "/etc/upstart/sysctl.conf", "0100644",
        stop_successful_sysctl,
    )
    install_overrides(image=output, group="bellatrix3", replacements={
        "/usr/sbin/qemu-runtime-permissions": (
            "qemu-runtime-permissions", "0100755",
        ),
        "/etc/upstart/console.conf": ("console.conf", "0100644"),
        "/etc/upstart/display": ("display", "0100755"),
        "/etc/upstart/qemu-development-state.conf": (
            "qemu-development-state.conf", "0100644",
        ),
        "/etc/upstart/qemu-usb-network.conf": (
            "qemu-usb-network.conf", "0100644",
        ),
        "/etc/upstart/qemu-telnet.conf": ("qemu-telnet.conf", "0100644"),
        "/etc/upstart/qemu-review-awake.conf": (
            "qemu-review-awake.conf", "0100644",
        ),
        "/etc/upstart/mtp.conf": ("mtp.conf", "0100644"),
    })
    install_overrides(image=output, group="bellatrix", replacements={
        "/etc/upstart/tzd.conf": ("tzd.conf", "0100644"),
        "/etc/upstart/registrationd.conf": ("registrationd.conf", "0100644"),
        **{
            f"/etc/upstart/{service}.conf": (
                "qemu-disabled-service.conf", "0100644",
            )
            for service in (
                "minerva_service", "minervad", "wmt", "wifid", "wifim", "wifis",
            )
        },
    })
    if waveform is not None:
        run_many(output, [
            "mkdir /data/init_bin",
            "set_inode_field /data/init_bin mode 040755",
        ], writable=True)
        replace_file(output, waveform, "/data/init_bin/wf_lut.gz", "0100644")
