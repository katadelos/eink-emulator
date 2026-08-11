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
│   ├── rootfs.img
│   └── panel-flash.bin
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
└── kobo-touch/
    ├── u-boot.bin
    └── sd.img
```

Every Kindle model requires `panel-flash.bin`; it provides the panel data needed
for graphical output. The optional Wario waveform, diagnostics kernel, and
diagnostics partition files use the same names for Kindle Basic (2014),
Paperwhite 2, and Paperwhite 3 as shown for Voyage. Kobo Touch does not use a
panel-flash artifact.

`rootfs.img` must be a raw ext filesystem image. If an extracted firmware
package contains `rootfs.img.gz`, decompress it before placing it here.

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
Kindle Paperwhite 1, Kindle 4, and Kindle Touch additionally require `accel`
and `sec`. An empty value is accepted when that is what the source device
reports.

Identity values are stored in `machines/NAME/machine.json`, which is ignored
by Git. Do not publish machine directories.

Paperwhite 4 / Rex also requires either `--profile production` or `--profile
dvt` at instance creation. The profile is stored with the instance and passed
to QEMU on every launch.
