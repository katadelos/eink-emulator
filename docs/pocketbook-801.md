# PocketBook Color Lux 801

The Color Lux 801 uses an i.MX50 and 256 MiB RAM with a 600 × 800 Triton
colour e-paper display. The panel interface carries 1800 × 800 colour subpixels.

## Firmware

Import the official 4.1.915 update ZIP, or its extracted `SWUPDATE.BIN`:

```sh
./eink import /path/to/sw_20131025_801_W_us_sync_rr_bookstore_br_4.1_801_915_default_default_triton_user.zip --model pocketbook-801
./eink create pb801 --model pocketbook-801
./eink run pb801
```

The [official package](https://download.pocketbook-int.com/fw/Yitoa/801/user/sw_20131025_801_W_us_sync_rr_bookstore_br_4.1_801_915_default_default_triton_user.zip)
contains the original U-Boot, Linux 2.6.35.3 kernel, root filesystem and
application filesystem. Imported firmware belongs under `firmware/pocketbook-801/`
and is excluded from Git.

The vendor publishes the [801 kernel and U-Boot sources](https://github.com/pocketbook/801).
The build configurations are `801_config` and `801_defconfig`.

## Input

Click or drag in the display to use the Goodix touchscreen. `M` operates Menu,
Escape or Home operates Back, and the up/down arrows or Page Up / Page Down
operate the navigation buttons. `P` operates the power button. The bracket keys
`[` and `]` operate the capacitive frontlight slider.

The stock power action suspends the guest and shows its sleep overlay. Press
`P` again to resume.

## Network

Wi-Fi uses the RTL8188EU USB model with the original driver. Select the open
`Kindle-QEMU` access point in the guest to connect through QEMU user networking.
See [networking](networking.md#pocketbook-wi-fi) for addresses and limits.

## Storage and display

The builder assembles a 4 GiB internal card on eSDHC3 with root, application,
secure and FAT32 user partitions. The kernel starts at byte offset `0x100000`,
the U-Boot environment at `0xc0000` and the colour boot logo at `0x1000000`.
The guest identifies this card as `mmcblk0`.

The first boot installs the bundled factory content on user storage. The builder
provisions a serial and matching secure state for application startup.
The original U-Boot, kernel and application CramFS binaries are retained.

The emulator combines the panel's red, green and blue subpixels into a colour
display surface. A generated neutral waveform supplies the factory calibration
file omitted by the update; it is not physical panel calibration.

Support is experimental. Audio is not emulated. Recovery and firmware
updates are unverified.
