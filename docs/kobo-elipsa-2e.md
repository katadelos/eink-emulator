# Kobo Elipsa 2E

The `kobo-elipsa-2e` model boots stock U-Boot, Linux 4.9.77 and Nickel on
the Netronix EA0T00 / MediaTek MT8113T board. It has two Cortex-A53 cores,
1 GiB RAM and a 1404 × 1872 portrait Cocoa display with mouse-driven touch.

## Firmware

Put these files in `firmware/kobo-elipsa-2e/`:

| File | Source |
| --- | --- |
| `u-boot-mtk-fit.bin`, `boot.img`, `tee.img` | `upgrade/mt8113t-ntx/EA0T00-A0x30/` in the mark 11 update |
| `boot-region.img` | Device boot-region dump containing the original GPT |
| `mmcblk0p1.img` | BL2 partition |
| `mmcblk0p3.img` | NVRAM partition |
| `mmcblk0p6.img` | Hardware configuration |
| `mmcblk0p7.img` | Netronix firmware |
| `mmcblk0p9.img` | Vendor partition |
| `mmcblk0p10.img` | Root filesystem |
| `mmcblk0p11.img` | Recovery filesystem |

Bring-up uses the supplied `elipsa2e-work/` partition dumps with Nickel
4.38.23697 and the compiled boot components from
[mark 11 firmware 4.38.23552](https://ereaderfiles.kobo.com/firmwares/kobo11/Nov2025/kobo-update-4.38.23552.zip),
listed by [pgaskin's firmware index](https://pgaskin.net/KoboStuff/kobofirmware.html).
Extract only the boot components; do not install the update over the rootfs:

```sh
mkdir -p firmware/kobo-elipsa-2e
for file in u-boot-mtk-fit.bin boot.img tee.img; do
  unzip -p elipsa2e-work/kobo-update-4.38.23552.zip \
    "upgrade/mt8113t-ntx/EA0T00-A0x30/$file" \
    > "firmware/kobo-elipsa-2e/$file"
done
```

Copy or symlink the listed dumps from `elipsa2e-work/` into the firmware
directory. The builder generates an ext4 waveform partition containing a
synthetic `wf_lut.gz` for the stock HWTCON loader. The image
builder changes only copies. It clears stale ext4 journal transactions before
checking the captured rootfs, removes its cached device-node archive, and
enables passwordless root serial access.

[Kobo's kernel and U-Boot sources](https://github.com/kobolabs/Kobo-Reader/tree/master/hw/mt8113-elipsa2e)
were downloaded into `elipsa2e-work/reference/` and used to implement the
hardware interfaces. Neither vendor source tree is built.

## Create and run

```sh
./eink create elipsa2e-ui --model kobo-elipsa-2e --sideloaded
./eink run elipsa2e-ui --serial-socket --qmp-socket
```

On macOS, this opens Cocoa. Click to touch and drag for a single-finger
swipe. Control–Option–G releases QEMU's mouse grab.

`--sideloaded` installs a first-boot hook before Hindenburg and Nickel.
It creates `Kobo eReader.conf` with `SideloadedMode=true` and `en_US`, so
the reader opens My Books without language selection or account setup.
Later boots preserve existing settings. Omitting the flag retains the
normal setup flow.

The complete eMMC is 2 GiB, with about 1.32 GiB available for the FAT32
userstore. System partition numbers, offsets and UUIDs are preserved;
the builder shrinks partition 12 and relocates the backup GPT. Each
instance has a writable qcow2 overlay over the shared base.

## Implementation notes

The board loads the update's U-Boot FIT payload and supplies the BL2 boot
arguments. Stock U-Boot then loads the kernel and device tree from eMMC.
The model wires the PMIC, ADC, display supply, USB detector and Elan
EKTH3500 touchscreen to the existing MT8113 SoC devices.

Kobo's MDP commands use the older GCE masked-write encoding. The display
model converts the RGB framebuffer to grayscale, applies WROT rotation
and horizontal flip, and presents completed HWTCON image-buffer updates
in Nickel's portrait orientation. It handles aligned source tiles and the
one-bit packing used for fast partial updates. The Elan model implements firmware
queries, calibration, pen enable/status commands and single-finger reports.

Wi-Fi connectivity, Bluetooth, stylus drawing, automatic rotation,
frontlight optics and physical e-ink ghosting are not emulated. Other
firmware versions and kernel builds have not been validated.
