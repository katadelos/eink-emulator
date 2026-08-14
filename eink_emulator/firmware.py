"""Import vendor firmware packages into the local firmware catalogue."""

from __future__ import annotations

import gzip
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any


def import_recovery(
    *,
    package: Path,
    destination: Path,
    definition: dict[str, Any],
) -> dict[str, Path]:
    """Extract and atomically install a model's Kindle recovery artifacts."""
    kindletool = shutil.which("kindletool")
    if not kindletool:
        raise SystemExit("kindletool is required to import Kindle recovery firmware")
    if not package.is_file():
        raise SystemExit(f"firmware package does not exist: {package}")
    if destination.exists():
        raise SystemExit(f"firmware destination already exists: {destination}")

    import_spec = definition.get("recovery_import")
    if not isinstance(import_spec, dict):
        raise SystemExit("this model does not support recovery-package import")

    required = definition.get("firmware", {})
    if set(import_spec) != set(required):
        raise SystemExit("recovery import does not provide every required artifact")
    for role, candidates in required.items():
        if not isinstance(candidates, list) or len(candidates) != 1:
            raise SystemExit(f"recovery import requires one output name for {role}")

    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=f".{destination.name}-import-", dir=destination.parent
    ) as temporary:
        workspace = Path(temporary)
        extracted = workspace / "extracted"
        prepared = workspace / "prepared"
        extracted.mkdir()
        prepared.mkdir()

        subprocess.run(
            [kindletool, "extract", str(package), str(extracted)],
            check=True,
        )

        installed: dict[str, Path] = {}
        for role, relative_source in import_spec.items():
            source = extracted / relative_source
            if not source.is_file():
                raise SystemExit(
                    f"recovery package is missing {role}: {relative_source}"
                )
            output_name = required[role][0]
            output = prepared / output_name
            if source.suffix == ".gz" and output.suffix != ".gz":
                with gzip.open(source, "rb") as compressed, output.open("wb") as target:
                    shutil.copyfileobj(compressed, target)
            else:
                shutil.copy2(source, output)
            installed[role] = destination / output_name

        prepared.replace(destination)
    return installed
