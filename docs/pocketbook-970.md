# PocketBook InkPad Lite (970)

The InkPad Lite uses an Allwinner B288 (`sun8iw10p1`), two Cortex-A7 cores,
512 MiB RAM and an 825 × 1200 monochrome display.

## Firmware

Import the official 6.8.4644 update ZIP, or its extracted `SWUPDATE.BIN`:

```sh
./eink import /path/to/sw_20250318_U970_6.8.4644_user.zip --model pocketbook-970
./eink create pb970 --model pocketbook-970
./eink run pb970
```

The [official update](https://download.pocketbook-int.com/fw/Jezetek/970/user/20250318/sw_20250318_U970_6.8.4644_user.zip)
contains the vendor U-Boot package, Linux 3.10.65 kernel, root filesystem,
application filesystem and recovery filesystem. Imported files live under
`firmware/pocketbook-970/` and are excluded from Git.

The board loader supplies boot0's DRAM and package-loading handoff, then
executes the original U-Boot. The original kernel, display module and
applications run from an assembled eMMC image. The builder selects hardware
configuration 67 and supplies secure factory state and a generated waveform.
Bundled content and fonts are installed on first boot. Automatic suspend is
disabled because SoC standby and its wakeup sources are not modeled.

The prepared IOC library uses its unprovisioned identity when the factory
record is absent. After a failed native read for that blank identity, the
monitor supplies a local configuration for a device without a contract.
Valid native reads and signature checks for writes use the stock code.
These adjustments apply to the prepared image; imported firmware remains
unchanged. Complete setup with the stock wizard and use Skip at account
screens for local reading. Manufacturer account and enrolment services are
not emulated.

## Network

Wi-Fi uses the XR819 SDIO model with the stock XRadio driver. Select the open
`PocketBook-QEMU` access point in the guest to connect through QEMU user networking.
See [networking](networking.md#pocketbook-wi-fi) for addresses and limits.

## Input

Click or drag in the display to use the FocalTech FT5726 touchscreen.
Page Up / Page Down, or Left / Right, operate the page buttons.
Home operates the home button.

Support is experimental. USB data transfer, the power button, cover sensing
and the orientation sensor are not implemented. Use the serial console for a
root shell. Recovery and firmware updates are unverified.
