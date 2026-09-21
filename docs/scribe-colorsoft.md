# Kindle Scribe Colorsoft

Experimental: Wi-Fi and USB Ethernet have carried traffic, but a usable Home
screen is not yet verified. Scribe Colorsoft uses `mt8115-pa6-cs8,board=calvados`
with four CPUs, 4 GiB RAM and an 8 GiB sparse disk.

## Setup

Install the [host requirements](../README.md#host-requirements), then run:

```sh
./eink import /path/to/update.bin --model kindle-scribe-colorsoft
./eink create my-scribe-colorsoft --model kindle-scribe-colorsoft --profile dvt
./eink run my-scribe-colorsoft
```

Use a `platcs8` recovery package. It shares the [firmware layout](firmware.md#scribe-recovery-packages)
and [development boot settings](guest-overrides.md#scribe-3-and-colorsoft)
with Scribe 3, using different touch firmware and a CS8 waveform.

See [hardware profiles](firmware.md#hardware-profiles) for board configurations
and [networking](networking.md) for SSH access. The display does not reproduce
physical panel colour or ghosting.
