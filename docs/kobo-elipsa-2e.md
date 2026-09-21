# Kobo Elipsa 2E

Elipsa 2E runs stock U-Boot, Linux 4.9.77 and the Nickel interface. The model
uses a Netronix EA0T00 / MediaTek MT8113T board, two Cortex-A53 cores, 1 GiB RAM
and a 1404 × 1872 portrait display.

## Firmware

Put these files in `firmware/kobo-elipsa-2e/`:

| File | Source |
| --- | --- |
| `u-boot-mtk-fit.bin`, `boot.img`, `tee.img` | `upgrade/mt8113t-ntx/EA0T00-A0x30/` in the mark 11 update |
| `boot-region.img` | Device boot-region dump with the original GPT |
| `mmcblk0p1.img` | BL2 partition |
| `mmcblk0p3.img` | NVRAM partition |
| `mmcblk0p6.img` | Hardware configuration |
| `mmcblk0p7.img` | Netronix firmware |
| `mmcblk0p9.img` | Vendor partition |
| `mmcblk0p10.img` | Root filesystem |
| `mmcblk0p11.img` | Recovery filesystem |

The tested setup combines Nickel 4.38.23697 device dumps with boot components
from [mark 11 firmware 4.38.23552](https://ereaderfiles.kobo.com/firmwares/kobo11/Nov2025/kobo-update-4.38.23552.zip).
Extract the boot components only. Do not install the update over the captured
rootfs. Replace `/path/to/` with your download location:

```sh
mkdir -p firmware/kobo-elipsa-2e
for file in u-boot-mtk-fit.bin boot.img tee.img; do
  unzip -p /path/to/kobo-update-4.38.23552.zip \
    "upgrade/mt8113t-ntx/EA0T00-A0x30/$file" \
    > "firmware/kobo-elipsa-2e/$file"
done
```

Copy or symlink the listed dumps into the same directory. The builder discards
stale journal transactions on a rootfs copy; replaying them would restore old
inode mappings over current files. It also generates the waveform partition.
[Kobo's sources](https://github.com/kobolabs/Kobo-Reader/tree/master/hw/mt8113-elipsa2e)
are available for kernel and bootloader work.

## Create and run

```sh
./eink create elipsa2e-ui --model kobo-elipsa-2e --sideloaded
./eink run elipsa2e-ui
```

`--sideloaded` opens My Books in English without account setup. Omit the flag
for the normal setup flow. Later boots preserve settings.

The 2 GiB disk provides about 1.32 GiB for a fresh FAT32 userstore. The builder
preserves system partition numbers, offsets and UUIDs, shrinks partition 12
and moves the backup GPT to the new disk boundary.

On macOS, `run` opens Cocoa. Click to tap and drag to swipe. Use
`Control–Option–G` to release the mouse. Serial accepts `root` without a
password. See [networking](networking.md) for Wi-Fi and USB telnet over RNDIS.

## Limits

Bluetooth, stylus drawing, automatic rotation, frontlight optics and physical
e-ink ghosting are not emulated. Other firmware versions and kernel builds
are unverified.
