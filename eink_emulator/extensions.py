"""Discover Python commands supplied by local companion checkouts."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re


@dataclass(frozen=True)
class LocalCommand:
    script: Path
    help: str


def discover_commands(root: Path) -> dict[str, LocalCommand]:
    commands = {}
    for manifest in sorted(root.glob("*/eink-commands.json")):
        try:
            entries = json.loads(manifest.read_text())
            if not isinstance(entries, dict):
                raise ValueError("expected a command mapping")
            for name, entry in entries.items():
                if not re.fullmatch(r"[a-z][a-z0-9-]*", name):
                    raise ValueError(f"invalid command name: {name}")
                if name in commands:
                    raise ValueError(f"duplicate command: {name}")
                if (not isinstance(entry, dict) or
                        not isinstance(entry.get("script"), str) or
                        not isinstance(entry.get("help"), str)):
                    raise ValueError(f"{name} needs script and help strings")
                directory = manifest.parent.resolve()
                script = (directory / entry["script"]).resolve()
                if not script.is_relative_to(directory) or not script.is_file():
                    raise ValueError(f"{name} needs a script inside {directory}")
                commands[name] = LocalCommand(script, entry["help"])
        except (OSError, ValueError) as error:
            raise ValueError(f"invalid command manifest {manifest}: {error}") from error
    return commands
