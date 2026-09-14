"""Deterministic, explicitly synthetic CS8/PA6 HWTCON V5 waveform data.

This is emulator input, not an Amazon waveform or physical panel calibration.
The file layout follows the CS8 GPL driver, specifically hwtcon_wf_file.c,
hwtcon_core.h, and pmic/FT9936/fiti_core.{c,h}. Synthetic transition symbols
are an emulator convention: 0=hold, 1=increase, 2=decrease. Their physical
voltage meaning and nibble ordering are not established by those sources.

PA6 uses the same signed V5 waveform format, 5/5-bit tables and 24-bit working
buffer as CS8. Stock U-Boot's product fixup selects Y8 and clears cfa-panel;
it does not change the waveform container or working-buffer format.
"""
from __future__ import annotations

import argparse
import gzip
import io
import json
import struct
import zlib
from pathlib import Path

FILE_NAME = "CS8_SYNTHETIC_V50.wrf.gz"
FILE_NAMES = {"cs8": FILE_NAME, "pa6": "PA6_SYNTHETIC_V50.wrf.gz"}
TEMPERATURE_TABLE_ZONES = 32
TEMPERATURE_ZONES = 30  # FT9936 fiti_core.c MAX_NUM_TS, smaller than HWTCON table.
TABLE_MODES = 48  # File stride; the CS8 kernel consumes modes 0 through 31.
ADDRESS_TABLE = 0x360
LENGTH_TABLE = 0x1B60
FRAME_BYTES = 0x200
FRAMES = 2
DATA_START = 0x3600
MODE_STRIDE = 0x600  # Two frames plus a 0x200-byte alignment/metadata gap.
NIGHT_MODES = frozenset((8, 9, 11, 12, 16, 17))

# 29 increasing threshold bytes produce 30 FT9936-compatible zones. The driver compares the
# Celsius value against these bytes; identical data in every zone is deliberate.
THRESHOLDS = bytes(range(1, 2 * TEMPERATURE_ZONES - 1, 2))


def _voltage_units(millivolts: int) -> int:
    """FT9936's waveform unit is 12.5 mV (raw * 25 / 2)."""
    return millivolts * 2 // 25


def _settings(night: bool) -> bytes:
    # wfm_setting is packed: version, extensions, XON, VGH/VGL/VCOM/VGHNM,
    # extension and reserved byte. The last 16 bytes of the 32-byte prefix
    # are reserved. Values use the driver's documented defaults, not a panel.
    return struct.pack(
        ">HBBBBHHHHBB", 0x8005 if night else 0x8004,
        0, 0, 0, 0, _voltage_units(35000), _voltage_units(35000),
        0, _voltage_units(2000), 0, 0,
    ).ljust(0x20, b"\0")


def _transition_frames() -> bytes:
    # 32 previous x 32 target levels, two 4-bit symbols per byte, match the
    # V5 512-byte frame size and signed DT format-infos' 5/5-bit mapping.
    # This unpacking and symbol meaning define our synthetic stimulus only;
    # no claim is made that they reproduce a factory waveform encoding.
    frame = bytearray(FRAME_BYTES)
    for previous in range(32):
        for target in range(32):
            symbol = 0 if target == previous else (1 if target > previous else 2)
            index = previous * 32 + target
            frame[index // 2] |= symbol << (4 * (index & 1))
    # One directed frame followed by a neutral frame. A nonzero frame count
    # also keeps the kernel's length-minus-one register programming valid.
    return bytes(frame) + bytes(FRAME_BYTES)


def build_waveform(*, product: str = "cs8") -> bytes:
    """Return a bounded V5.0 WRF with all 32x48 table entries populated."""
    if product not in FILE_NAMES:
        raise ValueError(f"unsupported Scribe waveform product: {product}")
    data = bytearray(DATA_START + (TABLE_MODES - 1) * MODE_STRIDE + FRAMES * FRAME_BYTES)
    name = f"SYNTHETIC_{product.upper()}_V50_EMULATOR_ONLY".encode("ascii")
    data[:len(name)] = name
    data[0x50] = 0xFF  # WF_MODE_VERSION_TEST, explicit in hwtcon_core.h.
    data[0x53] = 0x02  # Synthetic 5-bit transition input (WAVEFORM_TYPE_5BIT).
    data[0x56] = 1     # Synthetic revision; not a factory WFM revision.
    data[0x80:0x80 + len(THRESHOLDS)] = THRESHOLDS
    data[0xA2] = TEMPERATURE_ZONES - 1
    data[0xA4] = 0x50
    data[0xA5] = 0x08

    # SV entries are 12 bytes in 16-byte slots. Signed voltage channels are
    # represented as positive magnitudes, exactly as fiti_core.c interprets.
    sv = struct.pack(
        ">6H", *map(_voltage_units, (24000, 24000, 12000, 12000, 6000, 6000)),
    )
    for temperature in range(TEMPERATURE_TABLE_ZONES):
        offset = 0xC0 + temperature * 0x10
        data[offset:offset + len(sv)] = sv
        for mode in range(TABLE_MODES):
            table_offset = 4 * (temperature * TABLE_MODES + mode)
            struct.pack_into(
                ">I", data, ADDRESS_TABLE + table_offset, DATA_START + mode * MODE_STRIDE,
            )
            struct.pack_into(
                ">I", data, LENGTH_TABLE + table_offset, FRAMES * FRAME_BYTES,
            )

    frames = _transition_frames()
    for mode in range(TABLE_MODES):
        address = DATA_START + mode * MODE_STRIDE
        data[address - 0x20:address] = _settings(mode in NIGHT_MODES)
        data[address:address + len(frames)] = frames
    return bytes(data)


def describe_waveform(data: bytes) -> dict[str, object]:
    """Validate loader-relevant bounds, FT9936 settings and frame table sizes."""
    if len(data) < LENGTH_TABLE + TEMPERATURE_TABLE_ZONES * TABLE_MODES * 4:
        raise ValueError("truncated V5 waveform tables")
    if data[0xA4] < 0x50 or data[0xA5] < 8:
        raise ValueError("unsupported V5 format or converter version")
    threshold_count = data[0xA2]
    if not 0 < threshold_count < TEMPERATURE_ZONES:
        raise ValueError("invalid temperature threshold count")
    thresholds = list(data[0x80:0x80 + threshold_count])
    if thresholds != sorted(set(thresholds)):
        raise ValueError("temperature thresholds must increase")
    for temperature in range(TEMPERATURE_TABLE_ZONES):
        sv = struct.unpack_from(">6H", data, 0xC0 + temperature * 0x10)
        for channel, raw in enumerate(sv):
            millivolts = raw * 25 // 2
            lower, upper = ((9000, 27500), (6000, 20000), (3500, 12000))[channel // 2]
            if not lower <= millivolts <= upper:
                raise ValueError("source voltage outside FT9936 range")
        for mode in range(TABLE_MODES):
            index = 4 * (temperature * TABLE_MODES + mode)
            address = struct.unpack_from(">I", data, ADDRESS_TABLE + index)[0]
            length = struct.unpack_from(">I", data, LENGTH_TABLE + index)[0]
            if address < 0x3360 or address % 16 or not length or length % FRAME_BYTES:
                raise ValueError("invalid waveform address or frame length")
            if address + length > len(data):
                raise ValueError("waveform extends outside file")
            if mode in (2, 8):
                version = struct.unpack_from(">H", data, address - 0x20)[0]
                allowed = (0x8001, 0x8004) if mode == 2 else (0x8003, 0x8005)
                if version not in allowed:
                    raise ValueError("invalid FT9936 day/night voltage prefix")
    return {
        "synthetic": True,
        "name": data[:0x40].split(b"\0", 1)[0].decode("ascii"),
        "format": "HWTCON V5.0",
        "converter_version": data[0xA5],
        "mode_version": data[0x50],
        "uncompressed_bytes": len(data),
        "temperature_zones": threshold_count + 1,
        "temperature_table_zones": TEMPERATURE_TABLE_ZONES,
        "thresholds_celsius": thresholds,
        "table_modes": TABLE_MODES,
        "kernel_modes": 32,
        "frames_per_mode": FRAMES,
        "frame_bytes": FRAME_BYTES,
        "layout": {
            "address_table": ADDRESS_TABLE,
            "length_table": LENGTH_TABLE,
            "table_byte_order": "big endian",
            "source_voltage_table": 0xC0,
            "source_voltage_stride": 0x10,
            "voltage_prefix_bytes_before_payload": 0x20,
            "first_payload": DATA_START,
        },
        "sources": [
            "linux/device_module/drivers/misc/mediatek/hwtcon/hal/hwtcon_wf_file.c",
            "linux/device_module/drivers/misc/mediatek/hwtcon/hwtcon_core.h",
            "linux/device_module/drivers/misc/mediatek/hwtcon/hwtcon_core.c",
            "linux/device_module/drivers/misc/mediatek/pmic/FT9936/fiti_core.h",
            "linux/device_module/drivers/misc/mediatek/pmic/FT9936/fiti_core.c",
        ],
        "payloads_shared_between_temperature_zones": True,
        "source_rail_magnitudes_mv": [24000, 24000, 12000, 12000, 6000, 6000],
        "gate_rail_magnitudes_mv": {"vgh": 35000, "vgl": 35000, "vghnm": 2000},
        "checksums": "Standard gzip CRC32 and ISIZE; no inner WRF checksum is consumed by CS8 kernel or boot selector.",
        "limitations": [
            "Synthetic emulator stimulus, not Amazon firmware or panel calibration.",
            "Transition symbol meanings, nibble order, thresholds and frame counts are synthetic choices.",
            "Voltage fields use driver defaults; they are not measured panel settings.",
            "No factory identity, signature, or OTA installation wrapper is asserted.",
        ],
    }


def write_waveform(directory: Path, *, product: str = "cs8") -> Path:
    """Write raw WRF, deterministic gzip and a human-readable provenance file."""
    directory.mkdir(parents=True, exist_ok=True)
    raw = build_waveform(product=product)
    description = describe_waveform(raw)
    description["product"] = product
    description["panel_input"] = "Y8 monochrome" if product == "pa6" else "RGBA8888 CFA"
    description["working_buffer_bits"] = 24
    description["product_selection_evidence"] = (
        "Identical signed mt8115-pa6-cs8 DT uses wf-file-type=3 (V5.0), "
        "format-infos=5/5 and wb-data-type=1 (24-bit). Stock U-Boot at "
        "offset 0x1752c sets color-format=1/cfa-panel=0 for PA6, "
        "or color-format=4/cfa-panel=1 for CS8."
    )
    target = directory / FILE_NAMES[product]
    compressed = io.BytesIO()
    with gzip.GzipFile(fileobj=compressed, mode="wb", filename="", mtime=0) as stream:
        stream.write(raw)
    blob = compressed.getvalue()
    # gzip.decompress checks CRC32/ISIZE as the driver's gzip reader requires.
    if gzip.decompress(blob) != raw:
        raise ValueError("gzip round trip failed")
    crc, size = struct.unpack_from("<II", blob, len(blob) - 8)
    if crc != zlib.crc32(raw) or size != len(raw):
        raise ValueError("invalid gzip trailer")
    target.with_suffix("").write_bytes(raw)
    target.write_bytes(blob)
    description["compressed_bytes"] = len(blob)
    (directory / "README.json").write_text(json.dumps(description, indent=2) + "\n")
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--product", choices=tuple(FILE_NAMES), default="cs8")
    args = parser.parse_args()
    print(write_waveform(args.directory, product=args.product))


if __name__ == "__main__":
    main()
