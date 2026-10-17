# PocketBook InkPad 3 Pro (740-2)

The InkPad 3 Pro uses an Allwinner B288 (`sun8iw10p1`), two Cortex-A7 cores,
1 GiB RAM and a 1404 × 1872 monochrome display.

## Firmware

Import the official 6.5.2917 update ZIP, or its extracted `SWUPDATE.BIN`:

```sh
./eink import /path/to/sw_20220726_U740-2_6.5.2917_user.zip --model pocketbook-740-2
./eink create pb740-2 --model pocketbook-740-2
./eink run pb740-2
```

The [official update](https://download.pocketbook-int.com/fw/Yitoa/740-2/user/20220726/sw_20220726_U740-2_6.5.2917_user.zip)
contains the vendor U-Boot package, Linux 3.10.65 kernel, root filesystem,
application filesystem and recovery filesystem. Imported files live under
`firmware/pocketbook-740-2/` and are excluded from Git. The vendor publishes
[B288 U-Boot sources](https://github.com/pocketbook/uboot_b288) and
[kernel sources](https://github.com/pocketbook/kernel-b288), including
`740-2_defconfig` and `sunxi_pack/sys_config.fex.740-2`.

The board loader supplies boot0's DRAM and package-loading handoff, then
executes the original U-Boot. The original kernel, display module and
applications run from an assembled eMMC image. The builder supplies the
hardware configuration, secure factory state, touchscreen module link and
a generated waveform. The waveform supports emulation without reproducing
physical panel calibration. Bundled user content is installed on first boot.
The prepared startup script disables automatic suspend because SoC standby and
its wakeup sources are not modeled.

## Network

Wi-Fi uses the XR819 SDIO model with the stock XRadio driver. Select the open
`PocketBook-QEMU` access point in the guest to connect through QEMU user networking.
See [networking](networking.md#pocketbook-wi-fi) for addresses and limits.

## Input

Click or drag in the display to use the Cypress touchscreen. Page Up / Page Down,
or Left / Right, operate the page buttons. Home operates the home button;
Escape or Backspace operates Back.

Support is experimental. Bluetooth, audio, USB data transfer, the power
button, cover sensing and orientation sensor are not implemented. Use the serial
console for a root shell. Recovery and firmware updates are unverified.
