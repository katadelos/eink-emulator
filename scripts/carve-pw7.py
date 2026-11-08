#!/usr/bin/env python3
"""Extract Amaro firmware from a PW7 partition-dump tar archive."""

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
                        default=ROOT / "firmware/kindle-paperwhite-7")
    args = parser.parse_args()
    carve_ao5_dump(
        args.dump.resolve(), args.output.resolve(),
        rootfs_size=ROOTFS_SIZES["amaro"], rootfs_package="com.lab126.eink.amaro.os",
    )
    print(f"PW7 firmware: {args.output.resolve()}")


if __name__ == "__main__":
    main()
