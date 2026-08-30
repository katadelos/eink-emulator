#!/usr/bin/env python3
"""Reliable QMP control and hardware-aware diagnostics for e-ink machines."""

from __future__ import annotations

import argparse
import json
import re
import socket
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
HWTCON_QOM_PATH = "/machine/soc/hwtcon"
HWTCON_PROPERTIES = (
    "scanout-iova",
    "scanout-base-iova",
    "scanout-guest-va",
    "scanout-width",
    "scanout-height",
    "scanout-source-width",
    "scanout-source-height",
    "scanout-pitch",
    "scanout-format",
    "scanout-rotation",
    "last-update-x",
    "last-update-y",
    "last-update-width",
    "last-update-height",
    "mdp-transactions",
    "mdp-writebacks",
    "mdp-writeback-skips",
    "mdp-writeback-failures",
    "pipeline-triggers",
    "pipeline-voids",
    "last-pipeline-flags",
    "last-pipeline-lut",
    "last-frame-min",
    "last-frame-max",
    "waveform-triggers",
    "boot-handoff-arms",
    "boot-blank-retentions",
    "cfa-source-reports",
    "cfa-fault-va",
    "cfa-fault-cpu",
    "scanout-captures",
    "scanout-refreshes",
    "scanout-read-failures",
)
OBSERVE_HWTCON_PROPERTIES = (
    "scanout-iova",
    "pipeline-triggers",
    "pipeline-voids",
    "last-pipeline-flags",
    "last-pipeline-lut",
    "last-frame-min",
    "last-frame-max",
    "waveform-triggers",
    "boot-handoff-arms",
    "boot-blank-retentions",
    "scanout-refreshes",
    "scanout-read-failures",
)
MACHINE_PROPERTIES = (
    "board",
    "device-profile",
    "cfa-bypass",
    "cfa-bypass-applied",
    "cfa-bypass-address",
    "cfa-bypass-workers-address",
    "cfa-bypass-attempts",
    "idme-board-id",
    "idme-product-name",
    "idme-device-type",
)


class QMPError(RuntimeError):
    pass


class QMPClient:
    def __init__(self, path: Path, timeout: float) -> None:
        self.path = path
        self.timeout = timeout
        self.socket: socket.socket | None = None
        self.stream: Any = None
        self.request_id = 0

    def __enter__(self) -> "QMPClient":
        deadline = time.monotonic() + self.timeout
        last_error: OSError | None = None
        while time.monotonic() < deadline:
            candidate = socket.socket(socket.AF_UNIX)
            candidate.settimeout(max(0.1, deadline - time.monotonic()))
            try:
                candidate.connect(str(self.path))
                self.socket = candidate
                break
            except OSError as error:
                last_error = error
                candidate.close()
                time.sleep(0.05)
        else:
            raise QMPError(f"cannot connect to {self.path}: {last_error}")

        self.stream = self.socket.makefile("rwb", buffering=0)
        greeting = self._read_message(deadline)
        if "QMP" not in greeting:
            raise QMPError(f"invalid QMP greeting: {greeting!r}")
        self.execute("qmp_capabilities")
        return self

    def __exit__(self, *_exc: object) -> None:
        if self.stream is not None:
            self.stream.close()
        if self.socket is not None:
            self.socket.close()

    def _read_message(self, deadline: float) -> dict[str, Any]:
        if self.socket is None or self.stream is None:
            raise QMPError("QMP client is not connected")
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise QMPError("QMP response timed out")
        self.socket.settimeout(remaining)
        try:
            line = self.stream.readline()
        except TimeoutError as error:
            raise QMPError("QMP response timed out") from error
        if not line:
            raise QMPError("QMP disconnected")
        try:
            return json.loads(line)
        except json.JSONDecodeError as error:
            raise QMPError(f"invalid QMP response: {line!r}") from error

    def execute(self, command: str,
                arguments: dict[str, Any] | None = None) -> Any:
        if self.stream is None:
            raise QMPError("QMP client is not connected")
        self.request_id += 1
        request: dict[str, Any] = {
            "execute": command,
            "id": self.request_id,
        }
        if arguments is not None:
            request["arguments"] = arguments
        self.stream.write(json.dumps(request, separators=(",", ":")).encode()
                          + b"\n")

        deadline = time.monotonic() + self.timeout
        while True:
            response = self._read_message(deadline)
            if response.get("id") != self.request_id:
                continue
            if "error" in response:
                description = response["error"].get("desc", response["error"])
                raise QMPError(f"{command}: {description}")
            if "return" in response:
                return response["return"]
            raise QMPError(f"malformed QMP response: {response!r}")

    def hmp(self, command: str) -> str:
        return self.execute(
            "human-monitor-command", {"command-line": command})


def parse_arguments(value: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as error:
        raise argparse.ArgumentTypeError(str(error)) from error
    if not isinstance(parsed, dict):
        raise argparse.ArgumentTypeError("QMP arguments must be a JSON object")
    return parsed


def parse_cpu_registers(registers: str) -> list[dict[str, Any]]:
    sections = re.split(r"(?=CPU#\d+)", registers)
    cpus: list[dict[str, Any]] = []
    for section in sections:
        cpu_match = re.search(r"CPU#(\d+)", section)
        if cpu_match is None:
            continue
        values: dict[str, Any] = {"cpu-index": int(cpu_match.group(1))}
        for key, patterns in {
            "pc": (r"\bR15=([0-9a-f]+)", r"\bPC=([0-9a-f]+)",
                   r"\bPC\s+([0-9a-f]+)"),
            "sp": (r"\bR13=([0-9a-f]+)", r"\bSP=([0-9a-f]+)"),
            "cpsr": (r"\bPSR=([0-9a-f]+)", r"\bCPSR=([0-9a-f]+)"),
        }.items():
            for pattern in patterns:
                match = re.search(pattern, section, re.IGNORECASE)
                if match is not None:
                    values[key] = int(match.group(1), 16)
                    break
        cpus.append(values)
    return cpus


def parse_hmp_words(output: str) -> dict[int, int]:
    words: dict[int, int] = {}
    for line in output.splitlines():
        match = re.match(r"^([0-9a-f]+):\s+(.*)$", line, re.IGNORECASE)
        if match is None:
            continue
        address = int(match.group(1), 16)
        for index, value in enumerate(re.findall(
                r"0x([0-9a-f]{1,8})", match.group(2), re.IGNORECASE)):
            words[address + index * 4] = int(value, 16)
    return words


def virtual_memory_map(client: QMPClient, address: int, size: int,
                       cpu: int, page_size: int) -> list[dict[str, int | None]]:
    if size <= 0 or page_size <= 0 or page_size & (page_size - 1):
        raise QMPError("map size must be positive and page size a power of two")

    client.hmp(f"cpu {cpu}")
    first_page = address & -page_size
    last_page = (address + size - 1) & -page_size
    ranges: list[dict[str, int | None]] = []
    for virtual in range(first_page, last_page + page_size, page_size):
        output = client.hmp(f"gva2gpa 0x{virtual:x}")
        match = re.search(r"gpa:\s*0x([0-9a-f]+)", output,
                          re.IGNORECASE)
        physical = int(match.group(1), 16) if match is not None else None
        if ranges:
            previous = ranges[-1]
            previous_size = int(previous["size"])
            contiguous_virtual = (
                int(previous["virtual"]) + previous_size == virtual)
            previous_physical = previous["physical"]
            contiguous_physical = (
                previous_physical is None and physical is None) or (
                    previous_physical is not None and physical is not None and
                    int(previous_physical) + previous_size == physical)
            if contiguous_virtual and contiguous_physical:
                previous["size"] = previous_size + page_size
                continue
        ranges.append({
            "virtual": virtual,
            "physical": physical,
            "size": page_size,
        })
    return ranges


def query_hwtcon_properties(client: QMPClient,
                             properties: tuple[str, ...],
                             available: set[str] | None = None
                             ) -> dict[str, int]:
    if available is None:
        available = {
            item["name"] for item in client.execute("qom-list", {
                "path": HWTCON_QOM_PATH,
            })
        }
    return {
        name: client.execute("qom-get", {
            "path": HWTCON_QOM_PATH,
            "property": name,
        })
        for name in properties if name in available
    }


def query_hwtcon(client: QMPClient) -> dict[str, int]:
    return query_hwtcon_properties(client, HWTCON_PROPERTIES)


def query_machine(client: QMPClient) -> dict[str, Any]:
    available = {
        item["name"] for item in client.execute("qom-list", {
            "path": "/machine",
        })
    }
    return {
        name: client.execute("qom-get", {
            "path": "/machine",
            "property": name,
        })
        for name in MACHINE_PROPERTIES if name in available
    }


def query_gce_threads(client: QMPClient) -> list[dict[str, int]]:
    gce_base = 0x10238000
    words = parse_hmp_words(client.hmp(f"xp /1088wx 0x{gce_base:x}"))
    threads: list[dict[str, int]] = []
    registers = {
        "warm-reset": 0x00,
        "enable": 0x04,
        "suspend": 0x08,
        "status": 0x0c,
        "irq-status": 0x10,
        "irq-enable": 0x14,
        "current": 0x20,
        "end": 0x24,
        "wait-token": 0x30,
        "configuration": 0x40,
    }
    for index in range(32):
        base = gce_base + 0x100 + index * 0x80
        state = {name: words.get(base + offset, 0)
                 for name, offset in registers.items()}
        if any(state.values()):
            state["thread"] = index
            threads.append(state)
    return threads


def take_snapshot(client: QMPClient, include_register_text: bool) -> dict[str, Any]:
    registers = client.hmp("info registers -a")
    parsed_cpus = parse_cpu_registers(registers)
    stacks: dict[str, str] = {}
    for cpu in parsed_cpus:
        if "sp" in cpu:
            client.hmp(f"cpu {cpu['cpu-index']}")
            stacks[f"cpu{cpu['cpu-index']}"] = client.hmp(
                f"x /16wx 0x{cpu['sp']:x}")

    snapshot: dict[str, Any] = {
        "captured-monotonic": time.monotonic(),
        "status": client.execute("query-status"),
        "cpus-fast": client.execute("query-cpus-fast"),
        "cpus": parsed_cpus,
        "stacks-virtual": stacks,
        "machine-state": query_machine(client),
        "hwtcon-state": query_hwtcon(client),
        "gce-threads": query_gce_threads(client),
        "mmio": {
            "apxgpt": client.hmp("xp /16wx 0x10008000"),
            "dvfsrc": client.hmp("xp /8wx 0x10012000"),
            "iommu": client.hmp("xp /16wx 0x10209000"),
            "gce": client.hmp("xp /16wx 0x10238000"),
            "hwtcon": client.hmp("xp /32wx 0x14000000"),
            "mdp-rdma": client.hmp("xp /16wx 0x15007000"),
            "mdp-rdma-source": client.hmp("xp /4wx 0x15007f00"),
        },
    }
    if include_register_text:
        snapshot["registers"] = registers
    return snapshot


def synchronized_snapshot(client: QMPClient,
                          include_register_text: bool) -> dict[str, Any]:
    initial_status = client.execute("query-status")
    was_running = initial_status.get("running", False)
    if was_running:
        client.execute("stop")
        while client.execute("query-status").get("running", True):
            time.sleep(0.01)
    try:
        snapshot = take_snapshot(client, include_register_text)
        # Report the state observed by the caller, not the temporary pause
        # used to make CPU registers, stacks, and MMIO mutually consistent.
        snapshot["status"] = initial_status
        return snapshot
    finally:
        if was_running:
            client.execute("cont")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--socket", type=Path,
                        help="explicit QMP Unix socket path")
    parser.add_argument("--machine",
                        help="persistent machine name under machines/")
    parser.add_argument("--timeout", type=float, default=5.0,
                        help="connection and command timeout (default: 5s)")
    subparsers = parser.add_subparsers(dest="action", required=True)

    subparsers.add_parser("status", help="query standard VM run state")
    subparsers.add_parser("stop", help="pause the VM")
    subparsers.add_parser("cont", help="resume the VM")
    subparsers.add_parser("quit", help="shut down QEMU")
    subparsers.add_parser(
        "display", help="query Bellatrix HWTCON and scanout state")
    subparsers.add_parser(
        "machine", help="query Bellatrix board, patch, and IDME state")

    hmp_parser = subparsers.add_parser(
        "hmp", help="execute an arbitrary human-monitor command")
    hmp_parser.add_argument("command", nargs=argparse.REMAINDER)

    qmp_parser = subparsers.add_parser(
        "qmp", help="execute an arbitrary QMP command")
    qmp_parser.add_argument("command")
    qmp_parser.add_argument("--arguments", type=parse_arguments, default=None)

    snapshot_parser = subparsers.add_parser(
        "snapshot", help="capture synchronized Bellatrix device state")
    snapshot_parser.add_argument("--register-text", action="store_true")
    snapshot_parser.add_argument("--output", type=Path)

    sample_parser = subparsers.add_parser(
        "sample", help="capture repeated synchronized Bellatrix snapshots")
    sample_parser.add_argument("--count", type=int, default=5)
    sample_parser.add_argument("--interval", type=float, default=2.0)
    sample_parser.add_argument("--output", type=Path)

    observe_parser = subparsers.add_parser(
        "observe-display",
        help="sample live display state without pausing the VM")
    observe_parser.add_argument("--count", type=int, default=20)
    observe_parser.add_argument("--interval", type=float, default=0.5)
    observe_parser.add_argument("--screenshots", type=Path)
    observe_parser.add_argument("--output", type=Path)
    observe_parser.add_argument(
        "--changes-only", action="store_true",
        help="poll cheaply and capture only pipeline-trigger transitions")

    screen_parser = subparsers.add_parser(
        "screendump", help="save the active QEMU scanout as PNG or PPM")
    screen_parser.add_argument("path", type=Path)

    tap_parser = subparsers.add_parser(
        "tap", help="inject a Bellatrix panel-coordinate touch")
    tap_parser.add_argument("x", type=int)
    tap_parser.add_argument("y", type=int)
    tap_parser.add_argument("--hold", type=float, default=0.08)

    memory_parser = subparsers.add_parser(
        "memory", help="read virtual or physical guest words")
    memory_parser.add_argument("address", type=lambda value: int(value, 0))
    memory_parser.add_argument("--words", type=int, default=16)
    memory_parser.add_argument("--physical", action="store_true")

    map_parser = subparsers.add_parser(
        "map", help="map a guest virtual range to physical ranges")
    map_parser.add_argument("address", type=lambda value: int(value, 0))
    map_parser.add_argument("size", type=lambda value: int(value, 0))
    map_parser.add_argument("--cpu", type=int, default=0)
    map_parser.add_argument("--page-size", type=lambda value: int(value, 0),
                            default=4096)

    dump_parser = subparsers.add_parser(
        "dump", help="save a virtual or physical guest memory range")
    dump_parser.add_argument("address", type=lambda value: int(value, 0))
    dump_parser.add_argument("size", type=lambda value: int(value, 0))
    dump_parser.add_argument("path", type=Path)
    dump_parser.add_argument("--physical", action="store_true")
    return parser


def emit_json(value: Any, output: Path | None = None) -> None:
    rendered = json.dumps(value, indent=2) + "\n"
    if output is None:
        sys.stdout.write(rendered)
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered)


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.machine and args.socket:
        parser.error("--machine and --socket are mutually exclusive")
    if args.machine:
        if Path(args.machine).name != args.machine:
            parser.error("machine name cannot contain a path separator")
        args.socket = (
            REPO_ROOT / "machines" / args.machine /
            f"{args.machine}.qmp.sock"
        )
    elif args.socket is None:
        parser.error("one of --machine or --socket is required")
    try:
        with QMPClient(args.socket, args.timeout) as client:
            if args.action == "status":
                emit_json(client.execute("query-status"))
            elif args.action in {"stop", "cont", "quit"}:
                emit_json(client.execute(args.action))
            elif args.action == "display":
                emit_json(query_hwtcon(client))
            elif args.action == "machine":
                emit_json(query_machine(client))
            elif args.action == "hmp":
                if not args.command:
                    raise QMPError("hmp requires a command")
                sys.stdout.write(client.hmp(" ".join(args.command)))
            elif args.action == "qmp":
                emit_json(client.execute(args.command, args.arguments))
            elif args.action == "snapshot":
                emit_json(synchronized_snapshot(client, args.register_text),
                          args.output)
            elif args.action == "sample":
                if args.count < 1 or args.interval < 0:
                    raise QMPError("sample count must be positive and interval nonnegative")
                samples = []
                for index in range(args.count):
                    samples.append(synchronized_snapshot(client, False))
                    if index + 1 < args.count:
                        time.sleep(args.interval)
                emit_json(samples, args.output)
            elif args.action == "observe-display":
                if args.count < 1 or args.interval < 0:
                    raise QMPError(
                        "sample count must be positive and interval nonnegative")
                if args.screenshots is not None:
                    args.screenshots.mkdir(parents=True, exist_ok=True)
                samples = []
                available = {
                    item["name"] for item in client.execute("qom-list", {
                        "path": HWTCON_QOM_PATH,
                    })
                }
                previous_trigger = None
                for index in range(args.count):
                    if args.changes_only:
                        trigger = client.execute("qom-get", {
                            "path": HWTCON_QOM_PATH,
                            "property": "pipeline-triggers",
                        })
                        if trigger == previous_trigger:
                            if index + 1 < args.count:
                                time.sleep(args.interval)
                            continue
                        previous_trigger = trigger
                    sample = {
                        "captured-monotonic": time.monotonic(),
                        "status": client.execute("query-status"),
                        "hwtcon-state": query_hwtcon_properties(
                            client, OBSERVE_HWTCON_PROPERTIES, available),
                    }
                    if args.screenshots is not None:
                        screen_path = (
                            args.screenshots / f"display-{index:04d}.png"
                        ).resolve()
                        client.execute("screendump", {
                            "filename": str(screen_path),
                            "format": "png",
                        })
                        sample["screendump"] = str(screen_path)
                    samples.append(sample)
                    if index + 1 < args.count:
                        time.sleep(args.interval)
                emit_json(samples, args.output)
            elif args.action == "screendump":
                args.path.parent.mkdir(parents=True, exist_ok=True)
                suffix = args.path.suffix.lower()
                if suffix not in {".png", ".ppm"}:
                    raise QMPError("screendump path must end in .png or .ppm")
                emit_json(client.execute("screendump", {
                    "filename": str(args.path),
                    "format": suffix[1:],
                }))
            elif args.action == "tap":
                if not (0 <= args.x <= 1272 and 0 <= args.y <= 1696):
                    raise QMPError(
                        "tap coordinates must be within 0..1272 x 0..1696")
                if args.hold < 0:
                    raise QMPError("tap hold time must be nonnegative")
                # The QEMU input core scales absolute axes with integer-floor
                # division.  Use the inverse ceiling so the touchscreen
                # driver receives the exact requested panel coordinate.
                abs_x = (args.x * 0x7fff + 1272 - 1) // 1272
                abs_y = (args.y * 0x7fff + 1696 - 1) // 1696
                down = client.execute("input-send-event", {
                    "events": [
                        {"type": "abs", "data": {
                            "axis": "x", "value": abs_x}},
                        {"type": "abs", "data": {
                            "axis": "y", "value": abs_y}},
                        {"type": "btn", "data": {
                            "button": "left", "down": True}},
                    ],
                })
                time.sleep(args.hold)
                up = client.execute("input-send-event", {
                    "events": [
                        {"type": "btn", "data": {
                            "button": "left", "down": False}},
                    ],
                })
                emit_json({
                    "screen": {"x": args.x, "y": args.y},
                    "absolute": {"x": abs_x, "y": abs_y},
                    "down": down,
                    "up": up,
                })
            elif args.action == "memory":
                prefix = "xp" if args.physical else "x"
                sys.stdout.write(client.hmp(
                    f"{prefix} /{args.words}wx 0x{args.address:x}"))
            elif args.action == "map":
                initial_status = client.execute("query-status")
                was_running = initial_status.get("running", False)
                if was_running:
                    client.execute("stop")
                try:
                    emit_json(virtual_memory_map(
                        client, args.address, args.size, args.cpu,
                        args.page_size))
                finally:
                    if was_running:
                        client.execute("cont")
            elif args.action == "dump":
                args.path.parent.mkdir(parents=True, exist_ok=True)
                command = "pmemsave" if args.physical else "memsave"
                sys.stdout.write(client.hmp(
                    f"{command} 0x{args.address:x} 0x{args.size:x} "
                    f"{json.dumps(str(args.path))}"))
    except (OSError, QMPError) as error:
        print(f"eink-qmp: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
