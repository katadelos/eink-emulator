# PocketBook InkPad 3 (740)

The InkPad 3 uses an Allwinner B288 (`sun8iw10p1`), two Cortex-A7 cores,
1 GiB RAM and a 1404 × 1872 monochrome display.

## Firmware

Import the official 6.8.4473 update ZIP, or its extracted `SWUPDATE.BIN`:

```sh
./eink import /path/to/sw_20250110_U740_6.8.4473_user.zip --model pocketbook-740
./eink create inkpad3 --model pocketbook-740
./eink run inkpad3
```

The [official update](https://download.pocketbook-int.com/fw/Yitoa/740/user/20250110/sw_20250110_U740_6.8.4473_user.zip)
contains the vendor U-Boot package, Linux 3.10.65 kernel, root filesystem,
application filesystem and recovery filesystem. Imported files live under
`firmware/pocketbook-740/` and are excluded from Git. The vendor publishes
[B288 U-Boot sources](https://github.com/pocketbook/uboot_b288) and
[kernel sources](https://github.com/pocketbook/kernel-b288), including
`740_defconfig`.

The board loader supplies boot0's DRAM and package-loading handoff, then
executes the original U-Boot. The original kernel, display module and
application binaries run from the assembled eMMC image. The builder supplies
the hardware configuration, secure factory state, touchscreen module link and
a generated waveform. The waveform supports emulation without reproducing
physical panel calibration. Bundled user content is installed on first boot.

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
supply RAM, panel geometry, PMIC wiring and input configuration for the 740 and
[632](pocketbook-632.md), sharing peripheral attachment and firmware loading.

Audio, USB data transfer, the power button and cover sensing are not
implemented. Use the serial console for a root shell.
