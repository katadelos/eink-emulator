"""Pack a Scribe waveform partition as a standalone FAT32 image.

The factory loader reads waveform_to_use/*.wrf.gz directly. OTA WF01/SP01
wrappers are installation containers and must not be put around this file.
"""
from __future__ import annotations

import argparse
import gzip
import struct
from pathlib import Path

SECTOR = 512
EOC = 0x0FFFFFFF


def directory_entry(name: bytes, attribute: int, cluster: int, size: int) -> bytes:
    if len(name) != 11:
        raise ValueError("FAT short names require exactly eleven bytes")
    entry = bytearray(32)
    entry[:11] = name
    entry[11] = attribute
    struct.pack_into("<H", entry, 16, 0x21)  # 1980-01-01, deterministic
    struct.pack_into("<H", entry, 18, 0x21)
    struct.pack_into("<H", entry, 20, cluster >> 16)
    struct.pack_into("<H", entry, 24, 0x21)
    struct.pack_into("<HI", entry, 26, cluster & 0xFFFF, size)
    return bytes(entry)


def long_entry(name: str, short: bytes, attribute: int,
               cluster: int, size: int = 0) -> bytes:
    """VFAT long-name entries followed by their matching short-name entry."""
    raw = name.encode("utf-16le")
    units = list(struct.unpack(f"<{len(raw) // 2}H", raw))
    if len(units) > 255 or any(c in name for c in '\\/:*?"<>|'):
        raise ValueError(f"invalid FAT filename: {name!r}")
    checksum = 0
    for char in short:
        checksum = (((checksum & 1) << 7) + (checksum >> 1) + char) & 255
    units.append(0)
    units.extend([0xFFFF] * (-len(units) % 13))
    count = len(units) // 13
    result = bytearray()
    for index in range(count, 0, -1):
        entry = bytearray(32)
        entry[0] = index | (0x40 if index == count else 0)
        entry[11] = 0x0F
        entry[13] = checksum
        chars = units[(index - 1) * 13:index * 13]
        struct.pack_into("<5H", entry, 1, *chars[:5])
        struct.pack_into("<6H", entry, 14, *chars[5:11])
        struct.pack_into("<2H", entry, 28, *chars[11:])
        result.extend(entry)
    result.extend(directory_entry(short, attribute, cluster, size))
    return bytes(result)


def build(output: Path, waveform: Path, *, size_mib: int = 64,
          partition_start: int = 0,
          volume_label: str = "CS8 WAVEFRM") -> dict[str, int | str]:
    label = volume_label.encode("ascii")
    if len(label) != 11 or any(c < 32 or c > 126 for c in label):
        raise ValueError("FAT volume label must contain eleven ASCII characters")
    if not waveform.name.endswith(".wrf.gz"):
        raise ValueError("stock loader requires a .wrf.gz filename")
    payload = waveform.read_bytes()
    raw = gzip.decompress(payload)  # includes the gzip CRC/ISIZE checks
    if not raw:
        raise ValueError("empty decompressed waveform")
    if output.resolve() == waveform.resolve():
        raise ValueError("output must differ from the waveform file")
    sectors = size_mib * 1024**2 // SECTOR
    reserved, fats = 32, 2
    # One sector per cluster keeps a 64 MiB image above FAT32's 65525-cluster
    # threshold. Solve FAT size including its own space and reserved entries.
    fat_sectors = 1
    while True:
        clusters = sectors - reserved - fats * fat_sectors
        required = (clusters + 2 + 127) // 128
        if required <= fat_sectors:
            break
        fat_sectors = required
    if not 65525 <= clusters < 0x0FFFFFF5:
        raise ValueError("size is outside FAT32's valid cluster range")
    count = (len(payload) + SECTOR - 1) // SECTOR
    allocated = count + 2  # root directory, waveform_to_use, payload
    if allocated > clusters:
        raise ValueError("waveform does not fit in the partition")

    boot = bytearray(SECTOR)
    boot[:3] = b"\xeb\x58\x90"
    boot[3:11] = b"EINKEMU "
    struct.pack_into("<HBHBHHBHHHII", boot, 11, SECTOR, 1, reserved, fats,
                     0, 0, 0xF8, 0, 63, 255, partition_start, sectors)
    struct.pack_into("<IHHIHH", boot, 36, fat_sectors, 0, 0, 2, 1, 6)
    boot[64:67] = b"\x80\0\x29"
    struct.pack_into("<I", boot, 67, 0x43533857)
    boot[71:82] = label
    boot[82:90] = b"FAT32   "
    boot[510:512] = b"\x55\xaa"
    info = bytearray(SECTOR)
    struct.pack_into("<I", info, 0, 0x41615252)
    struct.pack_into("<I", info, 484, 0x61417272)
    struct.pack_into("<II", info, 488, clusters - allocated, allocated + 2)
    struct.pack_into("<I", info, 508, 0xAA550000)
    fat = bytearray(fat_sectors * SECTOR)
    struct.pack_into("<4I", fat, 0, 0x0FFFFFF8, EOC, EOC, EOC)
    for cluster in range(4, 4 + count):
        struct.pack_into("<I", fat, cluster * 4,
                         cluster + 1 if cluster < 3 + count else EOC)
    root = directory_entry(label, 8, 0, 0)
    root += long_entry("waveform_to_use", b"WAVEFO~1   ", 0x10, 3)
    # This is the stock successful-install marker. Never set WFM_DIRTY_FLAG.
    root += long_entry("DONT_ERASE_WFM", b"DONT_E~1   ", 0x20, 0)
    directory = directory_entry(b".          ", 0x10, 3, 0)
    directory += directory_entry(b"..         ", 0x10, 0, 0)
    directory += long_entry(waveform.name, b"CS8SYN~1GZ ", 0x20, 4, len(payload))
    if len(root) >= SECTOR or len(directory) >= SECTOR:
        raise ValueError("directory entries exceed one cluster")
    data_start = reserved + fats * fat_sectors
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("wb") as stream:
        stream.truncate(sectors * SECTOR)
        for sector, data in ((0, boot), (1, info), (6, boot), (7, info),
                             (reserved, fat), (reserved + fat_sectors, fat),
                             (data_start, root), (data_start + 1, directory),
                             (data_start + 2, payload)):
            stream.seek(sector * SECTOR)
            stream.write(data)
    return {"image": str(output), "bytes": sectors * SECTOR,
            "waveform": f"/waveform_to_use/{waveform.name}",
            "compressed_bytes": len(payload), "raw_bytes": len(raw),
            "fat_sectors": fat_sectors, "clusters": clusters}


def main() -> None:
    import json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("waveform", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--size-mib", type=int, default=64)
    parser.add_argument("--partition-start", type=int, default=0,
                        help="partition start LBA for the FAT hidden-sector field")
    args = parser.parse_args()
    print(json.dumps(build(args.output, args.waveform, size_mib=args.size_mib,
                           partition_start=args.partition_start), indent=2))


if __name__ == "__main__":
    main()
