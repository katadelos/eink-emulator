# PocketBook InkPad Color (741)

The InkPad Color uses an Allwinner B288 (`sun8iw10p1`), two Cortex-A7 cores,
1 GiB RAM and a 1404 × 1872 Kaleido Plus display. Black-and-white content uses
the full panel resolution; color content has a 468 × 624 effective resolution.

## Firmware

Import the official 6.8.4079 update ZIP, or its extracted `SWUPDATE.BIN`:

```sh
./eink import /path/to/sw_20240906_U741_6.8.4079_user.zip --model pocketbook-741
./eink create inkpad-color --model pocketbook-741
./eink run inkpad-color
```

The [official update](https://download.pocketbook-int.com/fw/Yitoa/741/user/20240906/sw_20240906_U741_6.8.4079_user.zip)
contains the vendor U-Boot package, Linux 3.10.65 kernel, root filesystem,
application filesystem and recovery filesystem. Imported files live under
`firmware/pocketbook-741/` and are excluded from Git. The vendor publishes
[B288 U-Boot sources](https://github.com/pocketbook/uboot_b288), including
`sunxi_pack/sys_config.fex.741`, and [kernel sources](https://github.com/pocketbook/kernel-b288).

The board loader supplies boot0's DRAM and package-loading handoff, then
executes the original U-Boot. The original kernel, display module and
applications run from an assembled eMMC image. The builder supplies the
hardware configuration, factory state, Cypress touchscreen module link and
a generated waveform named `EC078`. The panel name selects the stock driver's
Kaleido Plus color mode. The prepared startup script disables automatic suspend
because SoC standby and its wakeup sources are not modeled.

The prepared image adjusts the 6.8.4079 IOC library's factory-record check to
use its unprovisioned identity. The update excludes the physical device's
factory record. For this blank identity, a failed configuration read supplies
a local partner configuration with contract and lock flags set to zero. It also
clears the monitor's reply header before caching it. Valid records and signed
writes retain their stock behavior. Imported firmware remains unchanged; these
adjustments apply only when building this model's image.

## Display

The stock application library converts RGB content to individual Kaleido filter
pixels before the stock EPDC module constructs EINK transitions. The emulator
renders those transitions through the panel's six-column, two-row RGB filter
pattern and interpolates nearby channel samples. Panel updates retain their
DMA, completion interrupts and timing behavior. Filter transmission, physical
waveform calibration and the panel's measured color gamut are not reproduced.

## Network

Wi-Fi uses the XR819 SDIO model with the stock XRadio driver. Select the open
`PocketBook-QEMU` access point in the guest to connect through QEMU user networking.
See [networking](networking.md#pocketbook-wi-fi) for addresses and limits.

## Input

Click or drag in the display to use the Cypress touchscreen. Page Up / Page Down,
or Left / Right, operate the page buttons. Home operates the home button.

Support is experimental. Bluetooth, audio, USB data transfer, the power
button, cover sensing and orientation sensor are not implemented. Use the serial
console for a root shell. Recovery and firmware updates are unverified.
