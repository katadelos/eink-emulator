#!/usr/bin/env python3
"""Render the bundled Kindle MOTD using host-side toilet and lolcat."""

import argparse
from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[1]
PROJECTS = (
    ("k2", "Apps, packages and KOReader"),
    ("kppmods", "Make the stock Kindle UI your own"),
    ("kindle-epub", "Read EPUBs in the stock reader"),
    ("supernet", "SSH over USB and Wi-Fi"),
    ("react-kindle", "Build Kindle apps with React"),
)


def compact_colours(rendered: bytes) -> bytes:
    """Keep visible colours while omitting redundant and whitespace-only SGRs."""
    colour = written = b"\x1b[39m"
    output = bytearray()
    for token in re.split(rb"(\x1b\[[0-9;]*m)", rendered):
        if token.startswith(b"\x1b["):
            colour = token
            continue
        for byte in token:
            if byte not in b" \t\r\n" and colour != written:
                output.extend(colour)
                written = colour
            output.append(byte)
    if written != b"\x1b[39m":
        output.extend(b"\x1b[39m")
    return b"\n".join(line.rstrip(b" \t") for line in bytes(output).split(b"\n"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--font-dir", default="/opt/homebrew/share/figlet/fonts/")
    args = parser.parse_args()
    title = subprocess.run(
        ["toilet", "-f", "cyberlarge", "-d", args.font_dir],
        input=b"  eink\nemulator\n", capture_output=True, check=True,
    ).stdout
    rendered = subprocess.run(
        ["lolcat", "-F", "0.5", "-f"],
        input=title, capture_output=True, check=True,
    ).stdout
    banner = compact_colours(rendered) + b"\nhttps://github.com/katadelos/eink-emulator\n\n"
    for name, description in PROJECTS:
        banner += f"  \x1b[36m{name:<12}\x1b[39m  {description}\n".encode("ascii")
    banner += b"\n  Explore: https://github.com/katadelos\n"
    # Dropbear's built-in MOTD display reads at most 2000 bytes.
    if len(banner) > 2000:
        raise SystemExit(f"MOTD exceeds Dropbear's 2000-byte limit: {len(banner)} bytes")
    output = ROOT / "guest-additions/kindle/eink-motd"
    output.write_bytes(banner)
    print(f"Wrote {output} ({len(banner)} bytes)")


if __name__ == "__main__":
    main()
