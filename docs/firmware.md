# Bring your own firmware

Firmware is never downloaded by this project and every file below
`firmware/` is ignored by Git. Only use material obtained from hardware or
software that you are entitled to use.

Run this command at any time for an authoritative checklist:

```sh
./eink firmware
```

## Directory layout

Each model has its own flat directory:

```text
firmware/
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
├── kobo-mini/
│   ├── u-boot.bin
│   └── sd.img
└── kobo-touch/
    ├── u-boot.bin
    └── sd.img
```

The models which list `panel-flash.bin` use it for panel data. Eanab instead
loads its waveform from the root filesystem. Bellatrix4 devices use a
standalone `waveform.img`, described below. The optional Wario waveform,
diagnostics kernel, and diagnostics partition files use the same names for
Kindle Basic (2014), Paperwhite 2, and Paperwhite 3 as shown for Voyage. Kobo
Touch does not use a panel-flash artifact.

Colorsoft and Paperwhite 6 follow the component-image flow used by the other
Kindles. Supply the matching Bellatrix4 boot components, `boot.img`, and
`rootfs.img`; the builder creates a sparse disk with the required GPT layout
and a fresh fscrypt-capable userstore. A complete device storage image is
neither required nor used.

`waveform.img` is the raw FAT image written to the Bellatrix4 `wfm` partition.
It is separate from the root filesystem. The examined Colorsoft and
Paperwhite 6 recovery payloads contain the boot components, `boot.img`, and
`rootfs.img.gz`, but no waveform payload; their root filesystems only contain
software which reads the mounted waveform partition at `/mnt/wfm`. Supply
matching waveform data obtained from hardware or software that you are
entitled to use. A donor waveform may be sufficient for bring-up but is not
exact panel data.

`rootfs.img` must be a raw ext filesystem image. If an extracted firmware
package contains `rootfs.img.gz`, decompress it before placing it here.

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

For both Kobo models, `u-boot.bin` is passed directly to QEMU as the BIOS and
`sd.img` is the complete internal-card image, including its raw boot area,
rootfs, recoveryfs, and userstore.

## Instance identity

Kindle identity data is not part of the firmware catalogue. Supply the fields
from the source device when creating an instance:

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
Colorsoft and Paperwhite 6 use the development identity defaults built into
their QEMU machine and therefore do not accept `--idme` fields.
Kindle Paperwhite 1, Kindle 4, and Kindle Touch additionally require `accel`
and `sec`. An empty value is accepted when that is what the source device
reports.

Identity values are stored in `machines/NAME/machine.json`, which is ignored
by Git. Do not publish machine directories.

Paperwhite 4 / Rex also requires either `--profile production` or `--profile
dvt` at instance creation. The profile is stored with the instance and passed
to QEMU on every launch.

Bellatrix4 instances also require a profile. Colorsoft accepts `production`,
`dvt`, `evt`, `hvt`, or `proto`; Paperwhite 6 additionally accepts `hvt1.1`.
The profile selects the stock board tattoo exposed to U-Boot, the kernel, and
userspace capability detection.
