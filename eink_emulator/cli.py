"""Create, inventory, and launch e-ink emulator machines."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import socket
import subprocess
import sys
import tempfile
from contextlib import nullcontext
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .firmware import import_recovery
from .images import addons, build_raw_image
from .qemu import build as build_qemu
from .ssh import LOGIN_KEY, ensure_login_key
from .storage import (
    base_families, disk_info, image_references, open_files, storage_lock,
    unused_bases, write_base,
)


ROOT = Path(__file__).resolve().parent.parent
CATALOGUE = ROOT / "models.json"
FIRMWARE_ROOT = ROOT / "firmware"
MACHINES_ROOT = ROOT / "machines"
BUILD_ROOT = ROOT / "build"
BASES_ROOT = BUILD_ROOT / "images"
QEMU_BUILD = ROOT / "qemu" / "build"
QEMU_SYSTEMS = {
    "arm": QEMU_BUILD / "qemu-system-arm",
    "aarch64": QEMU_BUILD / "qemu-system-aarch64",
}
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
    override_groups = definition.get("rootfs_overrides", [definition["builder"]])
    for group in ["network", "kobo-network", "kindle", *override_groups]:
        overrides = ROOT / "guest-overrides" / group
        if overrides.is_dir():
            for path in sorted(path for path in overrides.rglob("*") if path.is_file()):
                digest.update(group.encode())
                digest.update(str(path.relative_to(overrides)).encode())
                digest.update(path.read_bytes())
    if definition["network"].get("usb", {}).get("service") == "ssh":
        additions = ROOT / "guest-additions"
        for path in sorted(path for path in additions.rglob("*") if path.is_file()):
            if path.is_relative_to(addons.DOWNLOADS):
                continue
            digest.update(str(path.relative_to(additions)).encode())
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


def qemu_system(definition: dict[str, Any]) -> Path:
    arch = definition.get("qemu_arch", "arm")
    try:
        return QEMU_SYSTEMS[arch]
    except KeyError:
        fail(f"unsupported QEMU architecture in model catalogue: {arch}")


def require_qemu_tools(qemu: Path) -> None:
    if not qemu.is_file() or not QEMU_IMG.is_file():
        print("QEMU is not built; building it now.")
        build_qemu()
    if not qemu.is_file() or not QEMU_IMG.is_file():
        fail("QEMU build completed without the required executables")


def ensure_base(model: str, definition: dict[str, Any], artifacts: dict[str, Path]) -> tuple[Path, str]:
    if model.startswith("kindle-"):
        artifacts = artifacts | {"ssh_authorized_keys": ensure_login_key()}
    fingerprint = digest_files(definition, artifacts)
    base = BASES_ROOT / f"{model}-{fingerprint[:16]}.qcow2"
    metadata = base.with_suffix(".json")
    if base.is_file() and metadata.is_file():
        return base, fingerprint

    require_qemu_tools(qemu_system(definition))
    BASES_ROOT.mkdir(parents=True, exist_ok=True)
    staging_root = BUILD_ROOT / "tmp"
    staging_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f"{model}-", dir=staging_root) as temporary:
        raw = Path(temporary) / "disk.raw"
        source = build_raw_image(definition, artifacts, raw)
        families = base_families(ROOT, QEMU_IMG, model=model)
        parents = families.get((model, source.stat().st_size), [])
        write_base(QEMU_IMG, source, "raw", base, backing=parents[0] if parents else None)
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
    if args.sideloaded:
        if definition["builder"] not in {"forma", "elipsa2e"}:
            fail("--sideloaded is only supported by Kobo Forma and Elipsa 2E")
        definition["sideloaded"] = True
    addon_plan = addons.plan(args.model, jailbreak=args.jailbreak, kual=args.kual, mrpi=args.mrpi)
    if addon_plan:
        definition["addons"] = addon_plan
    profile = parse_profile(args.profile, definition)
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
        manifest = {
            "base": str(base.relative_to(ROOT)),
            "created": datetime.now(timezone.utc).isoformat(),
            "firmware_fingerprint": fingerprint,
            "format": 1,
            "model": args.model,
            "name": args.name,
        }
        if addon_plan:
            manifest["addons"] = addon_plan
        if profile:
            manifest["profile"] = profile
        write_json(temporary / "machine.json", manifest)
        temporary.replace(target)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    print(f"created {args.name} ({definition['description']})")
    print(f"run it with: ./eink run {args.name}")
    if args.model.startswith("kindle-"):
        print(f"SSH over USB: ssh -i {shlex.quote(str(LOGIN_KEY))} -p 2222 root@127.0.0.1")
        print("SSH over Wi-Fi: use port 2223 after joining Kindle-QEMU")


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


def parse_profile(value: str | None, definition: dict[str, Any]) -> str | None:
    supported = definition.get("device_profiles", [])
    if not supported:
        if value:
            fail("--profile is not supported by this model")
        return None
    if not value:
        fail("--profile is required for this model (choose from: " + ", ".join(supported) + ")")
    if value not in supported:
        fail(f"unsupported profile '{value}' (choose from: {', '.join(supported)})")
    return value


def launch_command(args: argparse.Namespace) -> list[str]:
    directory, manifest = read_machine(args.name)
    model = manifest.get("model")
    definition = model_definition(model)
    # A saved disk already contains the kernel, rootfs and other image inputs.
    # Only files actually passed to QEMU are required to launch it.
    runtime_roles = {"bootloader", *definition.get("machine_firmware_properties", {}).values()}
    if model == "kindle-paperwhite-4":
        runtime_roles.update({"storage_bios", "falcon_bios"})
    missing_roles = runtime_roles - definition["firmware"].keys()
    if missing_roles:
        fail(f"model catalogue has undefined runtime firmware roles: {', '.join(sorted(missing_roles))}")
    runtime_definition = definition | {
        "firmware": {
            role: candidates for role, candidates in definition["firmware"].items()
            if role in runtime_roles
        },
    }
    artifacts = firmware_for(model, runtime_definition)
    disk = directory / "disk.qcow2"
    if not disk.is_file():
        fail(f"machine disk is missing: {disk}")
    machine_options = [definition["qemu_machine"]]
    machine_options.extend(
        f"{property_name}={value}"
        for property_name, value in definition.get("machine_properties", {}).items()
    )
    for property_name, artifact_role in definition.get(
        "machine_firmware_properties", {}
    ).items():
        try:
            machine_options.append(f"{property_name}={artifacts[artifact_role]}")
        except KeyError:
            fail(
                f"model catalogue maps machine property '{property_name}' "
                f"to missing firmware role '{artifact_role}'"
            )
    supported_profiles = definition.get("device_profiles", [])
    if supported_profiles:
        profile = manifest.get("profile")
        if profile not in supported_profiles:
            fail(f"machine profile is missing or invalid: {args.name}")
        machine_options.append(f"device-profile={profile}")
    if model == "kindle-paperwhite-4":
        machine_options.extend([
            f"storage-bios={artifacts['storage_bios']}",
            f"falcon-bios={artifacts['falcon_bios']}",
        ])
    command = [str(qemu_system(definition))]
    if accel := definition.get("accel"):
        command.extend(["-accel", accel])
    command.extend([
        "-name", args.name,
        "-machine", ",".join(machine_options),
        "-m", definition["memory"],
        "-bios", str(artifacts["bootloader"]),
        "-drive", f"file={disk},if=sd,index={definition['drive_index']},format=qcow2",
    ])
    runtime = runtime_paths(directory)
    if model in {"kobo-mini", "kobo-touch"}:
        chardev = (
            f"socket,id=console,path={runtime['serial']},server=on,wait=off,mux=on,logfile={runtime['serial_log']}"
            if args.serial_socket
            else "stdio,id=console,mux=on,signal=off"
        )
        command.extend([
            "-chardev", chardev,
            "-mon", "chardev=console,mode=readline",
            "-serial", "chardev:console",
            "-serial", "chardev:console",
        ])
    elif args.serial_socket:
        command.extend([
            "-chardev",
            f"socket,id=serial0,path={runtime['serial']},server=on,wait=off,logfile={runtime['serial_log']}",
            "-serial", "chardev:serial0",
            "-monitor", "none",
        ])
    else:
        command.extend(["-serial", "mon:stdio"])
    if args.qmp_socket:
        command.extend(["-qmp", f"unix:{runtime['qmp']},server=on,wait=off"])
    if not definition.get("allow_reboot"):
        command.append("-no-reboot")
    network = definition["network"]
    if wifi := network.get("wifi"):
        ssh_port = port(args.wifi_ssh_port if "usb" in network else args.ssh_port)
        command.extend([
            "-netdev", f"user,id=wifi,hostfwd=tcp:127.0.0.1:{ssh_port}-:22",
            "-global", f"{wifi['device']}.{wifi.get('netdev_property', 'netdev')}=wifi",
        ])
    if usb := network.get("usb"):
        controller = usb["device"]
        if usb["service"] == "telnet":
            forwarded_port = port(args.telnet_port)
            guest_port = 23
        else:
            forwarded_port = port(args.ssh_port)
            guest_port = 22
        command.extend([
            "-netdev",
            (
                "user,id=usb,net=192.168.15.0/24,"
                "host=192.168.15.201,dns=192.168.15.3,"
                "dhcpstart=192.168.15.244,"
                f"hostfwd=tcp:127.0.0.1:{forwarded_port}-192.168.15.244:{guest_port}"
            ),
            "-global", f"{controller}.netdev=usb",
            "-global", f"{controller}.mac=ee:19:00:00:00:00",
        ])
    if args.headless:
        command.extend(["-display", "none"])
    elif args.vnc:
        command.extend(["-vnc", args.vnc])
    elif sys.platform == "darwin":
        command.extend(["-display", "cocoa,show-cursor=on"])
    return command + list(args.qemu_args)


def runtime_paths(directory: Path) -> dict[str, Path]:
    name = directory.name
    return {
        "qmp": directory / f"{name}.qmp.sock",
        "serial": directory / f"{name}.serial.sock",
        "serial_log": directory / f"{name}.serial.log",
    }


def qmp_status(path: Path) -> dict[str, Any] | None:
    client = socket.socket(socket.AF_UNIX)
    client.settimeout(1.0)
    try:
        client.connect(str(path))
    except (FileNotFoundError, ConnectionRefusedError):
        client.close()
        return None
    except OSError as error:
        client.close()
        fail(f"cannot inspect existing QMP socket {path}: {error}")

    stream = client.makefile("rwb", buffering=0)
    try:
        greeting = json.loads(stream.readline())
        if "QMP" not in greeting:
            fail(f"unexpected data on existing QMP socket: {path}")
        for request_id, command in enumerate(("qmp_capabilities", "query-status"), 1):
            stream.write(json.dumps({"execute": command, "id": request_id}).encode() + b"\n")
            while True:
                response = json.loads(stream.readline())
                if response.get("id") != request_id:
                    continue
                if "error" in response:
                    fail(f"existing QMP socket rejected {command}: {response['error']}")
                if command == "query-status":
                    result = response.get("return")
                    return result if isinstance(result, dict) else {}
                break
    except (OSError, TimeoutError, json.JSONDecodeError) as error:
        fail(f"existing QMP socket is unresponsive: {path}: {error}")
    finally:
        stream.close()
        client.close()
    return {}


def attach_existing(directory: Path, status: dict[str, Any]) -> None:
    state = status.get("status", "running")
    print(f"{directory.name} is already {state}; reusing the existing QEMU process.")
    runtime = runtime_paths(directory)
    print(f"QMP: python3 scripts/eink-qmp.py --machine {directory.name} status")
    if runtime["serial"].exists():
        print(f"serial socket: {runtime['serial']}")
    else:
        print("serial remains attached to the original ./eink run process")


def command_run(args: argparse.Namespace) -> None:
    directory, manifest = read_machine(args.name)
    runtime = runtime_paths(directory)
    if not args.dry_run:
        status = qmp_status(runtime["qmp"])
        if status is not None:
            attach_existing(directory, status)
            return

    command = launch_command(args)
    if args.dry_run:
        print(shlex.join(command))
        return
    definition = model_definition(manifest.get("model"))
    qemu = qemu_system(definition)
    if args.qmp_socket:
        runtime["qmp"].unlink(missing_ok=True)
        print(f"QMP: python3 scripts/eink-qmp.py --machine {directory.name} status")
    if args.serial_socket:
        if runtime["serial"].exists():
            fail(
                f"serial socket path already exists: {runtime['serial']}\n"
                "Remove it only after confirming that no QEMU process is using it."
            )
        print(f"serial socket: {runtime['serial']}")
    if args.qmp_socket or args.serial_socket:
        sys.stdout.flush()
    require_qemu_tools(qemu)
    os.execv(command[0], command)


def command_qemu(args: argparse.Namespace) -> None:
    if not args.qemu_args:
        fail("QEMU arguments are required after '--'")
    qemu = QEMU_SYSTEMS[args.arch]
    command = [str(qemu), *args.qemu_args]
    if args.dry_run:
        print(shlex.join(command))
        return
    require_qemu_tools(qemu)
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
        value = disk_info(QEMU_IMG, path)
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
        print_table(("NAME", "MODEL", "STATE", "OVERLAY", "CREATED"), rows)
    else:
        print("No machines. Create one with: ./eink create NAME --model MODEL")
    print_storage_summary()


def print_storage_summary() -> None:
    totals = {"overlays": 0, "bases": 0, "other": 0}
    seen: set[tuple[int, int]] = set()
    for directory in (BASES_ROOT, MACHINES_ROOT):
        for path in directory.rglob("*"):
            if not path.is_file():
                continue
            stat = path.stat()
            identity = (stat.st_dev, stat.st_ino)
            if identity in seen:
                continue
            seen.add(identity)
            group = "other"
            if path.parent == BASES_ROOT and path.suffix == ".qcow2":
                group = "bases"
            elif path.name == "disk.qcow2" and path.parent.parent == MACHINES_ROOT:
                group = "overlays"
            totals[group] += stat.st_blocks * 512
    print(f"\nMachine overlays: {human_size(totals['overlays'])}; "
          f"shared bases: {human_size(totals['bases'])}; "
          f"other machine/image files: {human_size(totals['other'])}.")
    print(f"Total allocated: {human_size(sum(totals.values()))} "
          "(shared bases counted once; excludes imported firmware and build files).")


def prune_bases(paths: list[Path], *, dry_run: bool) -> None:
    allocated = sum(allocated_size(path) for path in paths)
    for path in paths:
        if not dry_run:
            path.unlink()
            path.with_suffix(".json").unlink(missing_ok=True)
        print(f"{'would remove' if dry_run else 'removed'} {path.relative_to(ROOT)}")
    action = "Would reclaim" if dry_run else "Reclaimed"
    print(f"{action} {human_size(allocated)} from {len(paths)} unused base images.")


def command_delete(args: argparse.Namespace) -> None:
    directory, _ = read_machine(args.name)
    if directory.is_symlink():
        fail(f"refusing to delete a symlinked machine directory: {directory}")
    qmp = runtime_paths(directory)["qmp"]
    if qmp.exists() and qmp_status(qmp) is not None:
        fail(f"machine is still running: {args.name}; stop it before deleting it")
    references = image_references(ROOT, QEMU_IMG, excluding=directory.resolve())
    files = [path for path in directory.rglob("*") if path.is_file()]
    if any(path.resolve() in references for path in files):
        fail(f"another disk depends on machine {args.name}; cannot delete it")
    if open_files(files):
        fail(f"machine files are still in use: {args.name}; stop it before deleting it")
    bases = unused_bases(ROOT, references)
    if not args.dry_run:
        shutil.rmtree(directory)
    print(f"{'would delete' if args.dry_run else 'deleted'} machine {args.name}")
    prune_bases(bases, dry_run=args.dry_run)


def command_images(args: argparse.Namespace) -> None:
    if args.dry_run and not (args.prune or args.compact):
        fail("--dry-run requires --prune or --compact")
    if args.compact:
        command_compact(args)
        return
    if args.prune:
        references = image_references(ROOT, QEMU_IMG)
        prune_bases(unused_bases(ROOT, references), dry_run=args.dry_run)
        return
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
    print_storage_summary()


def command_compact(args: argparse.Namespace) -> None:
    families = base_families(ROOT, QEMU_IMG)
    pairs = [(path, paths[0]) for paths in families.values() for path in paths[1:]]
    if not args.dry_run and open_files([path for path, _ in pairs]):
        fail("shared bases are in use; stop their machines before compacting")
    reclaimed = 0
    for path, backing in pairs:
        if args.dry_run:
            print(f"would layer {path.name} on {backing.name}")
            continue
        before = allocated_size(path)
        write_base(QEMU_IMG, path, "qcow2", path, backing=backing)
        saved = before - allocated_size(path)
        reclaimed += saved
        print(f"{path.name}: reclaimed {human_size(saved)}", flush=True)
    if args.dry_run:
        print(f"Would compact {len(pairs)} base images; exact savings require comparing disk contents.")
    else:
        print(f"Reclaimed {human_size(reclaimed)} from shared base images.")
        print_storage_summary()


def command_models(_: argparse.Namespace) -> None:
    rows = [
        (
            name,
            value["description"],
            " | ".join(value.get("device_profiles", [])) or "-",
        )
        for name, value in sorted(load_catalogue().items())
    ]
    print_table(("MODEL", "DEVICE", "PROFILES"), rows)


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


def command_import(args: argparse.Namespace) -> None:
    definition = model_definition(args.model)
    installed = import_recovery(
        package=Path(args.package).resolve(),
        destination=FIRMWARE_ROOT / args.model,
        definition=definition,
    )
    print(f"imported {definition['description']} firmware:")
    for role, path in installed.items():
        print(f"  {role}: {path.relative_to(ROOT)}")


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

    import_package = commands.add_parser(
        "import", help="import a vendor recovery firmware package"
    )
    import_package.add_argument("package")
    import_package.add_argument("--model", required=True)
    import_package.set_defaults(handler=command_import)

    create = commands.add_parser("create", help="create a persistent machine")
    create.add_argument("name")
    create.add_argument("--model", required=True)
    create.add_argument("--profile", help="hardware profile; required for models that expose profiles")
    create.add_argument(
        "--sideloaded", action="store_true",
        help="initialize Kobo Forma or Elipsa 2E in offline sideloaded mode, skipping setup",
    )
    create.add_argument("--jailbreak", action="store_true", help="prepare Kindle developer update key, debug/exec flags and root helper")
    create.add_argument("--kual", action="store_true", help="pre-install pinned KUAL (includes --jailbreak)")
    create.add_argument("--mrpi", action="store_true", help="pre-install pinned MRPI (includes --kual and --jailbreak)")
    create.set_defaults(handler=command_create)

    delete = commands.add_parser("delete", help="delete a stopped machine and prune unused shared bases")
    delete.add_argument("name")
    delete.add_argument("--dry-run", action="store_true", help="show what would be removed")
    delete.set_defaults(handler=command_delete)

    run = commands.add_parser("run", help="launch a persistent machine")
    run.add_argument("name")
    run.add_argument("--headless", action="store_true", help="disable graphical output")
    run.add_argument("--vnc", metavar="ENDPOINT", help="use QEMU's VNC display")
    run.add_argument("--ssh-port", type=int, default=2222, help="host USB SSH port, or Wi-Fi SSH port on Wi-Fi-only models (default: 2222)")
    run.add_argument("--wifi-ssh-port", type=int, default=2223, help="host Wi-Fi SSH port when USB networking is also configured (default: 2223)")
    run.add_argument("--telnet-port", type=int, default=2323, help="host USB telnet forwarding port for Kobos (default: 2323)")
    run.add_argument("--serial-socket", action="store_true", help="redirect serial to an instance-scoped Unix socket and log instead of this terminal")
    run.add_argument("--qmp-socket", action="store_true", help="expose QMP on an instance-scoped Unix socket")
    run.add_argument("--dry-run", action="store_true", help="print the QEMU command")
    run.set_defaults(handler=command_run)

    qemu = commands.add_parser("qemu", help="launch an ephemeral raw QEMU machine")
    qemu.add_argument("--arch", choices=sorted(QEMU_SYSTEMS), default="arm")
    qemu.add_argument("--dry-run", action="store_true", help="print the QEMU command")
    qemu.set_defaults(handler=command_qemu)

    machines = commands.add_parser("list", help="list persistent machines")
    machines.set_defaults(handler=command_list)

    images = commands.add_parser("images", help="list every generated disk image")
    maintenance = images.add_mutually_exclusive_group()
    maintenance.add_argument("--prune", action="store_true", help="remove shared bases no longer used by workspace disks")
    maintenance.add_argument("--compact", action="store_true", help="deduplicate stopped base revisions using shared backing images")
    images.add_argument("--dry-run", action="store_true", help="preview --prune or --compact without changing images")
    images.set_defaults(handler=command_images)
    return root


def main() -> None:
    args, extra = parser().parse_known_args()
    if extra:
        if args.command not in {"qemu", "run"} or extra[0] != "--":
            fail("unrecognized arguments: " + " ".join(extra))
        extra = extra[1:]
    args.qemu_args = extra
    try:
        changes_storage = args.command in {"create", "delete"} or (
            args.command == "images" and (args.prune or args.compact)
        )
        with storage_lock(BUILD_ROOT) if changes_storage else nullcontext():
            args.handler(args)
    except OSError as error:
        fail(str(error))
    except subprocess.CalledProcessError as error:
        fail(f"command failed with exit status {error.returncode}: {shlex.join(error.cmd)}")
    except KeyboardInterrupt:
        fail("interrupted")


if __name__ == "__main__":
    main()
