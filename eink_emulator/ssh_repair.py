"""Authorize the host login key in a standalone copy of a stopped guest disk."""

from __future__ import annotations

import os
import re
import struct
import subprocess
import tempfile
from pathlib import Path

from .images import rootfs
from .ssh import ensure_login_key


def partitions(raw: Path) -> list[tuple[int, int]]:
    """Read the 512-byte-sector GPT or primary MBR partitions used by guests."""
    size = raw.stat().st_size
    with raw.open('rb') as disk:
        mbr = disk.read(512)
        header = disk.read(512)
        if mbr[510:512] != b'\x55\xaa':
            raise ValueError('disk has no supported partition table')
        extents = []
        if header[:8] == b'EFI PART':
            table, count, stride = struct.unpack_from('<QII', header, 72)
            if not 128 <= stride <= 4096 or not 1 <= count <= 4096 or table * 512 + count * stride > size:
                raise ValueError('invalid GPT partition table')
            disk.seek(table * 512)
            for _ in range(count):
                entry = disk.read(stride)
                if entry[:16] != bytes(16):
                    first, last = struct.unpack_from('<QQ', entry, 32)
                    extents.append((first * 512, (last - first + 1) * 512))
        else:
            for index in range(4):
                entry = mbr[446 + index * 16:462 + index * 16]
                if entry[4] in {0x05, 0x0f, 0x85, 0xee}:
                    raise ValueError('unsupported MBR partition type')
                if entry[4]:
                    first, count = struct.unpack_from('<II', entry, 8)
                    extents.append((first * 512, count * 512))
    for offset, length in extents:
        if offset < 512 or length <= 0 or offset + length > size:
            raise ValueError('partition extends outside the disk')
    return extents


def copy_bytes(source, target, length: int) -> None:
    while length:
        chunk = source.read(min(length, 8 * 1024 * 1024))
        if not chunk:
            raise ValueError('unexpected end of disk partition')
        target.write(chunk)
        length -= len(chunk)


def repair_disk(qemu_img: Path, source: Path, destination: Path) -> None:
    """Write a new cold-boot disk; never modify a backing image or saved RAM."""
    if destination.exists():
        raise ValueError(f'destination already exists: {destination}')
    debugfs = rootfs.find_debugfs()
    public_key = ensure_login_key().read_bytes()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.ssh-repair-', dir=destination.parent) as temporary:
        work = Path(temporary)
        raw, partition = work / 'disk.raw', work / 'rootfs.img'
        # QEMU refuses a disk currently opened for writing. Flatten backing
        # chains into our copy, so sibling instances retain their own identity.
        subprocess.run([str(qemu_img), 'convert', '-f', 'qcow2', '-O', 'raw',
                        str(source), str(raw)], check=True)
        matches = []
        for offset, length in partitions(raw):
            with raw.open('rb') as disk:
                disk.seek(offset + rootfs.EXT_MAGIC_OFFSET)
                if disk.read(2) != b'\x53\xef':
                    continue
                disk.seek(offset)
                with partition.open('wb') as target:
                    copy_bytes(disk, target, length)
            if rootfs.file_exists(partition, '/etc/eink-ssh/authorized_keys'):
                matches.append((offset, length))
                partition.replace(work / 'selected.img')
        if len(matches) != 1:
            raise ValueError(f'expected one rootfs with /etc/eink-ssh/authorized_keys; found {len(matches)}')
        partition = work / 'selected.img'
        (work / 'login.pub').write_bytes(public_key)
        commands = ['rm /etc/eink-ssh/authorized_keys',
                    'write login.pub /etc/eink-ssh/authorized_keys']
        for path, mode in (('/etc/eink-ssh', '040700'),
                           ('/etc/eink-ssh/authorized_keys', '0100600')):
            commands.extend(f'set_inode_field {path} {field} {value}'
                            for field, value in (('mode', mode), ('uid', '0'), ('gid', '0')))
        (work / 'commands').write_text('\n'.join(commands) + '\n')
        subprocess.run([str(debugfs), '-w', '-f', 'commands', 'selected.img'],
                       cwd=work, check=True, capture_output=True, text=True)
        # debugfs can return success after a failed command. Check its result.
        result = subprocess.run([str(debugfs), '-R', 'cat /etc/eink-ssh/authorized_keys',
                                 str(partition)], check=True, capture_output=True)
        if result.stdout != public_key:
            raise ValueError('failed to install the SSH public key')
        for path, mode in (('/etc/eink-ssh', '0700'), ('/etc/eink-ssh/authorized_keys', '0600')):
            result = subprocess.run([str(debugfs), '-R', f'stat {path}', str(partition)],
                                    check=True, capture_output=True, text=True)
            if not re.search(rf'Mode:\s+{mode}\b', result.stdout) or not re.search(
                r'User:\s+0\s+Group:\s+0\b', result.stdout
            ):
                raise ValueError(f'failed to set SSH permissions on {path}')
        offset, length = matches[0]
        with raw.open('r+b') as disk, partition.open('rb') as patched:
            disk.seek(offset)
            copy_bytes(patched, disk, length)
        output = work / 'disk.qcow2'
        subprocess.run([str(qemu_img), 'convert', '-f', 'raw', '-O', 'qcow2',
                        str(raw), str(output)], check=True)
        # Publish without replacing an output created while conversion ran.
        os.link(output, destination)
