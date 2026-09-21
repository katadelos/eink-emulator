# Kobo Forma

Forma runs stock U-Boot, Linux 4.1.15 and the Nickel interface. The model uses
a Netronix E80K02 board with an i.MX6SLL, 512 MiB RAM and a 1440 × 1920 display.
The tested device dumps use firmware 4.38.23171.

## Firmware

Put these files in `firmware/kobo-forma/`:

| File | Source |
| --- | --- |
| `u-boot.imx` | `upgrade/mx6sll-ntx/u-boot-mx6sll-E80K00-LPDDR2-512MB.imx` from the update |
| `boot-region.img` | First 49,152 sectors (24 MiB) of the device eMMC |
| `rootfs.img` | Device partition 1 |
| `recoveryfs.img` | Device partition 2 |

Use the bootloader from [mark 7 firmware 4.38.23171](https://ereaderfiles.kobo.com/firmwares/kobo7/Oct2024/kobo-update-4.38.23171.zip).
Replace `/path/to/` with your download location:

```sh
mkdir -p firmware/kobo-forma
unzip -p /path/to/kobo-update-4.38.23171.zip \
  upgrade/mx6sll-ntx/u-boot-mx6sll-E80K00-LPDDR2-512MB.imx \
  > firmware/kobo-forma/u-boot.imx
```

Copy or symlink your three dumps into the same directory. Do not install the
update over the captured rootfs. The builder repairs its journal on a copy.

U-Boot loads the remaining boot data from `boot-region.img`; separate eMMC
boot-partition dumps are not required. [Kobo's sources](https://github.com/kobolabs/Kobo-Reader/tree/master/hw/imx6sll-forma)
are available for kernel and bootloader work.

## Create and run

```sh
./eink create forma-ui --model kobo-forma --sideloaded
./eink run forma-ui
```

`--sideloaded` opens My Books in English without account setup. Omit the flag
for the normal setup flow. Later boots preserve settings.

The 2 GiB disk preserves root and recovery offsets and provides about
1.48 GiB for a fresh FAT32 userstore. Serial accepts `root` without a password.
See [networking](networking.md) for Wi-Fi and USB telnet.

## Controls

On macOS, `run` opens Cocoa.

| Action | Control |
| --- | --- |
| Tap or swipe | Click or drag |
| Previous page | `Page Up` or `Left` |
| Next page | `Page Down` or `Right` |
| Power button | `P` |
| Release the mouse | `Control–Option–G` |

## Display behavior and limits

EPDC working-buffer completion occurs before LUT completion. Separate
interrupts prevent a double free in the vendor kernel's marker handling.

Automatic rotation, battery discharge, frontlight optics and physical e-ink
ghosting are not emulated. The display uses the stock kernel's reserved
framebuffer address. Other kernel builds and firmware versions are unverified.
