# E-ink emulator

This repository provides a small release-oriented interface for creating and
running persistent virtual e-readers. It builds the project QEMU fork, keeps
firmware supplied by the user outside Git, and stores every generated disk as
a sparse QCOW2 image.

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
`./eink firmware`. Then create an instance. Kindle models require every
identity field to be supplied at creation; values are written only to the
ignored instance manifest.

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

The first `create` builds QEMU when necessary, creates a cached immutable base,
and adds a small writable overlay for the instance.

## Everyday commands

```text
./eink models                 List supported hardware
./eink firmware               Check bring-your-own firmware
./eink create NAME --model M  Create a persistent instance
./eink run NAME               Launch an instance
./eink list                   Inventory instances
./eink images                 Inventory all base and instance disks
./eink build                  Build QEMU explicitly
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

Coloursoft is not included because its machine support is still experimental.

See [firmware setup](docs/firmware.md), [guest compatibility changes](docs/guest-overrides.md),
and [storage layout](docs/storage.md) for the workflows users normally need.

## Host requirements

- Python 3.10 or newer
- a C compiler and the normal QEMU build dependencies
- Ninja
- `mke2fs`, `tune2fs`, and `debugfs` from e2fsprogs for Kindle image creation

On macOS, Homebrew's `e2fsprogs` package supplies the filesystem tools. QEMU's
SLIRP dependency is built from its pinned subproject when it is not installed
on the host.
