# E-ink emulator

This repository provides tools for creating and running persistent virtual
e-readers with the project's QEMU fork. Firmware stays outside Git, and
generated disks are stored as sparse QCOW2 images.

No firmware, device dumps, account data, or physical-device identity values
are distributed here. This project is not affiliated with Amazon or Rakuten
Kobo.

## Quick start

Clone with submodules and inspect the supported models:

```sh
git clone --recurse-submodules git@github.com:katadelos/eink-emulator.git
cd eink-emulator
./eink models
./eink firmware
```

Copy firmware from a device you own into the directory shown by
`./eink firmware`, then create an instance. Kindle models require their
identity fields at creation; the values are stored only in the ignored
instance manifest.

```sh
./eink create my-reader --model kindle-voyage \
  --idme serial='<value>' \
  --idme mac='<value>' \
  --idme mfg='<value>' \
  --idme pcbsn='<value>' \
  --idme bootmode='<value>' \
  --idme postmode='<value>'

./eink run my-reader
```

Kobo devices do not use identity fields:

```sh
./eink create my-kobo --model kobo-touch
./eink run my-kobo

./eink create my-mini --model kobo-mini
./eink run my-mini
```

When necessary, `create` builds QEMU and an immutable base image before adding
a small writable overlay for the instance.

## Everyday commands

```text
./eink models                 List supported models
./eink firmware               Show required firmware files
./eink import FILE --model M  Import a supported recovery package
./eink create NAME --model M  Create a persistent instance
./eink run NAME               Launch an instance
./eink qemu -- ARGS           Use a raw QEMU machine
./eink list                   List instances
./eink images                 List base and instance disks
./eink build                  Build the QEMU fork
```

Use `./eink run NAME --headless` for serial-only operation,
`--ssh-port PORT` to change the loopback SSH forwarding port, and
`--vnc ENDPOINT` to use QEMU's VNC display. Arguments after `--` are passed
directly to QEMU.

## Using a raw QEMU machine

The raw QEMU machines can be used directly for kernel and bootloader
development. Supply the machine properties, firmware, storage, and other QEMU
options for each run:

```sh
# Bootloader development
./eink qemu -- \
  -machine imx6sl-wario,idme-serial='<value>',idme-mac='<value>' \
  -m 512M \
  -bios path/to/u-boot.bin \
  -serial mon:stdio \
  -no-reboot

# Direct kernel boot
./eink qemu -- \
  -machine imx6sl-wario,idme-serial='<value>',idme-mac='<value>' \
  -m 512M \
  -kernel path/to/uImage \
  -append '<kernel command line>' \
  -serial mon:stdio \
  -no-reboot

# Eanab bootloader development
./eink qemu -- \
  -machine imx6sl-eanab,idme-serial='<value>',idme-mac='<value>' \
  -m 512M \
  -bios path/to/u-boot.bin \
  -serial mon:stdio \
  -no-reboot
```

All arguments after `--` are passed directly to QEMU. These runs are ephemeral:
`eink` does not read the model catalogue, create an instance, or attach a
generated disk.

## Taking a screenshot

Use QEMU's monitor to capture the emulated framebuffer directly. While a
machine is running, press `Ctrl-A C` to switch from its serial console to the
monitor, then write a PNG to an absolute host path:

```text
(qemu) screendump /tmp/eink-screen.png -f png
```

Press `Ctrl-A C` again to return to the serial console. `screendump` captures
guest pixels without window decorations, cursor state, display scaling, or
other desktop content.

## Supported models

| Full name | Abbreviation | Board name | Notes |
| --- | --- | --- | --- |
| Kindle 4 | K4 | Tequila | |
| Kindle Touch | K5 | Whitney | |
| Kindle Paperwhite 1 | PW1 | Celeste | |
| Kindle Paperwhite 2 | PW2 | Pinot | |
| Kindle Basic (2014) | KT2 | Bourbon | |
| Kindle Voyage | KV | Icewine | |
| Kindle Paperwhite 3 | PW3 | Muscat | |
| Kindle Basic 2 (2016) | KT3 | Eanab | 8th Generation |
| Kindle Paperwhite 4 | PW4 | Moonshine | |
| Kobo Mini | N705 | E50610 | |
| Kobo Touch | N905 | E60610 | |

Coloursoft machine support remains experimental and is not listed above.

Additional documentation covers [firmware setup](docs/firmware.md),
[guest compatibility changes](docs/guest-overrides.md), and
[storage layout](docs/storage.md).

## Host requirements

- Python 3.10 or newer
- a C compiler and the standard QEMU build dependencies
- Ninja
- `mke2fs`, `tune2fs`, and `debugfs` from e2fsprogs for Kindle image creation
- `kindletool` when importing supported Kindle recovery packages

On macOS, Homebrew's `e2fsprogs` package supplies the filesystem tools. QEMU's
SLIRP dependency is built from its pinned subproject when it is not installed
on the host.
