"""Build a compact Forma eMMC from the live-device partition dumps."""
from __future__ import annotations

import shutil
import struct
import subprocess
import zlib
from pathlib import Path

from . import rootfs
from .common import atomic_output

DISK_SIZE = 2 * 1024**3
ROOT_START = 49152
RECOVERY_START = 573441
USER_START = 1097730
ENV_OFFSET = 768 * 1024
ENV_SIZE = 8192


def boot_environment(region: bytes, *, sideloaded: bool) -> bytes:
    """Keep the vendor boot commands, adding an opt-in userspace boot hook."""
    env = region[ENV_OFFSET:ENV_OFFSET + ENV_SIZE]
    if len(env) != ENV_SIZE or zlib.crc32(env[4:]) != struct.unpack_from('<I', env)[0]:
        raise ValueError('Forma boot region has an invalid U-Boot environment')
    entries = dict(item.split(b'=', 1) for item in env[4:].split(b'\0\0', 1)[0].split(b'\0'))
    if sideloaded:
        entries[b'mmcargs'] += b' eink.sideloaded=1'
    data = b'\0'.join(key + b'=' + value for key, value in entries.items()) + b'\0\0'
    if len(data) > ENV_SIZE - 4:
        raise ValueError('Forma U-Boot environment is too large')
    data = data.ljust(ENV_SIZE - 4, b'\0')
    return struct.pack('<I', zlib.crc32(data)) + data


def write_userstore(disk) -> None:
    """Write a plain FAT32 p3, keeping the on-device partition start."""
    sectors = DISK_SIZE // 512 - USER_START
    cluster_sectors, reserved = 8, 32
    fat_sectors = 1
    while True:
        clusters = (sectors - reserved - 2 * fat_sectors) // cluster_sectors
        needed = (clusters + 2 + 127) // 128
        if needed <= fat_sectors:
            break
        fat_sectors = needed
    boot = bytearray(512)
    boot[:11] = b'\xeb\x58\x90MSDOS5.0'
    struct.pack_into('<HBHBHHBHHHII', boot, 11, 512, cluster_sectors, reserved,
                     2, 0, 0, 0xf8, 0, 63, 255, USER_START, sectors)
    struct.pack_into('<IHHIHH', boot, 36, fat_sectors, 0, 0, 2, 1, 6)
    boot[64:67] = b'\x80\0\x29'
    struct.pack_into('<I', boot, 67, 0x464f524d)
    boot[71:82] = b'KOBOeReader'
    boot[82:90] = b'FAT32   '
    boot[510:] = b'\x55\xaa'
    info = bytearray(512)
    struct.pack_into('<I', info, 0, 0x41615252)
    struct.pack_into('<III', info, 484, 0x61417272, clusters - 1, 3)
    struct.pack_into('<I', info, 508, 0xaa550000)
    for sector, data in ((0, boot), (6, boot), (1, info), (7, info)):
        disk.seek((USER_START + sector) * 512)
        disk.write(data)
    for index in range(2):
        disk.seek((USER_START + reserved + index * fat_sectors) * 512)
        disk.write(struct.pack('<III', 0xffffff8, 0xffffffff, 0xfffffff))


def prepare_root(source: Path, output: Path) -> None:
    rootfs.copy_source(source, output, maximum_size=(RECOVERY_START - ROOT_START) * 512)
    # Recover the journal from the live dump before changing any inodes.
    result = subprocess.run([str(rootfs.find_debugfs().with_name('e2fsck')),
                             '-p', str(output)], check=False)
    if result.returncode not in (0, 1):
        raise ValueError('Could not recover the Forma root filesystem')
    rootfs.run(output, 'rm /etc/udev.tgz', writable=True)
    rootfs.install_overrides(image=output, group='forma', replacements={
        '/etc/init.d/eink-sideloaded': ('etc/init.d/eink-sideloaded', '0100755'),
    })
    marker = '/etc/init.d/eink-sideloaded\n'
    def patch_startup(contents: str) -> str:
        needle = '/usr/local/Kobo/hindenburg &'
        if contents.count(needle) != 1:
            raise ValueError('Unrecognized Forma rcS: expected one Hindenburg launch')
        return contents.replace(needle, marker + needle)
    rootfs.transform_file(output, '/etc/init.d/rcS', '0100755', patch_startup)
    rootfs.transform_file(output, '/etc/passwd', '0100644', rootfs.blank_root_password)


def build(output: Path, artifacts: dict[str, Path], *, sideloaded: bool = False) -> None:
    region = artifacts['boot_region'].read_bytes()
    if len(region) != ROOT_START * 512 or region[510:512] != b'\x55\xaa':
        raise ValueError('Forma requires the complete 24 MiB boot-region dump')
    for index, expected in enumerate((ROOT_START, RECOVERY_START, USER_START)):
        if struct.unpack_from('<I', region, 446 + 16 * index + 8)[0] != expected:
            raise ValueError('Unexpected Forma partition layout')
    prepared = output.with_name('prepared-rootfs.img')
    prepare_root(artifacts['rootfs'], prepared)
    with atomic_output(output) as staging, staging.open('wb') as disk:
        disk.truncate(DISK_SIZE)
        disk.write(region)
        disk.seek(ENV_OFFSET)
        disk.write(boot_environment(region, sideloaded=sideloaded))
        disk.seek(446 + 2 * 16 + 12)
        disk.write(struct.pack('<I', DISK_SIZE // 512 - USER_START))
        for source, start, limit in ((prepared, ROOT_START, RECOVERY_START),
                                     (artifacts['recoveryfs'], RECOVERY_START, USER_START)):
            if source.stat().st_size > (limit - start) * 512:
                raise ValueError(f'{source.name} does not fit its Forma partition')
            disk.seek(start * 512)
            with source.open('rb') as stream:
                shutil.copyfileobj(stream, disk)
        write_userstore(disk)
