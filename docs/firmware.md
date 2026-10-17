# Firmware

Supply firmware from your device or a recovery package for your model.
`./eink firmware` lists the required paths and checks which files are present.
Firmware is not distributed with the repository; imported files are ignored
by Git.

## Import a recovery package

With the [host requirements](../README.md#host-requirements) installed, run:

```sh
./eink import /path/to/update.bin --model kindle-scribe-1
```

The importer extracts the package, decompresses the rootfs and installs the
files under `firmware/MODEL/`. It refuses to overwrite an existing model
directory. Use a package for the selected device.

Import is available for these models:

| Device | Model ID |
| --- | --- |
| Basic 2016 | `kindle-basic-2016` |
| Basic 2022 | `kindle-basic-2022` |
| Basic 2024 | `kindle-basic-2024` |
| [Basic 2026](kt7.md) | `kindle-basic-2026` |
| [Oasis 1 and 2](oasis.md) | `kindle-oasis-1`, `kindle-oasis-2` |
| [Oasis 3](koa3.md) | `kindle-oasis-3` |
| [Basic 4 (2019)](kt4.md) | `kindle-kt4` |
| [Paperwhite 5](paperwhite-5.md) | `kindle-paperwhite-5` |
| [Scribe 1](scribe-1.md) | `kindle-scribe-1` |
| [Scribe 2](scribe-2.md) | `kindle-scribe-2` |
| [Scribe 3](scribe-3.md) | `kindle-scribe-3` |
| [Scribe Colorsoft](scribe-colorsoft.md) | `kindle-scribe-colorsoft` |
| [PocketBook 360 Plus New](pocketbook-512.md) | `pocketbook-512` |
| [PocketBook Basic 611](pocketbook-611.md) | `pocketbook-611` |
| [PocketBook Basic 613](pocketbook-613.md) | `pocketbook-613` |
| [PocketBook Touch 622](pocketbook-622.md) | `pocketbook-622` |
| [PocketBook Touch Lux 623](pocketbook-623.md) | `pocketbook-623` |
| [PocketBook Ultra 650](pocketbook-650.md) | `pocketbook-650` |
| [PocketBook Basic Lux 4](pocketbook-618.md) | `pocketbook-618` |
| [PocketBook Verse Lite](pocketbook-619.md) | `pocketbook-619` |
| [PocketBook Touch Lux 4](pocketbook-627.md) | `pocketbook-627` |
| [PocketBook Touch Lux 5](pocketbook-628.md) | `pocketbook-628` |
| [PocketBook Verse](pocketbook-629.md) | `pocketbook-629` |
| [PocketBook Touch HD 3](pocketbook-632.md) | `pocketbook-632` |
| [PocketBook Color](pocketbook-633.md) | `pocketbook-633` |
| [PocketBook Verse Pro](pocketbook-634.md) | `pocketbook-634` |
| [PocketBook Verse Pro Color](pocketbook-634k3.md) | `pocketbook-634k3` |
| [PocketBook Era](pocketbook-700.md) | `pocketbook-700` |
| [PocketBook Era Color](pocketbook-700k3.md) | `pocketbook-700k3` |
| [PocketBook InkPad 3](pocketbook-740.md) | `pocketbook-740` |
| [PocketBook InkPad 3 Pro](pocketbook-740-2.md) | `pocketbook-740-2` |
| [PocketBook InkPad Color](pocketbook-741.md) | `pocketbook-741` |
| [PocketBook InkPad Color 3](pocketbook-743k3.md) | `pocketbook-743k3` |
| [PocketBook InkPad Lite](pocketbook-970.md) | `pocketbook-970` |
| [PocketBook InkPad X](pocketbook-1040.md) | `pocketbook-1040` |
| [PocketBook Color Lux 801](pocketbook-801.md) | `pocketbook-801` |
| [reMarkable 1](remarkable-1.md) | `remarkable-1` |
| [reMarkable 2](remarkable-2.md) | `remarkable-2` |
| [reMarkable Paper Pro](remarkable-paper-pro.md) | `remarkable-paper-pro` |

[Tolino Vision Color](tolino-vision-color.md) and
[Shine 5 / Shine Color](tolino-shine.md) accept an update tar archive
or an extracted update directory through the same `import` command. Their
zstd-compressed components require `zstd` on the host; KindleTool is not used.

[PocketBook 360 Plus New](pocketbook-512.md),
[Basic 611](pocketbook-611.md), [Basic 613](pocketbook-613.md),
[Touch 622](pocketbook-622.md),
[Touch Lux 623](pocketbook-623.md), [Ultra 650](pocketbook-650.md),
[Touch Lux 5](pocketbook-628.md), [Touch HD 3](pocketbook-632.md),
[InkPad 3](pocketbook-740.md), [InkPad 3 Pro](pocketbook-740-2.md),
[InkPad X](pocketbook-1040.md) and
[Color Lux 801](pocketbook-801.md) accept their
official update ZIP or the extracted `SWUPDATE.BIN`. The importer checks the
selected PocketBook model and extracts the original bootloader, kernel, root
and application filesystems.

[reMarkable 1](remarkable-1.md) and [reMarkable 2](remarkable-2.md) accept
their official `.swu` update packages.
The importer extracts the root filesystem and its bundled vendor U-Boot;
the kernel and device tree remain in `/boot` inside the root filesystem.

[reMarkable Paper Pro](remarkable-paper-pro.md) accepts its official
Ferrari `.swu` package. Its boot stages come from the separate `imx-boot`
member; the importer also extracts the hardware-monitor firmware and
creates synthetic factory provisioning.

[Kindle Basic 7 (2026)](kt7.md) uses the standard update-package importer.
Its update packages have not been released; the expected Bellatrix package
layout remains unverified. The supplied partition dump uses the separate
[`scripts/carve-kt7.py`](../scripts/carve-kt7.py) utility, with its matching
kernel partition supplied through `--boot-image`. Touch firmware is extracted
from the rootfs into `peripherals/tt_fw.bin` by either workflow.

## Directory layout

For manual setup, place files under `firmware/MODEL/`:

| Models | Required files |
| --- | --- |
| Kindle 4, Touch, Paperwhite 1–3, Basic 2014/2016, Voyage | `u-boot.bin`, `uImage`, `rootfs.img` |
| Oasis 1 | The files above, plus `s-bios.bin` and `bios.bin` |
| Paperwhite 4, KT4, Oasis 2/3 | `u-boot.bin`, `boot.img`, `rootfs.img`, `s-bios.bin`, `bios.bin` |
| Basic 2022/2024, Paperwhite 5/6, Colorsoft, Scribe 1/2 | `u-boot.bin`, `bl2.img`, `tee.img`, `quickboot.img`, `boot.img`, `rootfs.img` |
| Basic 2026 | `u-boot.bin`, `bl2.img`, `tee.img`, `quickboot.img`, `boot.img`, `rootfs.img`, `peripherals/tt_fw.bin` |
| Kobo Mini, Touch | `u-boot.bin`, `sd.img` |
| Kobo Glo | See the [Glo file list](kobo-glo.md#firmware) |
| Kobo Aura HD | See the [Aura HD file list](kobo-aura-hd.md#firmware) |
| Kobo Glo HD | See the [Glo HD file list](kobo-glo-hd.md#firmware) |
| Kobo Clara HD | See the [Clara HD file list](kobo-clara-hd.md#firmware) |
| Kobo Forma | See the [Forma file list](kobo-forma.md#firmware) |
| Kobo Elipsa 2E | See the [Elipsa 2E file list](kobo-elipsa-2e.md#firmware) |
| PocketBook B288 models | `u-boot.img`, `uImage`, `rootfs.img`, `applications.img`, `updatefs` |
| reMarkable 1 | `u-boot.imx`, `rootfs.img`; see [import instructions](remarkable-1.md#firmware) |
| reMarkable 2 | `u-boot.imx`, `rootfs.img`; see [import instructions](remarkable-2.md#firmware) |
| reMarkable Paper Pro | `imx-boot`, `rootfs.img`, `hwmon.bin`, `factory.img`; see [import instructions](remarkable-paper-pro.md#firmware) |
| Tolino Vision Color | `uboot.img`, `kernel.img`, `rootfs.img`, `bl2.img`, `tee.img`; see [import instructions](tolino-vision-color.md#firmware) |
| Tolino Shine 5, Shine Color, Shine 5 TPV | `uboot.img`, `kernel.img`, `rootfs.img`, `bl2.img`, `tee.img`; see [kernel selection](tolino-shine.md#firmware) |

Basic 2014, Paperwhite 2/3 and Voyage also accept optional `diags-uImage` and
`diags.img` files.

`rootfs.img` must be a raw ext filesystem image. Decompress `rootfs.img.gz`
if you prepare the files manually. Kindle builders assemble a disk from
component images. Kobo Mini and Touch instead need a complete internal-card
image, `sd.img`, with the boot area and all partitions.

### Scribe recovery packages

Scribe 1/2 store boot files and rootfs in the model directory. Scribe 3 and
Scribe Colorsoft use this layout:

```text
firmware/MODEL/
├── rootfs.img
├── boot_images/
│   ├── u-boot.bin
│   ├── bl2.img
│   ├── tee.img
│   ├── quickboot.img
│   ├── boot.img
│   └── firmware.img
└── peripherals/
    ├── focaltech_ts_fw_bw5c.bin   # Scribe 3
    └── soc2_2_ram_mcu_mt8171_mt6631_1_hdr.bin
```

Scribe Colorsoft uses `focaltech_ts_fw_cp5d.bin` in place of the `bw5c` file.
The importer extracts both peripheral files from the rootfs.

## Display data

Waveforms and panel flash come from firmware or are generated by the emulator.
Do not supply separate files. Synthetic waveforms support display updates;
they do not reproduce physical panel response.

## QEMU device identity

Kindle machines provide synthetic IDME defaults. To override a value for one
run, pass QEMU options after `--`:

```sh
./eink run NAME --qmp-socket -- -idme-serial '<value>' -idme-mac '<value>'
```

Keep a launcher option, such as `--qmp-socket`, between `NAME` and `--`.
The current parser otherwise discards the separator and rejects the QEMU flags.

Supported `-idme-*` flags depend on the QEMU machine. Overrides apply to that
run and do not change the saved disk.

## Hardware profiles

The following models require `--profile` when you create an instance. The
profile selects the board identity used by U-Boot, Linux and guest services.
It is saved in the instance configuration and applied on each run.

| Models | Profiles |
| --- | --- |
| Paperwhite 4 | `production`, `dvt` |
| Paperwhite 5 | `production` |
| Basic 2026 | `production`, `dvt`, `evt`, `hvt`, `proto` |
| Basic 2022/2024, Colorsoft | `production`, `dvt`, `evt`, `hvt`, `proto` |
| Paperwhite 6 | `production`, `dvt`, `evt`, `hvt1.1`, `hvt`, `proto` |
| Scribe 1 | `production`, `dvt`, `evt`, `evt-doe`, `hvt`, `hvt-a`, `proto` |
| Scribe 2 | `production`, `dvt` |
| Scribe 3, Scribe Colorsoft | `production`, `dvt`, `evt`, `hvt1.1` |

On Basic 2026 and Scribes, `production` selects DVT hardware. Scribe 1's `proto` selects Proto2.
`./eink models` also lists the profiles from [`models.json`](../models.json).
