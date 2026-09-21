# Kindle Scribe 1

Experimental: Home, touch and suspend are not yet verified with the standard
images. Scribe 1 uses `mt8113-bellatrix3,board=barolo` with 1 GiB RAM and an
8 GiB sparse disk.

## Setup

Install the [host requirements](../README.md#host-requirements), then run:

```sh
./eink import /path/to/update.bin --model kindle-scribe-1
./eink create my-scribe --model kindle-scribe-1 --profile dvt
./eink run my-scribe
```

The image uses the original kernel and device tree. SBIOS storage requests
can time out if the host delays execution. See [hardware profiles](firmware.md#hardware-profiles)
for other board configurations.

## Guest behavior

First boot skips initial setup and selects British English. The guest has a
serial shell, USB Ethernet and SSH. Wi-Fi connects to `Kindle-QEMU`; see
[networking](networking.md) for access commands.

Scribe 1 and 2 share [guest startup changes](../guest-overrides/bellatrix3/README.md)
and the [partition layout](storage.md#scribe-partitions).
