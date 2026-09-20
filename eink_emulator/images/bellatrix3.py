"""Compose Barolo/Pisco storage with development changes in a temporary rootfs."""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

from . import bellatrix, bellatrix_waveform, rootfs, scribe_waveform_partition

MIB = 1024**2
ROOTFS_SIZE = 768 * MIB
BOARDS = {"barolo", "pisco"}

# Stock platform_variables fixes keys=p3, pdata=p5, root=p8, local=p9,
# user=p10 and hibernate metadata=p7. Recovery fixes kernel=p1 and wfm=p2.
# U-Boot resolves snapshot by name, and recovery clears p6 on factory reset.
# Factory byte geometry and p4's purpose are unpublished: p4 is deliberately
# an unused emulator reservation, not a fabricated diagnostics filesystem.
PARTITIONS = [
    ("kernel", 64 * MIB),
    ("wfm", 64 * MIB),
    ("keys", 16 * MIB),
    ("reserved4", 64 * MIB),
    ("pdata", 128 * MIB),
    ("snapshot", 1024 * MIB),
    ("miscdata", 512 * MIB),
    ("rootfs", ROOTFS_SIZE),
    ("varlocal", 512 * MIB),
]


def initialize_persistent_filesystems(
    image: Path, layout: dict[str, tuple[int, int]], original_rootfs: Path,
) -> None:
    """Do the stock first-boot mkfs work on the host, before installing keys.

    filesystems_pdata.conf uses ext3/pdata. varlocal_functions_ext4 uses
    ext4, encrypt, 4 KiB blocks and 16 KiB/inode. Read the shipped formatter
    configuration so host e2fsprogs does not enable newer kernel features.
    """
    config = subprocess.run(
        [str(rootfs.find_debugfs()), "-R", "cat /etc/mke2fs.conf", str(original_rootfs)],
        check=True, capture_output=True, text=True,
    ).stdout
    if "[defaults]" not in config or "[fs_types]" not in config:
        raise ValueError("original Bellatrix3 mke2fs configuration is missing")
    with tempfile.TemporaryDirectory(prefix=".bellatrix3-persistent-", dir=image.parent) as temporary:
        work = Path(temporary)
        config_path = work / "mke2fs.conf"
        config_path.write_text(config)
        environment = {**os.environ, "MKE2FS_CONFIG": str(config_path)}
        seed = work / "varlocal-seed"
        (seed / "metadata").mkdir(parents=True)
        # This is the exact post-mkfs state in filesystems_var_local.conf.
        # Empty metadata permits fenc to install its policy normally, then
        # NEW_VAR_LOCAL requests the real stock /opt/var/local restoration.
        (seed / "NEW_VAR_LOCAL").touch()
        for name, filesystem_type, label in (
            ("pdata", "ext3", "pdata"), ("varlocal", "ext4", "LocalVars"),
        ):
            filesystem = work / (name + ".img")
            with filesystem.open("wb") as output:
                output.truncate(layout[name][1] * 512)
            command = [
                bellatrix.find_tool("mke2fs"), "-q", "-F", "-t", filesystem_type,
                "-L", label, "-E", "lazy_itable_init=0,lazy_journal_init=0",
            ]
            if name == "varlocal":
                command.extend(["-i", "16384", "-b", "4096", "-O", "encrypt", "-d", str(seed)])
            command.append(str(filesystem))
            subprocess.run(command, check=True, env=environment)
            subprocess.run(
                [bellatrix.find_tool("tune2fs"), "-c", "0", "-i", "0", str(filesystem)],
                check=True, stdout=subprocess.DEVNULL,
            )
            if name == "varlocal":
                # mke2fs -d otherwise imports the host developer's uid/gid.
                rootfs.run_many(filesystem, [
                    "set_inode_field /metadata uid 0",
                    "set_inode_field /metadata gid 0",
                    "set_inode_field /metadata mode 040755",
                    "set_inode_field /NEW_VAR_LOCAL uid 0",
                    "set_inode_field /NEW_VAR_LOCAL gid 0",
                    "set_inode_field /NEW_VAR_LOCAL mode 0100644",
                ], writable=True)
            bellatrix.write_partition(image, layout, name, filesystem)


def build(
    image: Path, *, board: str, boot_image: Path, rootfs_image: Path,
    size: int = 8 * 1024**3,
) -> None:
    if board not in BOARDS:
        raise ValueError(f"unsupported Bellatrix3 board: {board}")
    for payload in (boot_image, rootfs_image):
        if not payload.is_file():
            raise ValueError(f"missing {board} firmware: {payload}")
    if rootfs_image.stat().st_size != ROOTFS_SIZE:
        raise ValueError("Bellatrix3 requires the original 768 MiB rootfs image")
    if size % 512 or size < 4 * 1024**3:
        raise ValueError("Bellatrix3 disk must be sector-aligned and at least 4 GiB")

    layout = bellatrix.create_image(
        image, size, partitions=PARTITIONS, namespace=f"bellatrix3-{board}",
    )
    bellatrix.write_partition(image, layout, "kernel", boot_image)
    fixture = bellatrix_waveform.write_waveform(
        image.parent / "synthetic-waveform", product=board,
    )
    with tempfile.TemporaryDirectory(
        prefix=".bellatrix3-waveform-", dir=image.parent,
    ) as temporary:
        waveform_partition = Path(temporary) / "waveform.img"
        scribe_waveform_partition.build(
            waveform_partition, fixture, partition_start=layout["wfm"][0],
            volume_label="SCRIBE WFM ",
        )
        bellatrix.write_partition(image, layout, "wfm", waveform_partition)
    # Keep imported firmware immutable and discard the prepared copy as soon
    # as it has been embedded. Public CLI and local bring-up use this same path.
    with tempfile.TemporaryDirectory(
        prefix=".bellatrix3-rootfs-", dir=image.parent,
    ) as temporary:
        prepared = Path(temporary) / "rootfs.img"
        rootfs.prepare_bellatrix3(
            rootfs_image, prepared, board=board, waveform=fixture,
        )
        bellatrix.write_partition(image, layout, "rootfs", prepared)
    initialize_persistent_filesystems(image, layout, rootfs_image)
    # /keys is intentionally empty: DHAv2-optee skips that mount.
    # The stock dual-filesystem userstore probe accepts this ext4 layout.
    # Falcon advertises discard without guaranteed discard-zeroes. Eager
    # initialization writes real inode-table zeros here, avoiding Linux 4.9's
    # loop-device lazy-init discard optimization and its EOPNOTSUPP errors.
    bellatrix.create_ext4_userstore(image, layout, eager_inode_init=True)
