#!/usr/bin/env python3
"""Extract Amaro firmware from a PW7 partition-dump tar archive."""

from __future__ import annotations

import argparse
import shutil
import struct
import sys
import tarfile
import tempfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from eink_emulator.firmware import validate_rootfs_package


def fit(data: bytes, offset: int = 0) -> bytes:
    if len(data) < offset + 40:
        raise ValueError("missing FIT header")
    magic, size = struct.unpack_from(">II", data, offset)
    if magic != 0xD00DFEED or not 40 <= size <= len(data) - offset:
        raise ValueError("invalid FIT extent")
    return data[offset:offset + size]


def carve(package: Path, destination: Path) -> None:
    if destination.exists():
        raise SystemExit(f"firmware destination already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".pw7-import-", dir=destination.parent,
    ) as temporary:
        prepared = Path(temporary) / "prepared"
        prepared.mkdir()
        seen = set()
        with tarfile.open(package, "r|*") as archive:
            for member in archive:
                name = PurePosixPath(member.name).as_posix()
                if name not in {"0boot0.img", "p1.img", "p8.img"}:
                    continue
                if name in seen or not member.isfile():
                    raise ValueError(f"duplicate or non-file partition: {name}")
                seen.add(name)
                with archive.extractfile(member) as source:
                    if name == "p8.img":
                        if member.size != 1280 * 1024**2:
                            raise ValueError("Amaro rootfs must be 1280 MiB")
                        with (prepared / "rootfs.img").open("wb") as output:
                            shutil.copyfileobj(source, output, 8 * 1024**2)
                    elif name == "p1.img":
                        (prepared / "boot.img").write_bytes(fit(source.read()))
                    else:
                        boot = source.read()
                        # MTK eMMC header, signed BL2, and the two inline FITs.
                        if boot[:9] != b"EMMC_BOOT" or len(boot) < 183296:
                            raise ValueError("unrecognized Amaro boot area")
                        (prepared / "bl2.img").write_bytes(boot[:183296])
                        (prepared / "u-boot.bin").write_bytes(fit(boot, 0x80000))
                        (prepared / "tee.img").write_bytes(fit(boot, 0x180000))
        missing = {"0boot0.img", "p1.img", "p8.img"} - seen
        if missing:
            raise ValueError("missing partitions: " + ", ".join(sorted(missing)))
        validate_rootfs_package(prepared / "rootfs.img", "com.lab126.eink.amaro.os")
        prepared.replace(destination)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dump", type=Path)
    parser.add_argument("--output", type=Path,
                        default=ROOT / "firmware/kindle-paperwhite-7")
    args = parser.parse_args()
    carve(args.dump.resolve(), args.output.resolve())
    print(f"PW7 firmware: {args.output.resolve()}")


if __name__ == "__main__":
    main()
