# Kindle Scribe Colorsoft

Calvados uses `mt8115-pa6-cs8,board=calvados` with four CPUs and 4 GiB RAM.
It shares the MT8115 platform with [Scribe 3](scribe-3.md), with a colour
display and different touch firmware. Import and image creation work;
the standard boot path has not yet been verified through to a usable Home
screen. Wi-Fi and USB Ethernet both carry traffic; see [networking](networking.md).

## Setup

Install KindleTool and e2fsprogs, then import a recovery package:

```sh
./eink import /path/to/update.bin --model kindle-scribe-colorsoft
./eink create my-scribe-colorsoft --model kindle-scribe-colorsoft --profile dvt
./eink run my-scribe-colorsoft
```

Profiles are `production` (DVT), `dvt`, `evt` and `hvt1.1`. QEMU supplies
the board identity.

Serial opens in the launching terminal. Use `--serial-socket` to redirect
it to the instance's Unix socket and log file.

## Firmware and disk image

The firmware platform is `platcs8`. Import saves six boot images
under `firmware/kindle-scribe-colorsoft/boot_images`, with
`rootfs.img` in the model directory. It also extracts these files into
`peripherals/`:

- `focaltech_ts_fw_cp5d.bin` — FocalTech touch firmware
- `soc2_2_ram_mcu_mt8171_mt6631_1_hdr.bin` — connectivity firmware

The builder creates an 8 GiB sparse development disk with fresh user storage.
It prepares copies of the rootfs and boot FIT: USB Ethernet starts automatically,
root serial login is available, and verity is disabled for the prepared rootfs.
The catalogue enables QEMU development mode, which removes the production-key
requirement from the in-memory U-Boot handoff. Imported firmware stays unchanged.
See the [partition layout](storage.md#scribe-partitions).

The builder generates a synthetic CS8 V5 waveform.
The display preview shows guest pixels; colour and ghosting on a physical
panel are not reproduced.
