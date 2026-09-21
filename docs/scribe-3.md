# Kindle Scribe 3

Experimental: Wi-Fi and USB Ethernet have carried traffic, but a usable Home
screen is not yet verified. Scribe 3 uses `mt8115-pa6-cs8,board=paloma` with
four CPUs, 4 GiB RAM and an 8 GiB sparse disk.

## Setup

Install the [host requirements](../README.md#host-requirements), then run:

```sh
./eink import /path/to/update.bin --model kindle-scribe-3
./eink create my-scribe-3 --model kindle-scribe-3 --profile dvt
./eink run my-scribe-3
```

Use a `platpa6` recovery package. The importer extracts boot and peripheral
firmware into the [Scribe directory layout](firmware.md#scribe-recovery-packages).
Other [hardware profiles](firmware.md#hardware-profiles) are available.

The image uses development boot settings with verity disabled to allow guest
changes. See [image preparation](guest-overrides.md#scribe-3-and-colorsoft)
for details and [networking](networking.md) for SSH access.
