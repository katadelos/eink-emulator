#!/usr/bin/env python3
"""Extract unchanged kernel, ramdisk and device-tree payloads for kexec."""
import argparse
import gzip
import struct
from pathlib import Path


def fdt_nodes(data):
    header = struct.unpack_from(">10I", data)
    if header[0] != 0xD00DFEED or header[1] > len(data):
        raise ValueError("Invalid device tree")
    pos, strings, end = header[2], header[3], header[2] + header[9]
    stack, nodes = [], {}
    while pos < end:
        token = struct.unpack_from(">I", data, pos)[0]
        pos += 4
        if token == 1:
            stop = data.index(b"\0", pos, end)
            stack.append(data[pos:stop].decode())
            nodes["/".join(stack)] = {}
            pos = (stop + 4) & ~3
        elif token == 2:
            stack.pop()
        elif token == 3:
            length, name = struct.unpack_from(">2I", data, pos)
            pos += 8
            name += strings
            key = data[name:data.index(b"\0", name)].decode()
            nodes["/".join(stack)][key] = data[pos:pos + length]
            pos = (pos + length + 3) & ~3
        elif token == 9:
            return nodes
        elif token != 4:
            raise ValueError("Invalid device-tree token")
    raise ValueError("Unterminated device tree")


def extract(data):
    if data.startswith(b"ANDROID!"):
        kernel, _, ramdisk, _, second, _, _, page = struct.unpack_from("<8I", data, 8)
        if page < 512 or page & (page - 1):
            raise ValueError("Invalid Android boot page size")
        pos = page
        result = {}
        for name, size in (("kernel", kernel), ("initrd", ramdisk), ("second", second)):
            if pos + size > len(data):
                raise ValueError("Truncated Android boot image")
            if size:
                result[name] = data[pos:pos + size]
            pos += (size + page - 1) & -page
        return result
    if data.startswith(b"\xd0\x0d\xfe\xed"):
        nodes = fdt_nodes(data)
        if "/images" in nodes:
            default = nodes["/configurations"]["default"].rstrip(b"\0").decode()
            config = nodes["/configurations/" + default]
            result = {}
            for prop, name in (("kernel", "kernel"), ("ramdisk", "initrd"), ("fdt", "dtb")):
                if prop not in config:
                    continue
                image = nodes["/images/" + config[prop].rstrip(b"\0").decode()]
                payload = image["data"]
                compression = image.get("compression", b"none\0").rstrip(b"\0")
                if compression == b"gzip":
                    payload = gzip.decompress(payload)
                elif compression != b"none":
                    raise ValueError(f"Unsupported FIT compression: {compression!r}")
                result[name] = payload
            return result
        # Lab126 Eanab packages place a DTB before a legacy uImage.
        end = struct.unpack_from(">I", data, 4)[0]
        offset = data.find(b"\x27\x05\x19\x56", end)
        if offset < 0:
            raise ValueError("Device tree has no embedded kernel")
        result = extract(data[offset:])
        result["dtb"] = data[:end]
        return result
    if data.startswith(b"\x27\x05\x19\x56"):
        size = struct.unpack_from(">I", data, 12)[0]
        if len(data) < 64 + size:
            raise ValueError("Truncated uImage")
        payload = data[64:64 + size]
        if data[31] == 1:
            payload = gzip.decompress(payload)
        elif data[31] != 0:
            raise ValueError("Unsupported uImage compression")
        return {"kernel": payload}
    raise ValueError("Expected a Lab126 uImage, Android boot image, or FIT")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = extract(args.image.read_bytes())
    args.output.mkdir(parents=True, exist_ok=True)
    for name, data in result.items():
        path = args.output / name
        path.write_bytes(data)
        print(f"{path}: {len(data)} bytes")


if __name__ == "__main__":
    main()
