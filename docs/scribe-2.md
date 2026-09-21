# Kindle Scribe 2

Experimental: Home, touch and suspend are not yet verified with the standard
images. Scribe 2 uses `mt8113-bellatrix3,board=pisco` with 1 GiB RAM and an
8 GiB sparse disk.

## Setup

Install the [host requirements](../README.md#host-requirements), then run:

```sh
./eink import /path/to/update.bin --model kindle-scribe-2
./eink create my-scribe-2 --model kindle-scribe-2 --profile dvt
./eink run my-scribe-2
```

Both `production` and `dvt` select DVT hardware. The image uses the original
kernel and device tree. SBIOS storage requests can time out if the host delays
execution.

First boot skips initial setup and selects British English. Guest startup
and storage are shared with [Scribe 1](scribe-1.md#guest-behavior).
See [networking](networking.md) for SSH and Wi-Fi access.
