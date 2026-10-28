# Kindle Paperwhite 7

PW7 uses the Amaro (AO5) MediaTek board with 1 GiB RAM and a 1272 × 1696
monochrome display. Its model ID is `kindle-paperwhite-7`.
It opens the unregistered Home screen with account setup skipped. Click the
display to tap, and join `Kindle-QEMU` in Wi-Fi settings for network access.

## Setup

Extract the supplied partition dump, then create an instance:

```sh
python3 scripts/carve-pw7.py /path/to/pw7_mmcblk.tar
./eink create pw7 --model kindle-paperwhite-7 --profile production
./eink run pw7
```

The dump utility reads `0boot0.img`, `p1.img` and `p8.img`. It installs BL2,
U-Boot, TEE, the signed kernel FIT and the original rootfs under
`firmware/kindle-paperwhite-7/`. It refuses to overwrite that directory.
The bootloader and kernel images are unchanged. Device identity, keys and
captured persistent data are not imported.

The disk builder creates an 8 GiB sparse disk with fresh persistent storage,
an ext4 userstore and a synthetic waveform for the FP9937 power controller.
It prepares a separate rootfs copy with offline setup, serial access and
[SSH networking](networking.md). Imported firmware remains unchanged.

`production` and `dvt` select DVT hardware (ID 4). The other profiles are
`evt-doe` (3), `evt` (2), `hvt` (1) and `proto` (0).
