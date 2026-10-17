"""Find and fetch Kindle update packages catalogued by FTVDB.

FTVDB (https://ftvdb.com/kindle/firmware/) records Amazon's public update URLs
and checksums without hosting the files. Its open-data snapshot is read here
instead of the HTML pages; packages come directly from Amazon.
"""

from __future__ import annotations

import hashlib
import json
import re
import socket
import sys
import threading
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

INDEX_URL = "https://raw.githubusercontent.com/FTVDB/FTVDB/main/database/firmware/{package}.json"
USER_AGENT = "eink-emulator"
# Version names become directory names, so accept only dotted numbers.
VERSION_RE = re.compile(r"^[0-9]+(?:\.[0-9]+)*$")
MD5_RE = re.compile(r"^[0-9a-f]{32}$")
ATTEMPTS = 4
# Abort and resume a connection that delivers less than this per window.
STALL_WINDOW = 60
STALL_BYTES = 256 * 1024


@dataclass(frozen=True)
class Release:
    version: str
    code: int
    uploaded: str
    md5: str
    urls: tuple[str, ...]
    # Pinned releases from other sources carry a SHA-256 instead of an MD5.
    sha256: str = ""

    def checksum(self) -> tuple[str, str]:
        return ("sha256", self.sha256) if self.sha256 else ("md5", self.md5)


def valid_version(value: str) -> bool:
    return bool(VERSION_RE.fullmatch(value))


def releases(package: str) -> list[Release]:
    """Return a package's releases, oldest first, merging mirrored records."""
    url = INDEX_URL.format(package=package)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            records = json.load(response)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            raise SystemExit(f"FTVDB lists no firmware for {package}")
        raise SystemExit(f"cannot read FTVDB firmware list: {error}")
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        raise SystemExit(f"cannot read FTVDB firmware list: {error}")
    if not isinstance(records, list):
        raise SystemExit("unexpected FTVDB firmware list format")

    grouped: dict[str, dict] = {}
    for record in records:
        try:
            version = record["versionName"]
            code = int(record["versionCode"])
            md5 = record["md5"].lower()
            url = record["url"]
        except (KeyError, TypeError, ValueError, AttributeError):
            continue
        if not valid_version(version) or not MD5_RE.fullmatch(md5) or not url.startswith("https://"):
            continue
        entry = grouped.setdefault(version, {
            "code": code, "uploaded": record.get("uploaded", ""), "md5": md5, "urls": [],
        })
        if entry["md5"] != md5:
            # Mirrors of one version share a checksum; a conflict is unsafe to guess at.
            entry["conflict"] = True
        if url not in entry["urls"]:
            entry["urls"].append(url)

    result = [
        Release(version, entry["code"], entry["uploaded"], entry["md5"], tuple(entry["urls"]))
        for version, entry in grouped.items() if not entry.get("conflict")
    ]
    return sorted(result, key=lambda release: (release.code, release.version))


def file_digest(path: Path, algorithm: str) -> str:
    digest = hashlib.new(algorithm, usedforsecurity=False)
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fetch(release: Release, destination: Path) -> Path:
    """Download a release to destination, trying each mirror until one verifies."""
    algorithm, expected = release.checksum()
    if destination.is_file():
        if file_digest(destination, algorithm) == expected:
            return destination
        destination.unlink()
    destination.parent.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []
    for url in release.urls:
        # One partial file per mirror, so an interrupted run resumes without
        # splicing bytes from different sources.
        tag = hashlib.sha256(url.encode()).hexdigest()[:12]
        partial = destination.with_name(f"{destination.name}.{tag}.part")
        resuming = " (resuming)" if partial.is_file() else ""
        print(f"Downloading firmware {release.version} from {url}{resuming}", flush=True)
        for attempt in range(1, ATTEMPTS + 1):
            try:
                download(url, partial)
                error = None
                break
            except (urllib.error.URLError, TimeoutError, OSError) as caught:
                error = caught
                # Missing or forbidden files will not appear on retry.
                if isinstance(caught, urllib.error.HTTPError) and caught.code < 500:
                    break
                if attempt < ATTEMPTS:
                    print(f"  interrupted ({caught}); resuming", file=sys.stderr, flush=True)
        if error is not None:
            # Keep the bytes received so far; a later run resumes them.
            failures.append(f"{url}: {error}")
            continue
        digest = file_digest(partial, algorithm)
        if digest != expected:
            failures.append(f"{url}: {algorithm.upper()} {digest} does not match {expected}")
            partial.unlink(missing_ok=True)
            continue
        partial.replace(destination)
        for leftover in destination.parent.glob(f"{destination.name}.*.part"):
            leftover.unlink()
        return destination
    raise SystemExit(f"cannot download firmware {release.version}:\n  " + "\n  ".join(failures))


def download(url: str, output: Path) -> None:
    """Download url to output, resuming from any bytes already there."""
    offset = output.stat().st_size if output.is_file() else 0
    headers = {"User-Agent": USER_AGENT}
    if offset:
        headers["Range"] = f"bytes={offset}-"
    request = urllib.request.Request(url, headers=headers)
    try:
        response = urllib.request.urlopen(request, timeout=60)
    except urllib.error.HTTPError as error:
        if error.code == 416 and offset:
            return  # Already complete; the checksum decides.
        raise
    with response:
        if offset and response.status != 206:
            offset = 0  # The server ignored the range; start again.
        total = offset + int(response.headers.get("Content-Length") or 0)
        received = offset
        interactive = sys.stderr.isatty()
        stalled = threading.Event()
        done = threading.Event()
        progress = [received]

        def watchdog() -> None:
            # A dribbling TLS connection keeps each read blocked inside the SSL
            # layer, so the socket timeout never fires; shut the socket instead.
            sock = getattr(getattr(response.fp, "raw", None), "_sock", None)
            last = progress[0]
            while not done.wait(STALL_WINDOW):
                if progress[0] - last < STALL_BYTES:
                    stalled.set()
                    if sock is not None:
                        try:
                            # Bypass SSLSocket.shutdown, which tears down SSL state.
                            socket.socket.shutdown(sock, socket.SHUT_RDWR)
                        except OSError:
                            pass
                    return
                last = progress[0]

        threading.Thread(target=watchdog, daemon=True).start()
        try:
            with output.open("ab" if offset else "wb") as target:
                for chunk in iter(lambda: response.read1(1024 * 1024), b""):
                    target.write(chunk)
                    received += len(chunk)
                    progress[0] = received
                    if interactive and total:
                        print(
                            f"\r  {received * 100 // total:3d}% "
                            f"({received / 2**20:.0f}/{total / 2**20:.0f} MiB)",
                            end="", file=sys.stderr, flush=True,
                        )
        except OSError:
            if not stalled.is_set():
                raise
        finally:
            done.set()
        if interactive and total:
            print(file=sys.stderr)
        if stalled.is_set():
            raise TimeoutError(f"download stalled after {received} bytes")
        if total > offset and received != total:
            raise OSError(f"download ended after {received} of {total} bytes")
