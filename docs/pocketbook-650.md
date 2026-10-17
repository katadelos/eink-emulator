# PocketBook Ultra 650

The Ultra 650 uses an i.MX6 SoloLite and 512 MiB RAM with a
758 × 1024 monochrome display, a capacitive touchscreen and physical buttons.

## Firmware

Import the official 5.14.798 update ZIP, or its extracted `SWUPDATE.BIN`:

```sh
./eink import /path/to/sw_20200623_650_W_5.14_798_user.zip --model pocketbook-650
./eink create pb650 --model pocketbook-650
./eink run pb650
```

The [official package](https://download.pocketbook-int.com/fw/Foxconn/650/user/20200623/sw_20200623_650_W_5.14_798_user.zip)
contains the original U-Boot, Linux 3.0.35 kernel, root filesystem and
application filesystem. Firmware belongs under `firmware/pocketbook-650/`;
it is excluded from Git.

The vendor publishes the [Platform_MX6 source tree](https://github.com/pocketbook/Platform_MX6).
The 650 sources are in `Uboot_650` and `Kernel`; their build configurations
are `650_config` and `650_defconfig`.

## Input

Click or drag in the display to use the touchscreen. Home operates the home
button, `M` or Escape operates the menu button, and the arrow keys operate
the navigation buttons. Page Up / Page Down also map to up / down.
`P` operates the power button and holding `H` closes the magnetic cover.

## Wi-Fi

The board uses the BCM43362 SDIO model on USDHC4 with the original DHD
driver and radio firmware. The emulated access point is `Kindle-QEMU`.
Scanning, association, reconnection, DHCP and IP traffic use the QEMU network
backend.

## Storage

The builder assembles a 2032 MiB internal card with the vendor raw boot area and
four partitions: root, applications, writable secure state and FAT32 user
storage. U-Boot starts at byte offset `0x400`, its environment at `0xc0000`
and the kernel at `0x100000`. Internal storage is attached to USDHC1.

The first boot installs the bundled factory content on the user partition.
The builder provisions a default serial, Wi-Fi MAC and matching secure callback
state for the original application startup code.
The original application CramFS, kernel and U-Boot binaries are retained.
The EPDC uses a generated neutral waveform for the emulator; this is not
physical panel calibration.

The original setup interface renders through the framebuffer and EPDC, with
touch and physical button input. Standby supports power-button wake.

Support is experimental. Camera, audio and GPU rendering are not emulated.
Firmware update and recovery paths are unverified.
