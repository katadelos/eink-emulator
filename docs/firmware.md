# Firmware

Supply firmware from hardware or recovery packages you are entitled to use.
The emulator does not download firmware, and Git ignores imported files.

List the required files for each model:

```sh
./eink firmware
```

## Directory layout

Each model has a directory under `firmware/`. Older models keep their files
directly in that directory; Scribe 3 and Scribe Colorsoft also use
`boot_images/` and `peripherals/` subdirectories. The older layouts are shown
below; see [Scribe recovery packages](#scribe-recovery-packages) for the Scribes.

```text
firmware/
├── kindle-basic-2022/
│   ├── u-boot.bin
│   ├── bl2.img
│   ├── tee.img
│   ├── quickboot.img
│   ├── boot.img
│   ├── rootfs.img
│   └── waveform.img  (optional)
├── kindle-basic-2024/
│   ├── u-boot.bin
│   ├── bl2.img
│   ├── tee.img
│   ├── quickboot.img
│   ├── boot.img
│   ├── rootfs.img
│   └── waveform.img  (optional)
├── kindle-colorsoft/
│   ├── u-boot.bin
│   ├── bl2.img
│   ├── tee.img
│   ├── quickboot.img
│   ├── boot.img
│   ├── rootfs.img
│   └── waveform.img
├── kindle-paperwhite-6/
│   ├── u-boot.bin
│   ├── bl2.img
│   ├── tee.img
│   ├── quickboot.img
│   ├── boot.img
│   ├── rootfs.img
│   └── waveform.img
├── kindle-voyage/
│   ├── u-boot.bin
│   ├── uImage
│   ├── rootfs.img
│   ├── panel-flash.bin
│   ├── diags-uImage        (optional)
│   ├── diags.img           (optional)
│   └── waveform-store.img  (optional)
├── kindle-basic-2014/
│   ├── u-boot.bin
│   ├── uImage
│   ├── rootfs.img
│   ├── panel-flash.bin
│   ├── diags-uImage        (optional)
│   └── diags.img           (optional)
├── kindle-basic-2016/
│   ├── u-boot.bin
│   ├── uImage
│   └── rootfs.img
├── kindle-paperwhite-1/
│   ├── u-boot.bin
│   ├── uImage
│   ├── rootfs.img
│   └── panel-flash.bin
├── kindle-paperwhite-2/
│   ├── u-boot.bin
│   ├── uImage
│   ├── rootfs.img
│   ├── panel-flash.bin
│   ├── diags-uImage        (optional)
│   └── diags.img           (optional)
├── kindle-paperwhite-3/
│   ├── u-boot.bin
│   ├── uImage
│   ├── rootfs.img
│   ├── panel-flash.bin
│   ├── diags-uImage        (optional)
│   └── diags.img           (optional)
├── kindle-paperwhite-4/
│   ├── u-boot.bin
│   ├── boot.img
│   ├── rootfs.img
│   ├── s-bios.bin
│   ├── bios.bin
│   ├── panel-flash.bin
│   └── waveform.img
├── kindle-4/
│   ├── u-boot.bin
│   ├── uImage
│   ├── rootfs.img
│   └── panel-flash.bin
├── kindle-touch/
│   ├── u-boot.bin
│   ├── uImage
│   ├── rootfs.img
│   └── panel-flash.bin
├── kobo-forma/
│   ├── u-boot.imx
│   ├── boot-region.img
│   ├── rootfs.img
│   └── recoveryfs.img
├── kobo-mini/
│   ├── u-boot.bin
│   └── sd.img
└── kobo-touch/
    ├── u-boot.bin
    └── sd.img
```

The models which list `panel-flash.bin` use it for panel data. Eanab instead
loads its waveform from the root filesystem. Bellatrix devices use a
standalone `waveform.img`, described below. The optional Wario waveform,
diagnostics kernel, and diagnostics partition files use the same names for
Kindle Basic (2014), Paperwhite 2, and Paperwhite 3 as shown for Voyage. Kobo
Touch does not use a panel-flash artifact.

For Kobo Mini and Kobo Touch, `u-boot.bin` is passed directly to QEMU as
the BIOS and `sd.img` is the complete internal-card image, including its
raw boot area, rootfs, recoveryfs, and userstore.

[Kobo Forma](kobo-forma.md) uses its live boot-region and partition dumps
with the U-Boot image from a Forma firmware update. Its builder preserves
the boot offsets and creates a fresh userstore within a 2 GiB eMMC image.

[Kobo Elipsa 2E](kobo-elipsa-2e.md) combines its partition dumps with the
compiled U-Boot, kernel and TEE from a mark 11 update. Its 2 GiB GPT disk
retains the original system partition offsets and has a fresh FAT32 userstore.
See the model page for the complete firmware file list.

Kindle Basic 5, Kindle Basic 6, Colorsoft, and Paperwhite 6 follow the
component-image flow used by the other Kindles. Supply the matching Bellatrix
boot components, `boot.img`, and `rootfs.img`; the builder creates a sparse
disk with the required GPT layout and a board-appropriate fresh userstore. A
complete device storage image is neither required nor used.

`waveform.img` is the raw FAT image written to the Bellatrix `wfm` partition.
It is separate from the root filesystem. The examined Colorsoft and
Paperwhite 6 recovery payloads contain the boot components, `boot.img`, and
`rootfs.img.gz`, but no waveform payload; their root filesystems only contain
software which reads the mounted waveform partition at `/mnt/wfm`. Supply
matching waveform data obtained from hardware or software that you are
entitled to use. A donor waveform may be sufficient for bring-up but is not
exact panel data.

`rootfs.img` must be a raw ext filesystem image. If an extracted firmware
package contains `rootfs.img.gz`, decompress it before placing it here.

## Scribe recovery packages

All four Scribes can import a recovery package. Install KindleTool and
e2fsprogs, then select the matching model:

```sh
./eink import /path/to/update.bin --model kindle-scribe-1
```

| Device | Model ID | Firmware layout |
| --- | --- | --- |
| [Scribe 1](scribe-1.md) | `kindle-scribe-1` | Boot files and rootfs in the model directory |
| [Scribe 2](scribe-2.md) | `kindle-scribe-2` | Boot files and rootfs in the model directory |
| [Scribe 3](scribe-3.md) | `kindle-scribe-3` | Boot files in `boot_images/`, extracted firmware in `peripherals/` |
| [Scribe Colorsoft](scribe-colorsoft.md) | `kindle-scribe-colorsoft` | Boot files in `boot_images/`, extracted firmware in `peripherals/` |

The importer decompresses `rootfs.img.gz` and refuses to overwrite an
existing firmware directory. Scribe 3 and Colorsoft also extract touch and
connectivity firmware from the rootfs. Their rootfs images keep the AVB
footer used for verified boot.

Place an optional `waveform.img` in the model directory to use a device
waveform partition. Without one, Scribe image creation generates a synthetic
waveform for display emulation. This does not reproduce panel calibration.

## Kindle Basic (2016) recovery package

The Eanab firmware is distributed as a Heisenberg recovery package. Import it
directly with KindleTool installed:

```sh
./eink import path/to/update_kindle_8th.bin --model kindle-basic-2016
```

The importer runs `kindletool extract`, validates the Heisenberg artifact
layout, decompresses `rootfs.img.gz`, and installs `u-boot.bin`, `uImage`, and
`rootfs.img` under `firmware/kindle-basic-2016/`. It refuses to overwrite an
existing firmware directory.

## Kindle Oasis recovery packages

Download the matching Oasis update from
[Amazon](https://www.amazon.com/gp/help/customer/display.html?nodeId=GKMQC26VQQMM8XSW),
then import it with KindleTool installed:

```sh
./eink import /path/to/update_kindle_oasis_5.16.2.1.1.bin --model kindle-oasis-1
./eink import /path/to/update_kindle_all_new_oasis_5.16.2.1.1.bin --model kindle-oasis-2
```

See [Oasis setup](oasis.md) to create and run your emulator.

## Instance identity

Older Kindle models require identity fields from the source device when
creating an instance:

```sh
./eink create NAME --model MODEL \
  --idme serial='<value>' \
  --idme mac='<value>' \
  --idme mfg='<value>' \
  --idme pcbsn='<value>' \
  --idme bootmode='<value>' \
  --idme postmode='<value>'
```

The exact required set is validated before any image is built. Kobo Touch
rejects identity fields because that platform does not use them.

The same six identity fields shown above apply to Kindle Basic (2016).
Bellatrix models, Oasis 1 and 2, and all four Scribes do not require
`--idme` fields.
Kindle Paperwhite 1, Kindle 4, and Kindle Touch additionally require `accel`
and `sec`. An empty value is accepted when that is what the source device
reports.

Identity values are stored in `machines/NAME/machine.json`, which is ignored
by Git. Do not publish machine directories.

Paperwhite 4 / Rex also requires either `--profile production` or `--profile
dvt` at instance creation. The profile is stored with the instance and passed
to QEMU on every launch.

Bellatrix instances also require a profile. Kindle Basic 5, Kindle Basic 6,
and Colorsoft accept `production`, `dvt`, `evt`, `hvt`, or `proto`;
Paperwhite 6 additionally accepts `hvt1.1`. The profile selects the stock
board tattoo exposed to U-Boot, the kernel, and userspace capability detection.

Scribes also require `--profile`:

| Device | Profiles |
| --- | --- |
| Scribe 1 | `production`, `dvt`, `evt`, `evt-doe`, `hvt`, `hvt-a`, `proto` |
| Scribe 2 | `production`, `dvt` |
| Scribe 3, Scribe Colorsoft | `production`, `dvt`, `evt`, `hvt1.1` |

For the Scribes, `production` selects the DVT configuration. Profile selection
is saved in the instance and passed to QEMU on each launch.
