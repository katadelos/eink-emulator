# PocketBook Basic Lux 4 (618)

The Basic Lux 4 uses an Allwinner B288 (`sun8iw10p1`), two Cortex-A7 cores,
512 MiB RAM and a 758 × 1024 E Ink Carta display.

## Firmware

Import the official 6.9.1044 update ZIP, or its extracted `SWUPDATE.BIN`:

```sh
./eink import /path/to/sw_20260520_U618_6.9.1044_user.zip --model pocketbook-618
./eink create pb618 --model pocketbook-618
./eink run pb618
```

The [official update](https://download.pocketbook-int.com/fw/Liangyan/618/user/20260520/sw_20260520_U618_6.9.1044_user.zip)
contains the vendor U-Boot package, Linux 3.10.65 kernel, root filesystem,
application filesystem and recovery filesystem. Imported files live under
`firmware/pocketbook-618/` and are excluded from Git. The vendor publishes
[B288 U-Boot sources](https://github.com/pocketbook/uboot_b288) and
[kernel sources](https://github.com/pocketbook/kernel-b288).

The board loader supplies boot0's DRAM and package-loading handoff, then
executes the original U-Boot. The original kernel, display module and
applications run from an assembled eMMC image. The builder supplies the
hardware configuration, factory state and a generated neutral waveform. The
prepared startup script disables automatic suspend because SoC standby and its
wakeup sources are not modeled.

The prepared image adjusts the 6.9.1044 IOC library's factory-record check to
use its unprovisioned identity. The update excludes the physical device's
factory record. For this blank identity, a failed configuration read supplies
a local partner configuration with contract and lock flags set to zero. It also
clears the monitor's reply header before caching it. Valid records and signed
writes retain their stock behavior. Imported firmware remains unchanged; these
adjustments apply only when building this model's image.

## Network

Wi-Fi uses the XR819 SDIO model with the stock XRadio driver. Select the open
`PocketBook-QEMU` access point in the guest to connect through QEMU user networking.
See [networking](networking.md#pocketbook-wi-fi) for addresses and limits.

## Input

Click or drag in the display to use the FocalTech FT6336 touchscreen. Page Up /
Page Down, or Left / Right, operate the page buttons. Home operates the home
button.

Support is experimental. USB data transfer, the power button, cover sensing
and external microSD storage are not implemented. Use the serial console for a
root shell. Recovery and firmware updates are unverified.
