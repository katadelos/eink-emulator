# Kindle Colorsoft 2

Experimental support for Colorsoft 2 uses the Julep (JP5) platform on the
MT8113 AO5 board, with 1 GiB RAM and a 1272 × 1696 colour display.
Its model ID is `kindle-colorsoft-2`. The emulator skips account setup.
First boot can take several minutes under TCG. Click the
display to tap, and join `Kindle-QEMU` in Wi-Fi settings for network access.

## Setup

Import a Colorsoft 2 update package, then create an instance:

```sh
./eink import /path/to/update.bin --model kindle-colorsoft-2
./eink create cs2 --model kindle-colorsoft-2 --profile production
./eink run cs2
```

To download and import automatically, skip `import` and add `--firmware latest`
to `create`.

The shared AO5 disk builder creates an 8 GiB sparse disk, fresh persistent
filesystems and an ext4 userstore. It prepares a rootfs copy with offline
setup, serial access, USB Ethernet and SSH. The builder generates the
waveform partition for both update packages and partition dumps.
Imported boot stages and firmware remain unchanged.

`production` and `dvt` select DVT hardware (ID 4). Other profiles are
`evt-doe` (3), `evt` (2), `hvt` (1) and `proto` (0).
See [networking](networking.md) for SSH and Wi-Fi access.

## Partition dump utility

```sh
python3 scripts/carve-cs2.py /path/to/cs2_mmcblk.tar.gz
```

The carver reads `0boot0.img`, `0boot1.img`, `p1.img` and `p8.img`.
It installs the boot stages, signed kernel FIT and rootfs under
`firmware/kindle-colorsoft-2/`. It checks the Julep rootfs identity and
refuses to overwrite an existing destination.

## Display

The preview displays RGB input pixels before colour-filter and waveform
processing. The CFA bypass avoids the stock software conversion under TCG.
The synthetic waveform supplies voltage tables for the FP9937 driver.
Physical panel colour and ghosting are not reproduced.
