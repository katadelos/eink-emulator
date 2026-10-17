# PocketBook Touch HD 3 (632)

The Touch HD 3 uses an Allwinner B288 (`sun8iw10p1`), two Cortex-A7 cores,
512 MiB RAM and a 1072 × 1448 monochrome display.

## Firmware

Import the official 6.9.1035 update ZIP, or its extracted `SWUPDATE.BIN`:

```sh
./eink import /path/to/sw_20260512_U632_6.9.1035_user.zip --model pocketbook-632
./eink create touchhd3 --model pocketbook-632
./eink run touchhd3
```

The [official update](https://download.pocketbook-int.com/fw/Yitoa/632/user/20260512/sw_20260512_U632_6.9.1035_user.zip)
contains the vendor U-Boot package, Linux 3.10.65 kernel, root filesystem,
application filesystem and recovery filesystem. Imported files live under
`firmware/pocketbook-632/` and are excluded from Git. The vendor publishes
[B288 U-Boot sources](https://github.com/pocketbook/uboot_b288) and
[kernel sources](https://github.com/pocketbook/kernel-b288), including
`632_defconfig` and the board's device tree.

The board loader supplies boot0's DRAM and package-loading handoff, then
executes the original U-Boot. The original kernel, display module and
applications run from an assembled eMMC image. The builder supplies the
632 hardware configuration, secure factory state and a generated waveform.
Bundled user content is installed on first boot.

## Network

Wi-Fi uses the XR819 SDIO model with the stock XRadio driver. Select the open
`PocketBook-QEMU` access point in the guest to connect through QEMU user networking.
See [networking](networking.md#pocketbook-wi-fi) for addresses and limits.

## Input

Click or drag in the display to use the touchscreen. Page Up / Page Down,
or Left / Right, operate the page buttons. Home operates the home button;
Escape or Backspace operates Back.

## Implementation

The reusable [B288 SoC](../qemu/hw/arm/allwinner-b288.c) contains the CPUs,
interrupt controller, clocks, GPIO, timers, RTC, ADC, UART, I²C and MMC
controllers. Its [display engine](../qemu/hw/display/allwinner-b288-eink.c)
renders EINK transition buffers and supplies completion and timing interrupts.
The [PocketBook board profiles](../qemu/hw/arm/allwinner-b288-pocketbook.c)
supply each board's RAM, panel geometry, display power wiring and input
configuration, sharing peripheral attachment and firmware loading.

Bluetooth, audio, USB data transfer, the power button and cover sensing
are not implemented. Use the serial console for a root shell.
