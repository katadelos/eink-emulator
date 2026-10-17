#!/usr/bin/env python3
"""Experimental portable checkpoints of a reader booted to its GUI.

start copies a stopped instance into a bundle and boots the copy.
save pauses that copy, saves RAM/devices, and stops QEMU, sealing the bundle.
resume runs a sealed bundle in a new directory with a disposable disk overlay.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from eink_emulator import cli
from eink_emulator.qmp import QMPClient, QMPError


def checked_path(value: str) -> Path:
    path = Path(value).resolve()
    if any(c in str(path) for c in (",", "\n", "{", "}")):
        raise ValueError("checkpoint paths cannot contain commas, newlines or braces")
    return path


def read_bundle(bundle: Path, status: str) -> dict:
    manifest = json.loads((bundle / "checkpoint.json").read_text())
    if manifest["format"] != 1 or manifest["status"] != status:
        raise ValueError(f"expected a {status} checkpoint bundle")
    return manifest


def qemu_version(binary: Path) -> str:
    return subprocess.check_output([str(binary), "--version"], text=True).splitlines()[0]


def wait_migration(client: QMPClient, timeout: float) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = client.execute("query-migrate")
        state = result.get("status")
        if state == "completed":
            return result
        if state in {"failed", "cancelled"}:
            raise QMPError(result.get("error-desc", f"migration {state}"))
        time.sleep(0.05)
    raise QMPError("migration timed out")


def launch(bundle: Path, runtime: Path, manifest: dict, args: argparse.Namespace,
           *, resume: bool) -> None:
    binary = cli.QEMU_SYSTEMS[manifest["arch"]]
    if qemu_version(binary) != manifest["qemu_version"]:
        raise ValueError("checkpoint requires the QEMU version recorded in checkpoint.json")
    if len(os.fsencode(runtime / "qmp.sock")) >= 100:
        raise ValueError("runtime directory is too long for a Unix socket; choose a shorter path")
    command = [str(binary)] + [arg.format(
        bundle=str(bundle), runtime=str(runtime), disk=str(runtime / "disk.qcow2")
    ) for arg in manifest["arguments"]]
    if args.headless:
        command.extend(["-display", "none"])
    elif args.vnc:
        command.extend(["-vnc", args.vnc])
    elif sys.platform == "darwin":
        command.extend(["-display", "cocoa,show-cursor=on"])
    if resume:
        command.extend(["-incoming", "defer"])
    start = time.monotonic()
    with (runtime / "qemu.log").open("ab") as log:
        process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=log,
                                   stderr=subprocess.STDOUT, start_new_session=True)
    try:
        with QMPClient(runtime / "qmp.sock", 30) as client:
            if resume:
                client.execute("migrate-incoming", {"uri": f"file:{bundle / 'memory.state'}"})
                wait_migration(client, 120)
                client.execute("cont")
            status = client.execute("query-status")
            if not status.get("running"):
                raise QMPError(f"guest did not start: {status}")
    except BaseException:
        process.terminate()
        process.wait(timeout=10)
        print(f"QEMU log: {runtime / 'qemu.log'}", file=sys.stderr)
        raise
    print(f"{'Resumed' if resume else 'Started'} in {time.monotonic() - start:.2f}s")
    print(f"QMP: {runtime / 'qmp.sock'}")
    print(f"Serial log: {runtime / 'serial.log'}")


def start(args: argparse.Namespace) -> None:
    bundle = args.bundle
    if bundle.exists():
        raise ValueError(f"destination already exists: {bundle}")
    source, machine = cli.read_machine(args.machine)
    if machine["model"] != "kindle-paperwhite-3":
        raise ValueError("experimental checkpoints currently support kindle-paperwhite-3; "
                         "other models need device-state support and restore validation")
    definition = cli.model_definition(machine["model"])
    options = cli.parser().parse_args(["run", args.machine])
    options.headless = True
    options.ssh_port = args.ssh_port
    options.wifi_ssh_port = args.wifi_ssh_port
    options.telnet_port = args.telnet_port
    options.serial_socket = options.qmp_socket = True
    options.qemu_args = []
    command = cli.launch_command(options)
    # Display backends belong to the receiving host, not the saved machine.
    display_index = command.index("-display")
    del command[display_index:display_index + 2]
    # convert takes a read lock and refuses an instance currently being written.
    # The resulting standalone image has no dependency on workspace bases.
    with cli.storage_lock(cli.BUILD_ROOT):
        bundle.mkdir(parents=True)
        runtime = bundle / "capture"
        runtime.mkdir()
        subprocess.run([str(cli.QEMU_IMG), "convert", "-O", "qcow2",
                        str(source / "disk.qcow2"), str(runtime / "disk.qcow2")], check=True)
        firmware = bundle / "firmware"
        firmware.mkdir()
        replacements = {str(source / "disk.qcow2"): "{disk}"}
        paths = cli.runtime_paths(source)
        replacements.update({str(paths[key]): "{runtime}/" + filename for key, filename in (
            ("serial_log", "serial.log"), ("serial", "serial.sock"), ("qmp", "qmp.sock")
        )})
        for argument in command[1:]:
            for part in argument.split(","):
                candidate = Path(part.split("=", 1)[-1])
                if candidate.is_absolute() and candidate.is_relative_to(cli.FIRMWARE_ROOT):
                    if not candidate.is_file():
                        raise ValueError(f"missing runtime firmware: {candidate}")
                    shutil.copy2(candidate, firmware / candidate.name)
                    replacements[str(candidate)] = "{bundle}/firmware/" + candidate.name
        arguments = []
        for argument in command[1:]:
            for old, new in replacements.items():
                argument = argument.replace(old, new)
            arguments.append(argument)
        manifest = {
            "format": 1, "status": "booting", "model": machine["model"],
            "profile": machine.get("profile"), "arch": definition.get("qemu_arch", "arm"),
            "qemu_version": qemu_version(Path(command[0])), "arguments": arguments,
        }
        cli.write_json(bundle / "checkpoint.json", manifest)
    launch(bundle, runtime, manifest, args, resume=False)
    print(f"When the GUI is ready: python3 scripts/eink-checkpoint.py save {bundle}")


def save(args: argparse.Namespace) -> None:
    bundle = args.bundle
    manifest = read_bundle(bundle, "booting")
    runtime = bundle / "capture"
    temporary = bundle / "memory.state.partial"
    if temporary.exists():
        raise ValueError(f"incomplete capture exists; inspect it before retrying: {temporary}")
    start = time.monotonic()
    with QMPClient(runtime / "qmp.sock", 10) as client:
        original = client.execute("query-status")
        if original["status"] not in {"running", "paused"}:
            raise ValueError(f"cannot capture guest in state {original['status']}")
        # This workflow owns one disk. Refuse extra writable devices instead of
        # silently producing memory paired with only part of the disk state.
        blocks = client.execute("query-block")
        writable = [b["inserted"] for b in blocks if b.get("inserted") and not b["inserted"]["ro"]]
        if len(writable) != 1 or Path(writable[0]["file"]).resolve() != runtime / "disk.qcow2":
            raise ValueError("checkpoint capture requires exactly the bundle's writable disk")
        client.execute("stop")
        try:
            client.execute("migrate-set-parameters", {"max-bandwidth": 1024**3})
            client.execute("migrate", {"uri": f"file:{temporary}"})
            wait_migration(client, 120)
        except BaseException:
            client.execute("migrate_cancel")
            # Do not resume while migration might still be writing the stream.
            deadline = time.monotonic() + 10
            while client.execute("query-migrate").get("status") not in {"cancelled", "failed", "completed", "none"}:
                if time.monotonic() >= deadline:
                    raise QMPError("cancellation timed out; guest left paused")
                time.sleep(0.05)
            if original["running"]:
                client.execute("cont")
            temporary.unlink(missing_ok=True)
            raise
        client.execute("quit")
    seal(bundle, runtime, manifest)
    print(f"Saved and stopped in {time.monotonic() - start:.2f}s: {bundle}")


def seal(bundle: Path, runtime: Path, manifest: dict) -> None:
    temporary = bundle / "memory.state.partial"
    # Wait for QEMU to release its disk lock, not merely acknowledge quit.
    deadline = time.monotonic() + 10
    while True:
        result = subprocess.run([str(cli.QEMU_IMG), "info", "--output=json",
                                 str(runtime / "disk.qcow2")], capture_output=True, text=True)
        if result.returncode == 0:
            break
        if time.monotonic() >= deadline:
            raise ValueError(f"cannot seal checkpoint disk: {result.stderr.strip()}")
        time.sleep(0.05)
    # QEMU's completed migration does not fsync the stream itself.
    with temporary.open("rb") as stream:
        os.fsync(stream.fileno())
    temporary.replace(bundle / "memory.state")
    (runtime / "disk.qcow2").replace(bundle / "disk.qcow2")
    with (bundle / "disk.qcow2").open("rb") as disk:
        os.fsync(disk.fileno())
    (bundle / "disk.qcow2").chmod(0o444)
    (bundle / "memory.state").chmod(0o444)
    manifest["status"] = "ready"
    cli.write_json(bundle / "checkpoint.json", manifest)
    shutil.rmtree(runtime)


def resume(args: argparse.Namespace) -> None:
    manifest = read_bundle(args.bundle, "ready")
    if args.runtime.exists():
        raise ValueError(f"runtime directory already exists: {args.runtime}")
    args.runtime.mkdir(parents=True)
    subprocess.run([str(cli.QEMU_IMG), "create", "-q", "-f", "qcow2", "-F", "qcow2",
                    "-b", str(args.bundle / "disk.qcow2"), str(args.runtime / "disk.qcow2")], check=True)
    launch(args.bundle, args.runtime, manifest, args, resume=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    boot = commands.add_parser("start", help="boot a standalone copy of a stopped instance")
    boot.add_argument("machine")
    boot.add_argument("bundle", type=checked_path)
    display = boot.add_mutually_exclusive_group()
    display.add_argument("--headless", action="store_true")
    display.add_argument("--vnc")
    boot.add_argument("--ssh-port", type=int, default=2222)
    boot.add_argument("--wifi-ssh-port", type=int, default=2223)
    boot.add_argument("--telnet-port", type=int, default=2323)
    boot.set_defaults(handler=start)
    capture = commands.add_parser("save", help="capture the ready GUI and stop the copy")
    capture.add_argument("bundle", type=checked_path)
    capture.set_defaults(handler=save)
    run = commands.add_parser("resume", help="resume in a new directory, preserving the checkpoint")
    run.add_argument("bundle", type=checked_path)
    run.add_argument("runtime", type=checked_path)
    display = run.add_mutually_exclusive_group()
    display.add_argument("--headless", action="store_true")
    display.add_argument("--vnc")
    run.set_defaults(handler=resume)
    args = parser.parse_args()
    try:
        args.handler(args)
    except (OSError, ValueError, QMPError, subprocess.SubprocessError) as error:
        parser.exit(1, f"eink-checkpoint: {error}\n")


if __name__ == "__main__":
    main()
