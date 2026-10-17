# reMarkable 1

The Zero Gravitas board uses the shared i.MX6 SoloLite SoC model with
512 MiB RAM, a 1404 × 1872 EPDC display, Wacom W9013 digitizer,
Cypress touchscreen and GPIO buttons. The QEMU machine is
`imx6sl-remarkable1`.

## Firmware

Import the reMarkable 1 SWU package, then create an instance:

```sh
./eink import /path/to/remarkable-production-image-3.27.1.0-rm1-public.swu --model remarkable-1
./eink create remarkable1 --model remarkable-1
./eink run remarkable1
```

The [3.27.1.0 package](https://remarkable-software.s3.us-east-2.amazonaws.com/remarkable-production-image-3.27.1.0-rm1-public.swu)
contains vendor U-Boot 2016.05, Linux 5.4.70, the device tree,
panel waveform and Xochitl. The importer reads the SWU archive without
running its installer scripts. Imported files belong under
`firmware/remarkable-1/` and are excluded from Git.

Vendor sources are available for
[U-Boot](https://github.com/reMarkable/uboot/tree/zero-gravitas) and
[Linux](https://github.com/reMarkable/linux/tree/rm1xx_5.4.70_v1.6.x).
The emulator boots the original firmware binaries.

## Offline interface

Prepared images open at Xochitl's **My files** interface. Create notebooks
and quick sheets through the plus button. Documents and settings persist
in the instance disk.

The builder writes `[General] Setup=false` to
`/var/lib/uboot/xochitl/xochitl.conf` on the factory FAT volume.
This is separate from the main user configuration at
`/home/root/.config/remarkable/xochitl.conf`.

## Input

The pointer starts in pen mode. Left-click or drag to tap and write.
Select the Eraser in the toolbar to erase. `T` selects finger input and
`P` returns to the pen. Mouse input supplies fixed pressure and zero tilt.

Left / Page Up, Home, and Right / Page Down operate the three front
buttons. QEMU's Power key operates the power button.

## Storage and serial

The builder creates a 4 GiB eMMC image on USDHC2. It contains the factory
FAT volume, two 512 MiB system slots, two reserved volumes and writable
`/home`, preserving the stock partition numbers. U-Boot reads the kernel
and device tree from the active system slot.

The serial console logs in as root automatically. Use `--serial-socket`
for a socket and log, or use the launching terminal normally.

Support is experimental. Wi-Fi, USB networking, cloud services and
firmware updates are not implemented. Suspend and recovery paths are
unverified.
