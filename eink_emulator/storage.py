"""Track shared disk dependencies and serialize storage changes."""

from __future__ import annotations

import fcntl
import json
import os
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


@contextmanager
def storage_lock(build_root: Path) -> Iterator[None]:
    build_root.mkdir(parents=True, exist_ok=True)
    with (build_root / "storage.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit("another storage operation is in progress; retry when it finishes")
        yield


def cached_bases(root: Path) -> list[Path]:
    # Symlinks may point into a development workspace; leave those alone.
    return sorted(
        path for path in (root / "build" / "images").glob("*.qcow2")
        if not path.is_symlink() and path.is_file()
    )


def disk_info(qemu_img: Path, path: Path) -> dict:
    return json.loads(subprocess.check_output(
        [str(qemu_img), "info", "--output=json", str(path)], text=True,
    ))


def base_families(
    root: Path, qemu_img: Path, *, model: str | None = None,
) -> dict[tuple[str, int], list[Path]]:
    """Group standalone bases by model and disk size, oldest first.

    Every revision layers directly on a standalone base, keeping chains bounded
    at machine -> prepared revision -> shared base.
    """
    families: dict[tuple[str, int], list[tuple[str, Path]]] = {}
    for path in cached_bases(root):
        try:
            metadata = json.loads(path.with_suffix(".json").read_text())
        except FileNotFoundError:
            # An interrupted build may not have published its metadata yet.
            continue
        if model is not None and metadata["model"] != model:
            continue
        info = disk_info(qemu_img, path)
        if info.get("backing-filename"):
            continue
        # Rebuilding only the current disk contents would lose these features.
        data = info.get("format-specific", {}).get("data", {})
        if info.get("snapshots") or data.get("bitmaps") or data.get("data-file"):
            continue
        key = (metadata["model"], info["virtual-size"])
        families.setdefault(key, []).append((metadata["created"], path))
    return {key: [path for _, path in sorted(items)] for key, items in families.items()}


def write_base(
    qemu_img: Path, source: Path, source_format: str, destination: Path,
    *, backing: Path | None = None,
) -> None:
    """Atomically install a checked base, preserving all guest-visible bytes."""
    fd, name = tempfile.mkstemp(prefix=f".{destination.stem}-", suffix=".tmp", dir=destination.parent)
    os.close(fd)
    temporary = Path(name)

    def run(*arguments: str) -> None:
        subprocess.run([str(qemu_img), *arguments], check=True)

    try:
        if backing is None:
            run("convert", "-f", source_format, "-O", "qcow2", "-S", "4k", str(source), str(temporary))
        else:
            # Safe rebase of an empty overlay computes the differences between
            # source and backing. convert -b alone does NOT deduplicate them.
            run("create", "-q", "-f", "qcow2", "-F", source_format,
                "-b", str(source.resolve()), str(temporary))
            run("rebase", "-f", "qcow2", "-F", "qcow2",
                "-b", os.path.relpath(backing.resolve(), destination.parent.resolve()), str(temporary))
        run("check", "-q", "-f", "qcow2", str(temporary))
        run("compare", "-q", "-f", source_format, "-F", "qcow2", str(source), str(temporary))
        if destination.exists():
            if source == destination and temporary.stat().st_blocks >= destination.stat().st_blocks:
                return
            if open_files([destination]):
                raise SystemExit(f"base is in use; stop its machines before compacting: {destination}")
        temporary.chmod(0o444)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


def image_references(root: Path, qemu_img: Path, *, excluding: Path | None = None) -> set[Path]:
    """Find dependencies of saved machines and other QCOW2 disks in the workspace.

    Inspect the actual backing chains, including snapshots and development disks,
    rather than assuming that machine manifests describe every dependency.
    Complete the entire inventory before allowing any deletion.
    """
    bases = set(cached_bases(root))
    roots = open_files(sorted(bases))
    visited: set[Path] = set()

    def walk_error(error: OSError) -> None:
        raise error

    for directory, children, names in os.walk(root, onerror=walk_error, followlinks=True):
        parent = Path(directory)
        resolved = parent.resolve()
        if resolved in visited or resolved == excluding:
            children.clear()
            continue
        visited.add(resolved)
        children[:] = [
            name for name in children
            if name != ".git" and (
                not (parent / name).is_symlink() or (parent / name).resolve().is_relative_to(root)
            )
        ]
        for name in names:
            path = parent / name
            if path == excluding:
                continue
            if name == "machine.json" and (
                parent.is_relative_to(root / "machines") or "disk.qcow2" in names
            ):
                try:
                    manifest = json.loads(path.read_text())
                    base = manifest["base"]
                    if not isinstance(base, str) or not base:
                        raise ValueError("base must be a nonempty path")
                    roots.add(root / base)
                except (OSError, ValueError, KeyError, TypeError) as error:
                    raise SystemExit(f"cannot inventory machine manifest {path}: {error}")
            elif path.suffix.lower() in {".qcow2", ".qcow", ".img", ".raw"} and path not in bases:
                # Some raw firmware images use these extensions too.
                if path.is_symlink() and not path.exists():
                    continue
                with path.open("rb") as source:
                    if source.read(4) == b"QFI\xfb":
                        roots.add(path)

    references: set[Path] = set()
    for path in sorted(roots):
        result = subprocess.run(
            [str(qemu_img), "info", "-U", "--output=json", "--backing-chain", str(path)],
            text=True, capture_output=True,
        )
        if result.returncode:
            raise SystemExit(f"cannot inspect backing chain for {path}: {result.stderr.strip()}")
        try:
            chain = json.loads(result.stdout)
            for entry in chain:
                references.add(Path(entry["filename"]).resolve())
        except (ValueError, KeyError, TypeError) as error:
            raise SystemExit(f"invalid backing chain for {path}: {error}")
    return references


def open_files(paths: list[Path]) -> set[Path]:
    """Protect disks opened directly by QEMU or another process, even outside machines/."""
    if not paths:
        return set()
    probe = Path(__file__).resolve()
    try:
        # A restricted process view can look like "nothing is open". Verify
        # that lsof can at least see a file held open by this process.
        with probe.open("rb"):
            result = subprocess.run(
                ["lsof", "-Fn", "--", str(probe), *(str(path) for path in paths)],
                text=True, capture_output=True,
            )
    except FileNotFoundError:
        raise SystemExit("lsof is required to check for disks in use before deleting images")
    if result.returncode not in {0, 1} or result.stderr.strip():
        raise SystemExit(f"cannot check for open disks: {result.stderr.strip()}")
    opened = {Path(line[1:]).resolve() for line in result.stdout.splitlines() if line.startswith("n")}
    if probe not in opened:
        raise SystemExit("cannot check for open disks: lsof cannot inspect this process; run outside the restricted sandbox")
    return opened - {probe}


def unused_bases(root: Path, references: set[Path]) -> list[Path]:
    return [path for path in cached_bases(root) if path.resolve() not in references]
