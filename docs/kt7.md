# Kindle Basic 7 (2026)

Experimental support for KT7 uses the Prosecco MT8110 board, 1 GiB RAM
and an 8 GiB sparse disk. The model ID is `kindle-basic-2026`.

## Setup

Install the [host requirements](../README.md#host-requirements), then import
a Kindle update package for this model:

```sh
./eink import /path/to/update.bin --model kindle-basic-2026
./eink create my-kt7 --model kindle-basic-2026 --profile production
./eink run my-kt7
```

The importer uses KindleTool and expects the Bellatrix package layout:
`mt8110_bellatrix/{u-boot.bin,bl2.img,tee.img,quickboot.img,boot.img}` and
`rootfs.img.gz`. It installs conventional firmware files under
`firmware/kindle-basic-2026/`, decompresses the rootfs and extracts
`peripherals/tt_fw.bin` from it. The rootfs must identify
`com.lab126.eink.prosecco.os`.

KT7 update packages have not been released, so this expected package layout
has not been verified against a retail update.

The builder prepares a separate rootfs copy with local serial and SSH access.
It creates a GPT disk with the root filesystem at partition 8, fresh persistent
filesystems, cold-boot configuration in `miscdata` and a synthetic waveform.
Imported firmware remains unchanged.
See [networking](networking.md) for the usual Kindle SSH connection.

## Partition dump utility

The supplied partition dump is handled separately from `eink import`:

```sh
python3 scripts/carve-kt7.py /path/to/kt7.tar.gz --boot-image /path/to/p1.img
```

The utility carves the supplied dump's `boot0.img` and `boot1.img`, copies
`p8.img` as the rootfs, and extracts the signed FIT from the separate kernel
partition. It also extracts the touch firmware. The kernel, device tree and
FIT signatures remain unchanged; partition padding is excluded.
Device identity, keys and persistent partitions are not imported.

The default output is `firmware/kindle-basic-2026/`; use `--output` for another
directory. The utility refuses to overwrite an existing output directory.

QEMU supplies synthetic Prosecco IDME defaults through the shared MediaTek
Kindle implementation. The captured device's IDME and user data are not loaded
into the emulator. [Identity overrides](firmware.md#qemu-device-identity)
apply to individual runs.

## Hardware profiles

Select a profile when creating an instance:

```sh
./eink create my-kt7-hvt --model kindle-basic-2026 --profile hvt
```

The supplied po8 U-Boot defines four hardware phases. GPIO113 is the least
significant hardware ID bit, followed by GPIO112 and GPIO114.

| Profile | U-Boot phase | Hardware ID |
| --- | --- | --- |
| `production`, `dvt` | DVT | 3 |
| `evt` | EVT | 2 |
| `hvt` | HVT | 1 |
| `proto` | Proto | 0 |

These profiles share the Prosecco panel and peripherals described by the
supplied po8 device tree. The synthetic PSN revision remains independent of
the hardware ID. The image provides no additional named Prosecco phases.
