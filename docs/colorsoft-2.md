# Kindle Colorsoft 2

Experimental support for Colorsoft 2 uses the Julep (JP5) platform on the
MT8113 AO5 board, with 1 GiB RAM and a 1272 × 1696 colour display.
Its model ID is `kindle-colorsoft-2`. It opens unregistered Home with initial
setup skipped. First boot can take several minutes under TCG. Click the
display to tap, and join `Kindle-QEMU` in Wi-Fi settings for network access.

## Setup

Carve the supplied partition dump, then create an instance:

```sh
python3 scripts/carve-cs2.py /path/to/cs2_mmcblk.tar.gz
./eink create cs2 --model kindle-colorsoft-2 --profile production
./eink run cs2
```

The carver reads `0boot0.img`, `0boot1.img`, `p1.img` and `p8.img`.
It installs BL2, U-Boot, TEE, quickboot, the signed kernel FIT, the original
1536 MiB rootfs under
`firmware/kindle-colorsoft-2/`. It checks the Julep rootfs identity and refuses
to overwrite an existing destination.
Device identity, keys and captured persistent filesystems are not imported.
Recovery-package import and automatic firmware download are unavailable.

The shared AO5 disk builder creates an 8 GiB sparse disk, fresh persistent
filesystems, an ext4 userstore and a synthetic waveform partition. It
prepares a rootfs copy with offline setup, serial access, USB Ethernet and SSH.
Imported boot stages and firmware remain unchanged.

`production` and `dvt` select DVT hardware (ID 4). Other profiles are
`evt-doe` (3), `evt` (2), `hvt` (1) and `proto` (0).
See [networking](networking.md) for SSH and Wi-Fi access.

## Display

The preview displays RGB input pixels before colour-filter and waveform
processing. The CFA bypass avoids the stock software conversion under TCG.
The synthetic waveform supplies voltage tables for the FP9937 driver.
Physical panel colour and ghosting are not reproduced.
