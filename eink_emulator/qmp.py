"""QMP connection shared by emulator control tools."""

from __future__ import annotations

import json
import socket
import time
from pathlib import Path
from typing import Any


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

        try:
            self.stream = self.socket.makefile("rwb", buffering=0)
            greeting = self._read_message(deadline)
            if "QMP" not in greeting:
                raise QMPError(f"invalid QMP greeting: {greeting!r}")
            self.execute("qmp_capabilities")
        except BaseException:
            self.__exit__()
            raise
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
