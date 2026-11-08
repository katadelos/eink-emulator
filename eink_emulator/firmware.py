"""Import vendor firmware packages into the local firmware catalogue."""

from __future__ import annotations

import gzip
import shutil
import struct
import subprocess
import tarfile
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any


def carve_ao5_dump(
    package: Path, destination: Path, *, rootfs_size: int,
    rootfs_package: str, quickboot: bool = False, waveform: bool = False,
) -> None:
    """Extract stock Amaro/Julep images without importing device data."""
    def fit(data: bytes, offset: int = 0) -> bytes:
        if len(data) < offset + 40:
            raise ValueError("missing FIT header")
        magic, size = struct.unpack_from(">II", data, offset)
        if magic != 0xD00DFEED or not 40 <= size <= len(data) - offset:
            raise ValueError("invalid FIT extent")
        return data[offset:offset + size]

    if destination.exists():
        raise SystemExit(f"firmware destination already exists: {destination}")
    required = {"0boot0.img", "p1.img", "p8.img"}
    if quickboot:
        required.add("0boot1.img")
    if waveform:
        required.add("p2.img")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=f".{destination.name}-import-", dir=destination.parent,
    ) as temporary:
        prepared = Path(temporary) / "prepared"
        prepared.mkdir()
        seen = set()
        with tarfile.open(package, "r|*") as archive:
            for member in archive:
                name = PurePosixPath(member.name).as_posix()
                if name not in required:
                    continue
                if name in seen or not member.isfile():
                    raise ValueError(f"duplicate or non-file partition: {name}")
                seen.add(name)
                with archive.extractfile(member) as source:
                    if name in {"p8.img", "p2.img"}:
                        expected = rootfs_size if name == "p8.img" else 16 * 1024**2
                        output_name = "rootfs.img" if name == "p8.img" else "waveform.img"
                        if member.size != expected:
                            raise ValueError(f"{name} must be {expected // 1024**2} MiB")
                        with (prepared / output_name).open("wb") as output:
                            shutil.copyfileobj(source, output, 8 * 1024**2)
                    elif name == "p1.img":
                        (prepared / "boot.img").write_bytes(fit(source.read()))
                    elif name == "0boot1.img":
                        (prepared / "quickboot.img").write_bytes(fit(source.read(), 0x80000))
                    else:
                        boot = source.read()
                        # MTK eMMC header, signed BL2, and the two inline FITs.
                        if boot[:9] != b"EMMC_BOOT" or len(boot) < 183296:
                            raise ValueError("unrecognized AO5 boot area")
                        (prepared / "bl2.img").write_bytes(boot[:183296])
                        (prepared / "u-boot.bin").write_bytes(fit(boot, 0x80000))
                        (prepared / "tee.img").write_bytes(fit(boot, 0x180000))
        missing = required - seen
        if missing:
            raise ValueError("missing partitions: " + ", ".join(sorted(missing)))
        validate_rootfs_package(prepared / "rootfs.img", rootfs_package)
        prepared.replace(destination)


def import_recovery(
    *,
    package: Path,
    destination: Path,
    definition: dict[str, Any],
) -> dict[str, Path]:
    """Extract and atomically install a model's Kindle recovery artifacts."""
    kindletool = shutil.which("kindletool")
    if not kindletool:
        raise SystemExit("kindletool is required to import Kindle recovery firmware")
    if not package.is_file():
        raise SystemExit(f"firmware package does not exist: {package}")
    if destination.exists():
        raise SystemExit(f"firmware destination already exists: {destination}")

    import_spec = definition.get("recovery_import")
    if not isinstance(import_spec, dict):
        raise SystemExit("this model does not support recovery-package import")

    required = definition.get("firmware", {})
    rootfs_extract = definition.get("rootfs_extract", {})
    if set(import_spec) & set(rootfs_extract):
        raise SystemExit("recovery and rootfs extraction roles overlap")
    if set(import_spec) | set(rootfs_extract) != set(required):
        raise SystemExit("recovery import does not provide every required artifact")
    for role, candidates in required.items():
        if not isinstance(candidates, list) or len(candidates) != 1:
            raise SystemExit(f"recovery import requires one output name for {role}")

    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=f".{destination.name}-import-", dir=destination.parent
    ) as temporary:
        workspace = Path(temporary)
        extracted = workspace / "extracted"
        prepared = workspace / "prepared"
        extracted.mkdir()
        prepared.mkdir()

        subprocess.run(
            [kindletool, "extract", str(package), str(extracted)],
            check=True,
        )

        installed: dict[str, Path] = {}
        for role, relative_source in import_spec.items():
            source = extracted / relative_source
            if not source.is_file():
                raise SystemExit(
                    f"recovery package is missing {role}: {relative_source}"
                )
            output_name = required[role][0]
            output = prepared / output_name
            output.parent.mkdir(parents=True, exist_ok=True)
            if source.suffix == ".gz" and output.suffix != ".gz":
                with gzip.open(source, "rb") as compressed, output.open("wb") as target:
                    shutil.copyfileobj(compressed, target)
            else:
                shutil.copy2(source, output)
            installed[role] = destination / output_name

        if rootfs_extract:
            extract_rootfs_firmware(prepared, definition)
            installed.update({
                role: destination / required[role][0] for role in rootfs_extract
            })

        if expected_package := definition.get("rootfs_package"):
            validate_rootfs_package(prepared / required["rootfs"][0], expected_package)

        prepared.replace(destination)
    return installed


def validate_rootfs_package(image: Path, expected: str) -> None:
    """Distinguish retail boards that share a recovery platform directory."""
    from .images.rootfs import run

    with tempfile.TemporaryDirectory(prefix="eink-firmware-identity-") as temporary:
        version = Path(temporary) / "version.txt"
        run(image, f"dump /etc/version.txt {version}")
        if not version.is_file() or expected not in version.read_text().splitlines():
            raise SystemExit(f"firmware rootfs does not identify the selected board ({expected})")


def extract_rootfs_firmware(directory: Path, definition: dict[str, Any]) -> None:
    """Read peripheral images without modifying the AVB-protected rootfs."""
    from .images.rootfs import run_many

    def quote(value: str) -> str:
        # debugfs has its own command parser; these are never shell commands.
        return '"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"'

    required = definition["firmware"]
    outputs = []
    commands = []
    for role, guest_path in definition["rootfs_extract"].items():
        output = directory / required[role][0]
        output.parent.mkdir(parents=True, exist_ok=True)
        commands.append(f"dump {quote(guest_path)} {quote(str(output.resolve()))}")
        outputs.append((role, guest_path, output))
    run_many(directory / required["rootfs"][0], commands)
    # debugfs can return success for a missing guest pathname.
    for role, guest_path, output in outputs:
        if not output.is_file() or not output.stat().st_size:
            raise SystemExit(f"rootfs is missing {role}: {guest_path}")
