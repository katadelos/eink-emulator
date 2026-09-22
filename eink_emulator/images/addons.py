"""Pinned, opt-in KUAL/MRPI preparation for the K4–Oasis 3 firmware family."""

from __future__ import annotations

import io
import json
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

from . import rootfs

ROOT = Path(__file__).resolve().parents[2]
SOURCES = ROOT / "guest-additions" / "kindle"
DOWNLOADS = SOURCES / "downloads"
KINDLETS = {"kindle-4": "1.0", "kindle-touch": "2.0", "kindle-paperwhite-1": "2.0"}
SUPPORTED = set(KINDLETS) | {
    "kindle-paperwhite-2", "kindle-basic-2014", "kindle-voyage",
    "kindle-paperwhite-3", "kindle-oasis-1", "kindle-basic-2016",
    "kindle-oasis-2", "kindle-paperwhite-4", "kindle-kt4", "kindle-oasis-3",
}
HARD_FLOAT = {"kindle-paperwhite-4", "kindle-kt4", "kindle-oasis-3"}


def plan(model: str, *, jailbreak: bool, kual: bool, mrpi: bool) -> dict[str, Any] | None:
    if not (jailbreak or kual or mrpi):
        return None
    if model not in SUPPORTED:
        raise SystemExit("Kindle add-ons support Kindle 4 through Oasis 3; see docs/kindle-addons.md")
    kual = kual or mrpi
    selected = {"jailbreak"}
    if model != "kindle-4" or kual:
        selected.add("mkk" if model in KINDLETS else "hotfix")
    if kual:
        selected.add("kual_kindlet" if model in KINDLETS else "kual_booklet")
    if mrpi:
        selected.add("mrpi")
    catalogue = json.loads((SOURCES / "assets.json").read_text())
    return {
        "model": model, "jailbreak": True, "kual": kual, "mrpi": mrpi,
        "assets": {name: catalogue[name] for name in sorted(selected)},
    }


def download(asset: dict[str, str]) -> Path:
    """Cache a versioned asset; publish it only after a complete download."""
    destination = DOWNLOADS / asset["version"] / asset["url"].rsplit("/", 1)[-1]
    if destination.is_file():
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {destination.name}", flush=True)
    with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as output:
        temporary = Path(output.name)
        try:
            request = urllib.request.Request(asset["url"], headers={"User-Agent": "eink-emulator"})
            with urllib.request.urlopen(request, timeout=60) as response:
                shutil.copyfileobj(response, output)
            output.close()
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)
    return destination


def tar_member(archive: Path | bytes, name: str) -> bytes:
    options = {"fileobj": io.BytesIO(archive)} if isinstance(archive, bytes) else {"name": archive}
    with tarfile.open(**options) as source:
        member = source.extractfile(name)
        if member is None:
            raise ValueError(f"missing regular file in asset: {name}")
        return member.read()


def extract_update(package: Path, destination: Path) -> None:
    kindletool = shutil.which("kindletool")
    if not kindletool:
        raise SystemExit("KindleTool is required for booklet/root-helper assets; install it and retry")
    subprocess.run([kindletool, "extract", str(package), str(destination)], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def write(directory: Path, name: str, contents: bytes, mode: int = 0o644) -> None:
    path = directory / name.lstrip("/")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(contents)
    path.chmod(mode)


def kindlet_keystore(kindlet: bytes, existing: bytes, work: Path) -> bytes:
    """Trust the original KUAL signatures, including the renewed 2025 certs."""
    for executable in ("keytool", "openssl"):
        if not shutil.which(executable):
            raise SystemExit(f"{executable} is required to prepare the KUAL Kindlet keystore")
    keystore = work / "developer.keystore"
    keystore.write_bytes(existing)
    with zipfile.ZipFile(io.BytesIO(kindlet)) as archive:
        for alias in ("dntest", "ditest", "dktest"):
            signature = archive.read(f"META-INF/{alias.upper()}.RSA")
            result = subprocess.run(["openssl", "pkcs7", "-inform", "DER", "-print_certs"],
                                    input=signature, capture_output=True, check=True)
            certificate = work / f"{alias}.pem"
            certificate.write_bytes(result.stdout)
            common = ["-keystore", str(keystore), "-storepass", "password", "-alias", alias]
            for command in (["keytool", "-delete", *common],
                            ["keytool", "-importcert", "-noprompt", *common, "-file", str(certificate)]):
                subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    return keystore.read_bytes()


def prepare(source: Path, output: Path, options: dict[str, Any]) -> Path:
    """Inject root files plus a first-boot data-volume payload into a copy."""
    model = options["model"]
    assets = {name: download(asset) for name, asset in options["assets"].items()}
    with tempfile.TemporaryDirectory(prefix="eink-addons-", dir=output.parent) as temporary:
        work = Path(temporary)
        system, data = work / "root", work / "data"
        system.mkdir()
        data.mkdir()
        key = tar_member(assets["jailbreak"], "K4_JailBreak/src/payload/jailbreak.pem")
        write(system, "/etc/uks/pubdevkey01.pem", key)
        for flag in ("MNTUS_EXEC", "PRE_GM_DEBUGGING_FEATURES_ENABLED__REMOVE_AT_GMC"):
            write(system, flag, b"")
        if "mkk" in assets:
            prefix = "DevCerts/src/install/"
            if model != "kindle-4":
                write(data, "/var/local/mkk/gandalf", tar_member(assets["mkk"], prefix + "gandalf"), 0o4755)
            if options["kual"]:
                kindlet = tar_member(assets["kual_kindlet"], f"KUAL-KDK-{KINDLETS[model]}.azw2")
                write(data, f"/mnt/us/documents/KUAL-KDK-{KINDLETS[model]}.azw2", kindlet)
                keystore = kindlet_keystore(kindlet, tar_member(assets["mkk"], prefix + "developer.keystore"), work)
                write(data, "/var/local/java/keystore/developer.keystore", keystore)
                write(data, "/var/local/mkk/developer.keystore", keystore)
                write(system, "/opt/amazon/ebook/lib/json_simple-1.1.jar",
                      tar_member(assets["mkk"], prefix + "json_simple-1.1.jar"))
        if "hotfix" in assets:
            unpacked = work / "hotfix"
            extract_update(assets["hotfix"], unpacked)
            arch = "armhf" if model in HARD_FLOAT else "armel"
            write(data, "/var/local/mkk/gandalf",
                  tar_member(unpacked / "kmc.tar", f"./{arch}/bin/gandalf"), 0o4755)
        if "kual_booklet" in assets:
            package = work / "kual.bin"
            package.write_bytes(tar_member(assets["kual_booklet"], "Update_KUALBooklet_c6ac782_install.bin"))
            unpacked = work / "kual"
            extract_update(package, unpacked)
            write(system, "/opt/amazon/ebook/booklet/KUALBooklet.jar", (unpacked / "KUALBooklet.jar").read_bytes())
            sql = (unpacked / "appreg.install.sql").read_bytes()
            if model == "kindle-voyage":
                sql += (unpacked / "whispertouch.install.sql").read_bytes()
            write(system, "/usr/share/eink-addons/appreg.install.sql", sql)
            write(data, "/mnt/us/documents/KUAL.kual", b"")
        if "mrpi" in assets:
            with zipfile.ZipFile(assets["mrpi"]) as archive:
                for entry in archive.infolist():
                    path = PurePosixPath(entry.filename)
                    if not entry.filename.startswith("extensions/"):
                        continue
                    if ".." in path.parts:
                        raise ValueError("unsafe MRPI archive path")
                    if entry.is_dir():
                        (data / "mnt/us" / path).mkdir(parents=True, exist_ok=True)
                        continue
                    mode = (entry.external_attr >> 16) & 0o777
                    write(data, "/mnt/us/" + entry.filename, archive.read(entry), mode or 0o644)
            (data / "mnt/us/mrpackages").mkdir(parents=True)
        # A receipt records exactly which pinned assets produced this base.
        write(system, "/etc/eink-addons.json", (json.dumps(options, indent=2) + "\n").encode())
        write(system, "/usr/sbin/qemu-kindle-addons", (SOURCES / "qemu-kindle-addons").read_bytes(), 0o755)
        payload = system / "usr/share/eink-addons/data.tar.gz"
        payload.parent.mkdir(parents=True, exist_ok=True)
        for directory in data.rglob("*"):
            if directory.is_dir():
                directory.chmod(0o755)
        with tarfile.open(payload, "w:gz", format=tarfile.USTAR_FORMAT) as archive:
            def root_owner(info: tarfile.TarInfo) -> tarfile.TarInfo:
                info.uid = info.gid = 0
                info.uname = info.gname = "root"
                return info
            for path in sorted(data.iterdir()):
                archive.add(path, arcname=path.name, filter=root_owner)
        if model == "kindle-4":
            write(system, "/etc/rc5.d/S92qemu-kindle-addons", b"#!/bin/sh\n/usr/sbin/qemu-kindle-addons\n", 0o755)
        else:
            write(system, "/etc/upstart/qemu-kindle-addons.conf", b'''# Block framework startup until optional data-volume setup completes.
start on starting framework
task
exec /usr/sbin/qemu-kindle-addons
''')
        rootfs.copy_source(source, output)
        commands = []
        for path in sorted(system.rglob("*")):
            destination = "/" + path.relative_to(system).as_posix()
            if path.is_dir():
                commands.append(f"mkdir {destination}")
            else:
                commands.extend([f"rm {destination}", f'write "{path}" {destination}',
                                 f"set_inode_field {destination} mode {0o100000 | (path.stat().st_mode & 0o7777):07o}",
                                 f"set_inode_field {destination} uid 0", f"set_inode_field {destination} gid 0"])
        rootfs.run_many(output, commands, writable=True)
        # debugfs does not propagate allocation failures through its exit code.
        verified = work / "verify.tar.gz"
        rootfs.run(output, f'dump /usr/share/eink-addons/data.tar.gz "{verified}"')
        if not verified.is_file() or verified.read_bytes() != payload.read_bytes():
            raise SystemExit("cannot write add-on payload to rootfs (check free filesystem space)")
    return output
