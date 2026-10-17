# PocketBook Touch Lux 623

The Touch Lux 623 (Foxconn EP7A) uses an i.MX50 and 128 MiB RAM with a
758 × 1024 monochrome display, a touchscreen, physical buttons and a frontlight.

## Firmware

Import the official 4.4.614 update ZIP, or its extracted `SWUPDATE.BIN`:

```sh
./eink import /path/to/sw_20140213_623_W_us_syncV2_rr_s2pb_bookstore_br_4.4_614_user.zip --model pocketbook-623
./eink create pb623 --model pocketbook-623
./eink run pb623
```

The [official package](https://download.pocketbook-int.com/fw/Foxconn/623/user/20140213/sw_20140213_623_W_us_syncV2_rr_s2pb_bookstore_br_4.4_614_user.zip)
contains the original U-Boot, Linux 2.6.35.3 kernel, root filesystem and
application filesystem. Firmware belongs under `firmware/pocketbook-623/`;
it is excluded from Git.

The vendor publishes
[U-Boot](https://github.com/pocketbook-free/uboot_623) and
[kernel](https://github.com/pocketbook-free/kernel_623) repositories.
The vendor build configurations are `ep7a_config` and `ep7a_defconfig`;
`623_defconfig` links to the latter.

## Input

Click or drag in the display to use the touchscreen. Home operates the home
button, `M` or Escape operates the menu button, Page Down / Page Up operate
the forward / backward buttons, and `P` operates the power button.
Standby supports power-button wake.

The stock frontlight controls update PWM1 duty and its GPIO6_9 power gate.
The display surface keeps its normal contrast.

## Wi-Fi

The board uses the BCM43362 SDIO model on eSDHC2 with the original DHD driver
and radio firmware. The emulated access point is `Kindle-QEMU`.
Scanning, association, DHCP and IP traffic use the QEMU network backend.

## Storage

The builder constructs a 2032 MiB internal card with the vendor raw boot area
and four partitions: root, applications, writable secure state and FAT32 user
storage. Internal storage is attached to eSDHC3. The byte-addressed card stays
below 2 GiB to avoid capacity-decoding bugs in the vendor loader.

The first boot installs the bundled factory content on the user partition.
The builder initializes secure storage for the firmware's default device identity.
The original application CramFS, kernel and U-Boot binaries are retained.
The EPDC uses a generated neutral waveform for the emulator; this is not
physical panel calibration.

Support is experimental. The stock setup interface, touch, physical buttons and
frontlight controls are supported. Audio is not emulated. Recovery and firmware
updates are unverified.
