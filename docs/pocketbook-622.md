# PocketBook Touch 622

The Touch 622 (Foxconn EP7) uses an i.MX50 and 128 MiB RAM with a
600 × 800 monochrome display, an ELAN touchscreen and physical buttons.

## Firmware

Import the official 4.4.565 update ZIP, or its extracted `SWUPDATE.BIN`:

```sh
./eink import /path/to/sw_20140204_622_EURO_us_syncV2_rr_s2pb_bookstore_br_4.4_565_user.zip --model pocketbook-622
./eink create pb622 --model pocketbook-622
./eink run pb622
```

The [official package](https://download.pocketbook-int.com/fw/Foxconn/622/4.4/sw_20140204_622_EURO_us_syncV2_rr_s2pb_bookstore_br_4.4_565_user.zip)
contains the original U-Boot, Linux 2.6.35.3 kernel, root filesystem and
application filesystem. Firmware belongs under `firmware/pocketbook-622/`;
it is excluded from Git.

The vendor publishes
[U-Boot](https://github.com/pocketbook-free/uboot_622) and
[kernel](https://github.com/pocketbook-free/kernel_622) repositories.
The vendor build configurations are `622_config` and `622_defconfig`.

## Input

Click or drag in the display to use the touchscreen. Home operates the home
button, `M` or Escape operates the menu button, Page Down / Page Up operate
the forward / backward buttons, and `P` operates the power button.

## Wi-Fi

The emulated board uses the WC121 revision with a BCM43362 module on eSDHC2.
The original DHD driver and radio firmware are retained. Enable Wi-Fi and
join the open `Kindle-QEMU` access point to use QEMU's network backend.

## Storage

The builder constructs a 2032 MiB eMMC with the vendor raw boot area and four
partitions: root, applications, writable secure state and FAT32 user storage.
The kernel occupies byte offset `0x280400`; internal storage is attached to
eSDHC3. The byte-addressed card stays below 2 GiB to avoid capacity-decoding
bugs in the vendor loader.

The first boot installs the bundled factory content on the user partition.
The builder initializes the secure partition's permissions and callback state
for the firmware's default device identity.
The original application CramFS, kernel and U-Boot binaries are retained.
The EPDC uses a generated neutral waveform for the emulator; this is not
physical panel calibration.

Support is experimental. The stock boot chain, setup display, touch, physical
buttons, standby/wake and Wi-Fi scanning, association and DHCP work. Recovery
and firmware updates are unverified.
