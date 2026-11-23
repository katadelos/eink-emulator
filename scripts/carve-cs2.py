#!/usr/bin/env python3
"""Extract Julep firmware from a Colorsoft 2 partition-dump tar archive."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from eink_emulator.firmware import carve_ao5_dump
from eink_emulator.images.ao5 import ROOTFS_SIZES


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dump", type=Path)
    parser.add_argument("--output", type=Path,
                        default=ROOT / "firmware/kindle-colorsoft-2")
    args = parser.parse_args()
    carve_ao5_dump(
        args.dump.resolve(), args.output.resolve(),
        rootfs_size=ROOTFS_SIZES["julep"], rootfs_package="com.lab126.eink.julep.os",
        quickboot=True,
    )
    print(f"Colorsoft 2 firmware: {args.output.resolve()}")


if __name__ == "__main__":
    main()
