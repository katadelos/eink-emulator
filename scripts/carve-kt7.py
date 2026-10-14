#!/usr/bin/env python3
"""Carve the KT7 partition dump independently of update-package importing."""

from __future__ import annotations

import argparse
import json
import shutil
import struct
import sys
import tarfile
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from eink_emulator.firmware import extract_rootfs_firmware, validate_rootfs_package

MODEL = "kindle-basic-2026"
DUMP_IMPORT = {
    "bootloader": {"source": "boot0.img", "offset": 524288, "size": 715795},
    "bl2": {"source": "boot0.img", "offset": 0, "size": 183296},
    "tee": {"source": "boot0.img", "offset": 1572864, "size": 630803},
    "quickboot": {"source": "boot1.img", "offset": 524288, "size": 213197},
    "rootfs": "p8.img",
}


def carve_boot_image(source: Path, output: Path) -> None:
    """Extract the signed inline FIT at the start of a kernel partition."""
    with source.open("rb") as partition:
        header = partition.read(40)
        if len(header) != 40:
            raise SystemExit(f"kernel partition has no FIT header: {source}")
        magic, size = struct.unpack_from(">II", header)
        if magic != 0xD00DFEED or not 40 <= size <= source.stat().st_size:
            raise SystemExit(f"kernel partition has an invalid FIT extent: {source}")
        partition.seek(0)
        with output.open("wb") as image:
            remaining = size
            while remaining:
                chunk = partition.read(min(remaining, 8 * 1024 * 1024))
                if not chunk:
                    raise SystemExit(f"short read from kernel partition: {source}")
                image.write(chunk)
                remaining -= len(chunk)


def carve_dump(
    *, package: Path, destination: Path, definition: dict[str, Any],
    boot_image: Path,
) -> dict[str, Path]:
    """Carve the supplied KT7 dump into conventional firmware files."""
    if not package.is_file():
        raise SystemExit(f"firmware dump does not exist: {package}")
    if destination.exists():
        raise SystemExit(f"firmware destination already exists: {destination}")
    import_spec = definition.get("dump_import")
    required = definition.get("firmware", {})
    if not isinstance(import_spec, dict) or not import_spec or set(import_spec) - set(required):
        raise SystemExit("dump import contains undefined firmware artifacts")
    for role in import_spec:
        candidates = required[role]
        if not isinstance(candidates, list) or len(candidates) != 1:
            raise SystemExit(f"dump import requires one output name for {role}")
    sources: dict[str, list[tuple[str, int, int | None]]] = {}
    for role, source in import_spec.items():
        spec = {"source": source} if isinstance(source, str) else source
        offset, size = spec.get("offset", 0), spec.get("size")
        if not isinstance(offset, int) or offset < 0 or (
            size is not None and (not isinstance(size, int) or size <= 0)
        ):
            raise SystemExit(f"invalid dump image range for {role}")
        sources.setdefault(PurePosixPath(spec["source"]).as_posix(), []).append(
            (role, offset, size)
        )

    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=f".{destination.name}-import-", dir=destination.parent,
    ) as temporary:
        prepared = Path(temporary) / "prepared"
        prepared.mkdir()
        installed: dict[str, Path] = {}
        with tarfile.open(package, "r|*") as archive:
            for member in archive:
                roles = sources.get(PurePosixPath(member.name).as_posix())
                if roles is None:
                    continue
                if not member.isfile() or not member.size:
                    raise SystemExit(f"firmware dump artifact is not a regular image: {member.name}")
                for role, offset, size in roles:
                    if role in installed:
                        raise SystemExit(f"firmware dump contains duplicate {role}: {member.name}")
                    if offset + (size or member.size - offset) > member.size or offset >= member.size:
                        raise SystemExit(f"firmware dump image range exceeds {member.name}: {role}")
                with archive.extractfile(member) as source:
                    if len(roles) == 1 and roles[0][1:] == (0, None):
                        role = roles[0][0]
                        output = prepared / required[role][0]
                        output.parent.mkdir(parents=True, exist_ok=True)
                        with output.open("wb") as target:
                            shutil.copyfileobj(source, target, 8 * 1024 * 1024)
                    else:
                        # Shared boot partitions are small; spool once so FIT
                        # ranges can be read without seeking a compressed tar.
                        with tempfile.TemporaryFile(dir=prepared) as partition:
                            shutil.copyfileobj(source, partition, 8 * 1024 * 1024)
                            for role, offset, size in roles:
                                output = prepared / required[role][0]
                                output.parent.mkdir(parents=True, exist_ok=True)
                                partition.seek(offset)
                                remaining = size or member.size - offset
                                with output.open("wb") as target:
                                    while remaining:
                                        chunk = partition.read(min(remaining, 8 * 1024 * 1024))
                                        if not chunk:
                                            raise SystemExit(f"short read from firmware dump: {member.name}")
                                        target.write(chunk)
                                        remaining -= len(chunk)
                installed.update({role: destination / required[role][0] for role, _, _ in roles})
        missing = set(import_spec) - set(installed)
        if missing:
            raise SystemExit("firmware dump is missing: " + ", ".join(
                f"{role} ({import_spec[role]})" for role in sorted(missing)
            ))
        if rootfs_extract := definition.get("rootfs_extract"):
            extract_rootfs_firmware(prepared, definition)
            installed.update({role: destination / required[role][0] for role in rootfs_extract})
        output_name = required["boot_image"][0]
        carve_boot_image(boot_image, prepared / output_name)
        installed["boot_image"] = destination / output_name
        if expected_package := definition.get("rootfs_package"):
            validate_rootfs_package(prepared / required["rootfs"][0], expected_package)
        prepared.replace(destination)
    return installed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dump", type=Path, help="KT7 partition-dump tar archive")
    parser.add_argument("--boot-image", type=Path, required=True,
                        help="matching kernel partition containing the signed FIT")
    parser.add_argument("--output", type=Path, default=ROOT / "firmware" / MODEL,
                        help="new output directory (default: firmware/kindle-basic-2026)")
    args = parser.parse_args()
    if not args.boot_image.is_file():
        parser.error(f"kernel partition does not exist: {args.boot_image}")
    definition = json.loads((ROOT / "models.json").read_text())[MODEL]
    definition["dump_import"] = DUMP_IMPORT
    installed = carve_dump(package=args.dump.resolve(), destination=args.output.resolve(),
                           definition=definition, boot_image=args.boot_image.resolve())
    print(f"carved KT7 firmware into {args.output.resolve()}:")
    for role, path in installed.items():
        print(f"  {role}: {path}")


if __name__ == "__main__":
    main()
