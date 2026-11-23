# Kindle Paperwhite 7

Experimental support for PW7 uses the Amaro (AO5) MediaTek board with 1 GiB
RAM and a 1272 × 1696 monochrome display. Its model ID is
`kindle-paperwhite-7`.
The emulator skips account setup. Click the display to tap, and join
`Kindle-QEMU` in Wi-Fi settings for network access.

## Setup

Import a Paperwhite 7 update package, then create an instance:

```sh
./eink import /path/to/update.bin --model kindle-paperwhite-7
./eink create pw7 --model kindle-paperwhite-7 --profile production
./eink run pw7
```

To download and import automatically, skip `import` and add `--firmware latest`
to `create`.

The disk builder creates an 8 GiB sparse disk with fresh persistent storage,
an ext4 userstore and a synthetic waveform for the FP9937 power controller.
It prepares a separate rootfs copy with offline setup, serial access and
[SSH networking](networking.md). Imported firmware remains unchanged.

`production` and `dvt` select DVT hardware (ID 4). The other profiles are
`evt-doe` (3), `evt` (2), `hvt` (1) and `proto` (0).

## Partition dump utility

```sh
python3 scripts/carve-pw7.py /path/to/pw7_mmcblk.tar
```

The dump utility reads `0boot0.img`, `p1.img` and `p8.img`. It installs BL2,
U-Boot, TEE, the signed kernel FIT and the original rootfs under
`firmware/kindle-paperwhite-7/`. It refuses to overwrite that directory.
