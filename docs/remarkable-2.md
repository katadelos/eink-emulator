# reMarkable 2

The Zero Sugar board uses the shared i.MX7D SoC with two Cortex-A7 cores,
1 GiB RAM and an 8 GiB eMMC. Its QEMU machine is `imx7d-remarkable2`.
The board wires the Wacom W9021 digitizer, Parade touchscreen, BD71815
PMIC, MAX77818 charger/fuel gauge and SY7636 display supply.

## Firmware

```sh
./eink import /path/to/remarkable-production-image-3.27.1.0-rm2-public.swu --model remarkable-2
./eink create remarkable2 --model remarkable-2
./eink run remarkable2
```

The [3.27.1.0 package](https://remarkable-software.s3.us-east-2.amazonaws.com/remarkable-production-image-3.27.1.0-rm2-public.swu)
contains vendor U-Boot 2018.03, Linux 5.4.70, the device tree, Xochitl
and the ED103TC2M1 waveform. The importer extracts the root filesystem
and U-Boot without running the update scripts. Firmware belongs under
`firmware/remarkable-2/` and is excluded from Git.

Vendor sources are available for
[U-Boot](https://github.com/reMarkable/uboot/tree/zero-sugar) and
[Linux](https://github.com/reMarkable/linux/tree/rm1xx_5.4.70_v1.6.x).
The emulator boots the original binaries. Xochitl's SWTCON drives the
shared LCDIF model; a separate panel model decodes its source-driver
signals into the 1404 × 1872 portrait display.

## Interface and input

Prepared images open at **My files** for offline notebook use. The factory
flag `[General] Setup=false` lives in
`/var/lib/uboot/xochitl/xochitl.conf`, independently of the user settings.
Notebooks and settings persist in the instance disk.

The pointer starts in pen mode. Left-click or drag to tap and write.
`T` selects finger input; `P` returns to the pen. Select the Eraser from
the notebook toolbar to erase. Mouse input supplies fixed pressure and
zero tilt. QEMU's Power key operates the SNVS power button.

## Storage and serial

The eMMC is attached to USDHC3. Partition 1 holds factory settings and the
selected waveform; partitions 2 and 3 are 512 MiB system slots. Partition
4 holds `/home`. This differs from reMarkable 1's extended partition layout.
U-Boot loads the kernel and device tree from the active system slot.
The eMMC boot area contains synthetic factory serial numbers.

The serial console logs in as root automatically. `--serial-socket`
provides a socket and log; otherwise use the launching terminal.
Prepared images disable network socket activation and WPA supplicant;
the writable filesystems use ext4 journaling.

Support is experimental. Panel reflectance accumulates source-driver pulses;
the analog response and ghosting are approximations. Wi-Fi, USB networking,
cloud services and firmware updates are not implemented. Full suspend and
recovery paths are unverified.
