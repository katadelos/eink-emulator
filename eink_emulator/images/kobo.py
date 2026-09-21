"""Prepare networking in Kobo's complete internal-SD firmware dumps."""
from __future__ import annotations

import shutil
import struct
import subprocess
from pathlib import Path

from . import rootfs
from .common import atomic_output


def prepare_network(image: Path) -> None:
    rootfs.install_overrides(image=image, group='kobo-network', replacements={
        '/etc/init.d/qemu-usb-network': ('qemu-usb-network', '0100755'),
    })

    def startup(contents: str) -> str:
        marker = 'PLATFORM=$PLATFORM /etc/init.d/qemu-usb-network\n'
        if marker in contents:
            return contents
        needle = '/usr/local/Kobo/hindenburg &'
        if contents.count(needle) != 1:
            raise ValueError('Unrecognized Kobo rcS: expected one Hindenburg launch')
        return contents.replace(needle, marker + needle)

    rootfs.transform_file(image, '/etc/init.d/rcS', '0100755', startup)
    rootfs.transform_file(image, '/etc/passwd', '0100644', rootfs.blank_root_password)


def build(source: Path, output: Path) -> None:
    """Keep the dumped partition layout and change only the prepared rootfs."""
    with source.open('rb') as disk:
        mbr = disk.read(512)
        if mbr[510:512] != b'\x55\xaa' or mbr[450] != 0x83:
            raise ValueError('Kobo SD image requires an ext rootfs in partition 1')
        start, sectors = struct.unpack_from('<II', mbr, 454)
        if (start + sectors) * 512 > source.stat().st_size:
            raise ValueError('Kobo rootfs partition lies outside its SD image')
        disk.seek(start * 512)
        prepared = output.with_name('prepared-rootfs.img')
        with prepared.open('wb') as root:
            remaining = sectors * 512
            while remaining:
                data = disk.read(min(8 * 1024 * 1024, remaining))
                if not data:
                    raise ValueError('Truncated Kobo rootfs partition')
                root.write(data)
                remaining -= len(data)
    result = subprocess.run([str(rootfs.find_debugfs().with_name('e2fsck')),
                             '-p', str(prepared)], check=False)
    if result.returncode not in (0, 1):
        raise ValueError('Could not recover the Kobo root filesystem')
    prepare_network(prepared)
    with atomic_output(output) as staging:
        # Preserve sparse zero regions without requiring another conversion.
        with source.open('rb') as original, staging.open('wb') as disk:
            while data := original.read(1024 * 1024):
                if data.strip(b'\0'):
                    disk.write(data)
                else:
                    disk.seek(len(data), 1)
            disk.truncate(source.stat().st_size)
            disk.seek(start * 512)
            with prepared.open('rb') as root:
                shutil.copyfileobj(root, disk)
