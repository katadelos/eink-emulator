"""The shared host login identity for emulated readers."""

from __future__ import annotations

import fcntl
import os
import shutil
import subprocess
import tempfile
from pathlib import Path


LOGIN_KEY = Path(__file__).resolve().parents[1] / "build" / "ssh" / "id_ed25519"


def ensure_login_key() -> Path:
    """Create one private login key locally; return its public-key file."""
    keygen = shutil.which("ssh-keygen")
    if not keygen:
        raise SystemExit("ssh-keygen is required to prepare guest SSH access")
    LOGIN_KEY.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    public_key = LOGIN_KEY.with_suffix(".pub")
    # Parallel image creation must authorize the same identity in every image.
    with (LOGIN_KEY.parent / ".lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if not LOGIN_KEY.exists():
            with tempfile.TemporaryDirectory(dir=LOGIN_KEY.parent) as temporary:
                staging = Path(temporary) / "id_ed25519"
                subprocess.run([
                    keygen, "-q", "-t", "ed25519", "-N", "", "-C", "eink-emulator",
                    "-f", str(staging),
                ], check=True)
                staging.replace(LOGIN_KEY)
                staging.with_suffix(".pub").replace(public_key)
        os.chmod(LOGIN_KEY, 0o600)
        # A copied/replaced private key may have a stale public-key sidecar.
        # Always derive the identity used by SSH before authorizing an image.
        result = subprocess.run(
            [keygen, "-y", "-P", "", "-f", str(LOGIN_KEY)],
            check=True, capture_output=True, text=True,
        )
        identity = result.stdout.split()[:2]
        existing = public_key.read_text().split()[:2] if public_key.exists() else []
        if existing != identity:
            with tempfile.TemporaryDirectory(dir=LOGIN_KEY.parent) as temporary:
                staging = Path(temporary) / "id_ed25519.pub"
                staging.write_text(" ".join(identity) + " eink-emulator\n")
                staging.replace(public_key)
    return public_key
