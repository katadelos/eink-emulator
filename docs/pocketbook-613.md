# PocketBook Basic 613

The Basic 613 (Foxconn EP8) uses an i.MX50 and 128 MiB RAM with a
600 × 800 monochrome display and physical navigation buttons.

## Firmware

Import the official 4.0.477 update ZIP, or its extracted `SWUPDATE.BIN`:

```sh
./eink import /path/to/sw_20130314_613_EURO_br_4.0_613_477_user.zip --model pocketbook-613
./eink create pb613 --model pocketbook-613
./eink run pb613
```

The [official package](https://download.pocketbook-int.com/fw/Foxconn/613/user/20130314/sw_20130314_613_EURO_br_4.0_613_477_user.zip)
contains the original U-Boot, Linux 2.6.35.3 kernel, root filesystem and
application filesystem. Firmware belongs under `firmware/pocketbook-613/`;
it is excluded from Git.

The vendor publishes
[U-Boot](https://github.com/pocketbook-free/uboot_613) and
[kernel](https://github.com/pocketbook-free/kernel_613) repositories. The
vendor build configurations are `ep8_config` and `ep8_defconfig`.

## Input

Use the arrow keys to navigate, Enter to confirm, and Page Up / Page Down
for the page buttons. `P` operates the power button. The first boot displays
the original language selection and license screens.

The Basic 613 has no touchscreen or Wi-Fi. This machine has no network
forwarding configured.

## Storage

The firmware update contains component images rather than a complete disk.
The builder constructs a 2032 MiB eMMC with the vendor raw boot area and four
partitions: root, applications, writable secure state and FAT32 user storage.
The kernel occupies byte offset `0x280400`, as specified by the original
U-Boot configuration. Internal storage is attached to eSDHC3.

The virtual card uses byte addressing. Its capacity stays below 2 GiB to
avoid capacity-decoding bugs in the vendor loader.

The builder installs the bundled factory content on the first boot and
initializes the secure partition's permissions and callback state for the
emulated device identity. These factory files are absent from the update's
filesystem images. The original U-Boot, kernel and application binaries
are retained.

The EPDC uses a generated neutral waveform because physical panel calibration
is absent from the update. This waveform is for the emulator only.

Support is experimental; the stock boot chain, setup display and navigation
buttons work. Physical-device recovery and firmware updates are unverified.
