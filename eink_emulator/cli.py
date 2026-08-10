"""Create, inventory, and launch persistent e-ink emulator machines."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .images import build_raw_image
from .qemu import build as build_qemu


ROOT = Path(__file__).resolve().parent.parent
CATALOGUE = ROOT / "models.json"
FIRMWARE_ROOT = ROOT / "firmware"
MACHINES_ROOT = ROOT / "machines"
BUILD_ROOT = ROOT / "build"
BASES_ROOT = BUILD_ROOT / "images"
QEMU_BUILD = ROOT / "qemu" / "build"
QEMU = QEMU_BUILD / "qemu-system-arm"
QEMU_IMG = QEMU_BUILD / "qemu-img"
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


def fail(message: str) -> None:
    raise SystemExit(message)


def load_catalogue() -> dict[str, dict[str, Any]]:
    try:
        value = json.loads(CATALOGUE.read_text())
    except (OSError, json.JSONDecodeError) as error:
        fail(f"cannot read model catalogue: {error}")
    if not isinstance(value, dict):
        fail("model catalogue must contain an object")
    return value


def model_definition(name: str) -> dict[str, Any]:
    catalogue = load_catalogue()
    try:
        return catalogue[name]
    except KeyError:
        fail(f"unknown model '{name}' (choose from: {', '.join(sorted(catalogue))})")


def validate_name(name: str) -> None:
    if not NAME_RE.fullmatch(name):
        fail("machine name must start with a lowercase letter or digit and contain only lowercase letters, digits, '-' or '_'")


def selected_artifacts(model: str, definition: dict[str, Any], *, required: bool) -> dict[str, Path]:
    group = "firmware" if required else "optional_firmware"
    directory = FIRMWARE_ROOT / model
    selected: dict[str, Path] = {}
    missing: list[str] = []
    for role, candidates in definition.get(group, {}).items():
        found = [directory / candidate for candidate in candidates if (directory / candidate).is_file()]
        if len(found) > 1:
            fail(f"multiple files supplied for {model} {role}: {', '.join(str(path) for path in found)}")
        if found:
            selected[role] = found[0]
        elif required:
            missing.append(" or ".join(str(directory / candidate) for candidate in candidates))
    if missing:
        fail("missing required firmware:\n  " + "\n  ".join(missing) + "\nSee docs/firmware.md.")
    return selected


def firmware_for(model: str, definition: dict[str, Any]) -> dict[str, Path]:
    return selected_artifacts(model, definition, required=True) | selected_artifacts(
        model, definition, required=False
    )


def digest_files(definition: dict[str, Any], artifacts: dict[str, Path]) -> str:
    digest = hashlib.sha256()
    digest.update(json.dumps(definition, sort_keys=True).encode())
    image_library = ROOT / "eink_emulator" / "images"
    for path in sorted(image_library.glob("*.py")):
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    overrides = ROOT / "guest-overrides" / definition["builder"]
    if overrides.is_dir():
        for path in sorted(path for path in overrides.rglob("*") if path.is_file()):
            digest.update(str(path.relative_to(overrides)).encode())
            digest.update(path.read_bytes())
    for role, path in sorted(artifacts.items()):
        digest.update(role.encode())
        digest.update(path.name.encode())
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(8 * 1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def run_checked(command: list[str], **kwargs: Any) -> None:
    subprocess.run(command, check=True, **kwargs)


def require_qemu_tools() -> None:
    if not QEMU.is_file() or not QEMU_IMG.is_file():
        print("QEMU is not built; building it now.")
        build_qemu()
    if not QEMU.is_file() or not QEMU_IMG.is_file():
        fail("QEMU build completed without the required executables")


def ensure_base(model: str, definition: dict[str, Any], artifacts: dict[str, Path]) -> tuple[Path, str]:
    fingerprint = digest_files(definition, artifacts)
    base = BASES_ROOT / f"{model}-{fingerprint[:16]}.qcow2"
    metadata = base.with_suffix(".json")
    if base.is_file() and metadata.is_file():
        return base, fingerprint

    require_qemu_tools()
    BASES_ROOT.mkdir(parents=True, exist_ok=True)
    staging_root = BUILD_ROOT / "tmp"
    staging_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f"{model}-", dir=staging_root) as temporary:
        raw = Path(temporary) / "disk.raw"
        converted = Path(temporary) / "disk.qcow2"
        source = build_raw_image(definition, artifacts, raw)
        run_checked([str(QEMU_IMG), "convert", "-f", "raw", "-O", "qcow2", "-S", "4k", str(source), str(converted)])
        run_checked([str(QEMU_IMG), "check", "-f", "qcow2", str(converted)])
        converted.replace(base)
    os.chmod(base, 0o444)
    write_json(metadata, {
        "created": datetime.now(timezone.utc).isoformat(),
        "firmware": {role: path.name for role, path in sorted(artifacts.items())},
        "fingerprint": fingerprint,
        "format": "qcow2",
        "model": model,
    })
    return base, fingerprint


def machine_directory(name: str) -> Path:
    validate_name(name)
    return MACHINES_ROOT / name


def command_create(args: argparse.Namespace) -> None:
    definition = model_definition(args.model)
    identity = parse_identity(args.idme, definition)
    artifacts = firmware_for(args.model, definition)
    target = machine_directory(args.name)
    if target.exists():
        fail(f"machine already exists: {args.name}")
    base, fingerprint = ensure_base(args.model, definition, artifacts)

    MACHINES_ROOT.mkdir(parents=True, exist_ok=True)
    temporary = MACHINES_ROOT / f".{args.name}.tmp-{os.getpid()}"
    temporary.mkdir()
    try:
        disk = temporary / "disk.qcow2"
        relative_base = os.path.relpath(base, temporary)
        run_checked([str(QEMU_IMG), "create", "-f", "qcow2", "-F", "qcow2", "-b", relative_base, str(disk)])
        write_json(temporary / "machine.json", {
            "base": str(base.relative_to(ROOT)),
            "created": datetime.now(timezone.utc).isoformat(),
            "firmware_fingerprint": fingerprint,
            "format": 1,
            "idme": identity,
            "model": args.model,
            "name": args.name,
        })
        temporary.replace(target)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    print(f"created {args.name} ({definition['description']})")
    print(f"run it with: ./eink run {args.name}")


def read_machine(name: str) -> tuple[Path, dict[str, Any]]:
    directory = machine_directory(name)
    manifest = directory / "machine.json"
    try:
        value = json.loads(manifest.read_text())
    except FileNotFoundError:
        fail(f"machine not found: {name}")
    except json.JSONDecodeError as error:
        fail(f"invalid machine manifest for {name}: {error}")
    return directory, value


def port(value: int) -> int:
    if not 1 <= value <= 65535:
        fail("SSH port must be between 1 and 65535")
    return value


def parse_identity(values: list[str], definition: dict[str, Any]) -> dict[str, str]:
    required = definition.get("idme_fields", [])
    supplied: dict[str, str] = {}
    for item in values:
        if "=" not in item:
            fail(f"invalid --idme value '{item}'; expected FIELD=VALUE")
        field, value = item.split("=", 1)
        if field not in required:
            allowed = ", ".join(required) if required else "none for this model"
            fail(f"unsupported identity field '{field}' (allowed: {allowed})")
        if field in supplied:
            fail(f"identity field supplied more than once: {field}")
        if not value.isascii() or "," in value:
            fail(f"identity field '{field}' must be ASCII and cannot contain a comma")
        supplied[field] = value
    missing = [field for field in required if field not in supplied]
    if missing:
        fail("missing required identity fields: " + ", ".join(missing) + "\nSupply each one as --idme FIELD=VALUE.")
    return supplied


def launch_command(args: argparse.Namespace) -> list[str]:
    directory, manifest = read_machine(args.name)
    model = manifest.get("model")
    definition = model_definition(model)
    artifacts = firmware_for(model, definition)
    disk = directory / "disk.qcow2"
    if not disk.is_file():
        fail(f"machine disk is missing: {disk}")
    identity = manifest.get("idme", {})
    required_identity = definition.get("idme_fields", [])
    if not isinstance(identity, dict) or sorted(identity) != sorted(required_identity):
        fail(f"machine identity is incomplete: {args.name}")
    machine_options = [definition["qemu_machine"]]
    machine_options.extend(f"idme-{field}={identity[field]}" for field in required_identity)
    if model == "kindle-paperwhite-4":
        machine_options.extend([
            f"storage-bios={artifacts['storage_bios']}",
            f"falcon-bios={artifacts['falcon_bios']}",
        ])
    command = [
        str(QEMU), "-machine", ",".join(machine_options),
        "-m", definition["memory"],
        "-bios", str(artifacts["bootloader"]),
        "-drive", f"file={disk},if=sd,index={definition['drive_index']},format=qcow2",
    ]
    if model == "kobo-touch":
        command.extend([
            "-chardev", "stdio,id=console,mux=on,signal=off",
            "-mon", "chardev=console,mode=readline",
            "-serial", "chardev:console",
            "-serial", "chardev:console",
            "-no-reboot",
        ])
    else:
        command.extend(["-serial", "mon:stdio", "-no-reboot"])
    if definition.get("network") == "wifi":
        ssh_port = port(args.ssh_port)
        command.extend([
            "-netdev", f"user,id=wifi,hostfwd=tcp:127.0.0.1:{ssh_port}-:22",
            "-global", "ar6003-sdio.netdev=wifi",
        ])
    if "panel_flash" in artifacts:
        panel = artifacts["panel_flash"]
        command.extend(["-drive", f"file={panel},if=mtd,index=0,format=raw,readonly=on"])
    if args.headless:
        command.extend(["-display", "none"])
    elif args.vnc:
        command.extend(["-vnc", args.vnc])
    elif sys.platform == "darwin":
        command.extend(["-display", "cocoa,show-cursor=on"])
    return command + list(args.qemu_args)


def command_run(args: argparse.Namespace) -> None:
    command = launch_command(args)
    if args.dry_run:
        print(shlex.join(command))
        return
    require_qemu_tools()
    os.execv(command[0], command)


def human_size(size: int | None) -> str:
    if size is None:
        return "-"
    value = float(size)
    for suffix in ("B", "KiB", "MiB", "GiB", "TiB"):
        if value < 1024 or suffix == "TiB":
            return f"{value:.0f}{suffix}" if suffix == "B" else f"{value:.1f}{suffix}"
        value /= 1024
    return str(size)


def allocated_size(path: Path) -> int:
    return path.stat().st_blocks * 512


def image_info(path: Path) -> tuple[int | None, str]:
    if not QEMU_IMG.is_file():
        return None, "-"
    try:
        value = json.loads(subprocess.check_output([str(QEMU_IMG), "info", "--output=json", str(path)], text=True))
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        return None, "?"
    backing = value.get("backing-filename") or "-"
    return value.get("virtual-size"), Path(backing).name if backing != "-" else backing


def print_table(headers: tuple[str, ...], rows: list[tuple[str, ...]]) -> None:
    widths = [len(header) for header in headers]
    for row in rows:
        widths = [max(width, len(cell)) for width, cell in zip(widths, row)]
    print("  ".join(header.ljust(width) for header, width in zip(headers, widths)))
    print("  ".join("-" * width for width in widths))
    for row in rows:
        print("  ".join(cell.ljust(width) for cell, width in zip(row, widths)))


def command_list(_: argparse.Namespace) -> None:
    rows: list[tuple[str, ...]] = []
    if MACHINES_ROOT.is_dir():
        for directory in sorted(path for path in MACHINES_ROOT.iterdir() if path.is_dir() and not path.name.startswith(".")):
            try:
                manifest = json.loads((directory / "machine.json").read_text())
                disk = directory / "disk.qcow2"
                state = "ready" if disk.is_file() and (ROOT / manifest["base"]).is_file() else "incomplete"
                allocated = human_size(allocated_size(disk)) if disk.is_file() else "-"
                rows.append((directory.name, str(manifest.get("model", "?")), state, allocated, str(manifest.get("created", "-"))[:10]))
            except (OSError, KeyError, json.JSONDecodeError):
                rows.append((directory.name, "?", "invalid", "-", "-"))
    if rows:
        print_table(("NAME", "MODEL", "STATE", "ALLOCATED", "CREATED"), rows)
    else:
        print("No machines. Create one with: ./eink create NAME --model MODEL")


def command_images(_: argparse.Namespace) -> None:
    paths = sorted(BASES_ROOT.glob("*.qcow2")) if BASES_ROOT.is_dir() else []
    if MACHINES_ROOT.is_dir():
        paths.extend(sorted(MACHINES_ROOT.glob("*/disk.qcow2")))
    rows: list[tuple[str, ...]] = []
    for path in paths:
        virtual, backing = image_info(path)
        rows.append((str(path.relative_to(ROOT)), human_size(virtual), human_size(allocated_size(path)), backing))
    if rows:
        print_table(("IMAGE", "VIRTUAL", "ALLOCATED", "BACKING"), rows)
    else:
        print("No generated images.")


def command_models(_: argparse.Namespace) -> None:
    rows = [
        (name, value["description"], "yes" if value.get("idme_fields") else "no")
        for name, value in sorted(load_catalogue().items())
    ]
    print_table(("MODEL", "DEVICE", "IDENTITY REQUIRED"), rows)


def command_firmware(_: argparse.Namespace) -> None:
    rows: list[tuple[str, ...]] = []
    for model, definition in sorted(load_catalogue().items()):
        directory = FIRMWARE_ROOT / model
        for required, group in ((True, "firmware"), (False, "optional_firmware")):
            for role, candidates in definition.get(group, {}).items():
                matches = [candidate for candidate in candidates if (directory / candidate).is_file()]
                status = "present" if len(matches) == 1 else "missing" if not matches else "ambiguous"
                expected = " | ".join(str(Path("firmware") / model / candidate) for candidate in candidates)
                rows.append((model, role, "required" if required else "optional", status, expected))
    print_table(("MODEL", "ARTIFACT", "NEED", "STATUS", "PATH"), rows)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="eink", description=__doc__)
    root.add_argument("--version", action="version", version="%(prog)s 0.1.0")
    commands = root.add_subparsers(dest="command", required=True)

    build = commands.add_parser("build", help="build QEMU and its image tool")
    build.set_defaults(handler=lambda _: build_qemu())

    models = commands.add_parser("models", help="list supported models")
    models.set_defaults(handler=command_models)

    firmware = commands.add_parser("firmware", help="show required bring-your-own firmware")
    firmware.set_defaults(handler=command_firmware)

    create = commands.add_parser("create", help="create a persistent machine")
    create.add_argument("name")
    create.add_argument("--model", required=True)
    create.add_argument("--idme", action="append", default=[], metavar="FIELD=VALUE", help="instance identity field; repeat for every field required by the model")
    create.set_defaults(handler=command_create)

    run = commands.add_parser("run", help="launch a persistent machine")
    run.add_argument("name")
    run.add_argument("--headless", action="store_true", help="disable graphical output")
    run.add_argument("--vnc", metavar="ENDPOINT", help="use QEMU's VNC display")
    run.add_argument("--ssh-port", type=int, default=2222, help="host SSH forwarding port (default: 2222)")
    run.add_argument("--dry-run", action="store_true", help="print the QEMU command")
    run.set_defaults(handler=command_run)

    machines = commands.add_parser("list", help="list persistent machines")
    machines.set_defaults(handler=command_list)

    images = commands.add_parser("images", help="list every generated disk image")
    images.set_defaults(handler=command_images)
    return root


def main() -> None:
    args, extra = parser().parse_known_args()
    if extra:
        if args.command != "run" or extra[0] != "--":
            fail("unrecognized arguments: " + " ".join(extra))
        extra = extra[1:]
    args.qemu_args = extra
    try:
        args.handler(args)
    except subprocess.CalledProcessError as error:
        fail(f"command failed with exit status {error.returncode}: {shlex.join(error.cmd)}")
    except KeyboardInterrupt:
        fail("interrupted")


if __name__ == "__main__":
    main()
