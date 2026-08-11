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

Kobo Touch does not use identity fields:

```sh
./eink create my-kobo --model kobo-touch
./eink run my-kobo
```

When necessary, `create` builds QEMU and an immutable base image before adding
a small writable overlay for the instance.

## Everyday commands

```text
./eink models                 List supported models
./eink firmware               Show required firmware files
./eink create NAME --model M  Create a persistent instance
./eink run NAME               Launch an instance
./eink list                   List instances
./eink images                 List base and instance disks
./eink build                  Build the QEMU fork
```

Use `./eink run NAME --headless` for serial-only operation,
`--ssh-port PORT` to change the loopback SSH forwarding port, and
`--vnc ENDPOINT` to use QEMU's VNC display. Arguments after `--` are passed
directly to QEMU.

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
| Kindle Basic (2016) | KT3 | Eanab | |
| Kindle Paperwhite 4 | PW4 | Moonshine | |
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

On macOS, Homebrew's `e2fsprogs` package supplies the filesystem tools. QEMU's
SLIRP dependency is built from its pinned subproject when it is not installed
on the host.
