# Kindle Scribe 3

Paloma uses `mt8115-pa6-cs8,board=paloma` with four CPUs and 4 GiB RAM.
It shares the MT8115 platform with [Scribe Colorsoft](scribe-colorsoft.md).
Import and image creation work; the standard boot path has not yet been
verified through to a usable Home screen. Wi-Fi and USB Ethernet both carry traffic; see [networking](networking.md).

## Setup

Install KindleTool and e2fsprogs, then import a recovery package:

```sh
./eink import /path/to/update.bin --model kindle-scribe-3
./eink create my-scribe-3 --model kindle-scribe-3 --profile dvt
./eink run my-scribe-3
```

Profiles are `production` (DVT), `dvt`, `evt` and `hvt1.1`. QEMU supplies
the board identity.

Serial opens in the launching terminal. Use `--serial-socket` to redirect
it to the instance's Unix socket and log file.

## Firmware and disk image

The firmware platform is `platpa6`. Import saves six boot images
under `firmware/kindle-scribe-3/boot_images`, with `rootfs.img`
in the model directory. It also extracts these files into `peripherals/`:

- `focaltech_ts_fw_bw5c.bin` — FocalTech touch firmware
- `soc2_2_ram_mcu_mt8171_mt6631_1_hdr.bin` — connectivity firmware

The builder creates an 8 GiB sparse development disk with fresh user storage.
It prepares copies of the rootfs and boot FIT: USB Ethernet starts automatically,
root serial login is available, and verity is disabled for the prepared rootfs.
The catalogue enables QEMU development mode, which removes the production-key
requirement from the in-memory U-Boot handoff. Imported firmware stays unchanged.
See the [partition layout](storage.md#scribe-partitions).

The builder generates a synthetic PA6 V5 waveform for display emulation. It does not reproduce physical panel calibration.
