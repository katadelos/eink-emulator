# PocketBook InkPad X (1040)

The InkPad X uses an Allwinner B288 (`sun8iw10p1`), two Cortex-A7 cores,
1 GiB RAM and a 1404 × 1872 monochrome display.

## Firmware

Import the official 6.5.2920 update ZIP, or its extracted `SWUPDATE.BIN`:

```sh
./eink import /path/to/sw_20220726_U1040_6.5.2920_user.zip --model pocketbook-1040
./eink create pb1040 --model pocketbook-1040
./eink run pb1040
```

The [official update](https://download.pocketbook-int.com/fw/Jezetek/1040/user/20220726/sw_20220726_U1040_6.5.2920_user.zip)
contains the vendor U-Boot package, Linux 3.10.65 kernel, root filesystem,
application filesystem and recovery filesystem. Imported files live under
`firmware/pocketbook-1040/` and are excluded from Git. The vendor publishes
[B288 U-Boot sources](https://github.com/pocketbook/uboot_b288) and
[kernel sources](https://github.com/pocketbook/kernel-b288), including
`1040_defconfig` and `sunxi_pack/sys_config.fex.1040`.

The board loader supplies boot0's DRAM and package-loading handoff, then
executes the original U-Boot. The original kernel, display module and
applications run from an assembled eMMC image. The builder supplies the
hardware configuration, secure factory state and a generated waveform.
The original startup script loads the Cypress touchscreen module directly.
The waveform supports emulation without reproducing physical panel calibration.
Bundled user content is installed on first boot.
The prepared startup script disables automatic suspend because SoC standby and
its wakeup sources are not modeled.

The prepared image patches the 6.5.2920 IOC library's factory-record check
to use its existing unprovisioned identity response. The vendor-signed record
is absent from the update, and the unmodified library stops without it.
Imported firmware remains unchanged; the patch applies only when building
this model's image.

The first application launch can take a few minutes while the firmware scans
its bundled fonts. Use **Skip** at the Wi-Fi setup step; radio initialization
can delay the transition to the bundled licence documents.

## Input

Click or drag in the display to use the Cypress touchscreen. Page Up / Page Down,
or Left / Right, operate the page buttons. Home operates the home button;
Escape or Backspace operates Back.

Support is experimental. Wi-Fi, Bluetooth, audio, USB data transfer, the power
button, cover sensing and orientation sensor are not implemented. Use the serial
console for a root shell; networking is unavailable. Recovery and firmware
updates are unverified.
