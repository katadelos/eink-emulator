"""Explicit synthetic waveform input for the stock HWTCON loaders.

Layout: Amazon Linux 4.9/5.15 hwtcon_v2 and Kobo Linux 4.9 hwtcon
hal/hwtcon_wf_lut_config.{c,h}.
Voltages: mt8113-barolo.dts and mediatek/pmic/fiti/fiti_core.c.
This is an emulator fixture, not panel calibration or a factory waveform.
"""
from __future__ import annotations

import argparse
import gzip
import json
import struct
from pathlib import Path

PRODUCTS = (
    "barolo", "pisco", "cava", "malbec", "rossini",
    "sangria", "sangria-color", "elipsa2e",
)
DUAL_MODE_PRODUCTS = {"sangria", "sangria-color"}
TEMPERATURES = 32
MODES = 16
FRAME_BYTES = 0x100
FRAMES = 2
DATA_START = 0x1100


def build_waveform(product: str = "barolo") -> bytes:
    if product not in PRODUCTS:
        raise ValueError(f"unsupported Bellatrix waveform product: {product}")
    # Bellatrix4's dual-scan driver reads 36 modes in 48-entry rows.
    # Other HWTCON loaders use 16-entry rows at the original offsets.
    dual = product in DUAL_MODE_PRODUCTS
    modes, stride = (36, 48) if dual else (MODES, MODES)
    addresses, lengths, data_start = (
        (0x3C0, 0x1BC0, 0x3400) if dual else (0xC0, 0x8C0, DATA_START)
    )
    data = bytearray(data_start + modes * FRAME_BYTES * FRAMES)
    name = f"SYNTHETIC_{product.upper()}_HWTCON_V2_EMULATOR_ONLY".encode("ascii")
    data[:len(name)] = name
    data[0x50] = 0x59  # WF_MODE_VERSION_TL: includes swipe and night DU modes.
    data[0x53] = 2     # Stock driver reports WAVEFORM_TYPE_5BIT.
    data[0x56] = 1     # Synthetic revision, not a factory revision.
    # 31 boundaries produce 32 zones; the loader rejects 32 boundaries.
    thresholds = bytes(range(1, 62, 2))
    data[0x80:0x80 + len(thresholds)] = thresholds
    data[0xA2] = len(thresholds)
    # Positive magnitudes, in the FT9930 header's 12.5 mV units.
    for offset, millivolts in ((0x62, 15000), (0x64, 15000),
                              (0x66, 28000), (0x68, 20000), (0x7C, 2900)):
        struct.pack_into(">H", data, offset, millivolts * 2 // 25)
    data[0x74] = 251  # XON_LEN=2510; delay=0 and VGH/VGL extensions=0.
    data[0x7E] = 30   # VGHNM_EXT=1500 mV.
    # 32x32 transitions, four two-bit symbols per byte. Direction is an
    # explicit emulator convention, not a claim about physical voltage codes.
    frame = bytearray(FRAME_BYTES)
    for previous in range(32):
        for target in range(32):
            symbol = 0 if target == previous else (1 if target > previous else 2)
            index = previous * 32 + target
            frame[index // 4] |= symbol << (2 * (index & 3))
    for mode in range(modes):
        address = data_start + mode * FRAME_BYTES * FRAMES
        data[address:address + FRAME_BYTES] = frame
        # The second frame is neutral; nonzero lengths prevent underflow in
        # hardware's length-minus-one register programming.
        for temperature in range(TEMPERATURES):
            slot = 4 * (temperature * stride + mode)
            struct.pack_into(">I", data, addresses + slot, address)
            struct.pack_into(">I", data, lengths + slot, FRAME_BYTES * FRAMES)
    return bytes(data)


def write_waveform(directory: Path, product: str = "barolo") -> Path:
    raw = build_waveform(product)
    directory.mkdir(parents=True, exist_ok=True)
    output = directory / f"{product.upper()}_SYNTHETIC_HWTCON_V2.wrf.gz"
    output.write_bytes(gzip.compress(raw, mtime=0))
    (directory / "README.json").write_text(json.dumps({
        "product": product, "synthetic": True, "file": output.name,
        "format": "HWTCON, 256-byte frames",
        "temperatures": TEMPERATURES,
        "modes": 36 if product in DUAL_MODE_PRODUCTS else MODES,
        "frames_per_mode": FRAMES, "raw_bytes": len(raw),
        "physical_panel_calibration": False,
    }, indent=2) + "\n")
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--product", choices=PRODUCTS, required=True)
    args = parser.parse_args()
    print(write_waveform(args.directory, args.product))


if __name__ == "__main__":
    main()
