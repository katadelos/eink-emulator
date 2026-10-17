# PocketBook Touch Lux 5 (628)

The Touch Lux 5 uses an Allwinner B288 (`sun8iw10p1`), two Cortex-A7 cores,
512 MiB RAM and a 758 × 1024 monochrome display.

## Firmware

Import the official 6.5.2890 update ZIP, or its extracted `SWUPDATE.BIN`:

```sh
./eink import /path/to/sw_20220720_U628_6.5.2890_user.zip --model pocketbook-628
./eink create pb628 --model pocketbook-628
./eink run pb628
```

The [official update](https://download.pocketbook-int.com/fw/Yitoa/628/user/20220720/sw_20220720_U628_6.5.2890_user.zip)
contains the vendor U-Boot package, Linux 3.10.65 kernel, root filesystem, application
filesystem and recovery filesystem. Imported files live under
`firmware/pocketbook-628/` and are excluded from Git. The vendor publishes
[B288 U-Boot sources](https://github.com/pocketbook/uboot_b288) and
[kernel sources](https://github.com/pocketbook/kernel-b288), including
`628_defconfig` and `sunxi_pack/sys_config.fex.628`.

The board loader supplies boot0's DRAM and package-loading handoff, then
executes the original U-Boot. The original kernel, display module and
applications run from an assembled eMMC image. The builder supplies the
hardware configuration, secure factory state, touchscreen module link and
a generated waveform. The waveform supports emulation without reproducing
physical panel calibration. Bundled user content is installed on first boot.
The prepared startup script disables automatic suspend because SoC standby and
its wakeup sources are not modeled.

The prepared image patches the 6.5.2890 IOC library's factory-record check
to use a fixed emulator identity. The vendor-signed record is absent from the
update, and the unmodified library stops without it. Imported firmware remains
unchanged; the patch applies only when building this model's image.

The first reader launch can take a few minutes while the firmware scans its
bundled fonts.

Use **Skip** at the Wi-Fi setup step. Radio initialization can delay the
transition to the bundled licence documents.

## Input

The machine models the original 628 with its ELAN touchscreen (`ektf2k_5B.ko`).
Click or drag in the display to use the touchscreen. Page Up / Page Down,
or Left / Right, operate the page buttons. Home operates the home button;
Escape or Backspace operates Back.

Support is experimental. Wi-Fi, Bluetooth, audio, USB data transfer, the power
button and cover sensing are not implemented. Use the serial console for a
root shell; networking is unavailable.
