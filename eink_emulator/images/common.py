"""Shared image-building primitives."""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


@contextmanager
def atomic_output(output: Path) -> Iterator[Path]:
    """Yield a sibling staging path and atomically install it on success."""
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = output.with_name(f".{output.name}.tmp-{os.getpid()}")
    if staging.exists():
        staging.unlink()
    try:
        yield staging
        os.replace(staging, output)
    finally:
        staging.unlink(missing_ok=True)
