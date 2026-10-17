# PocketBook Era (700)

The Era uses an Allwinner B288 (`sun8iw10p1`), two Cortex-A7 cores,
1 GiB RAM and a 1264 × 1680 monochrome display.

## Firmware

Import the official 6.10.3209 update ZIP, or its extracted `SWUPDATE.BIN`:

```sh
./eink import /path/to/sw_20260223_U700_6.10.3209_user.zip --model pocketbook-700
./eink create pb700 --model pocketbook-700
./eink run pb700
```

The [official update](https://download.pocketbook-int.com/fw/Jezetek/700/user/20260223/sw_20260223_U700_6.10.3209_user.zip)
contains the vendor U-Boot package, Linux 3.10.65 kernel, root filesystem,
application filesystem and recovery filesystem. Imported files live under
`firmware/pocketbook-700/` and are excluded from Git.

The board loader supplies boot0's DRAM and package-loading handoff, then
executes the original U-Boot. The original kernel, display module and
applications run from an assembled eMMC image. The builder selects the Era's
hardware configuration and supplies secure factory state and a generated waveform.
The waveform's `ED070` identifier selects the vendor driver's Era panel timings.
Bundled user content is installed on first boot. The prepared startup script
disables automatic suspend because SoC standby and its wakeup sources are not modeled.

The prepared image adjusts the 6.10.3209 IOC library's factory-record
check to use its existing unprovisioned identity response. The vendor-signed
record is absent from the update. For the emulator's all-zero serial, failed
native factory reads receive a local configuration for a device without a
contract. The stock reader handles valid native records and verifies signed
record writes. These adjustments apply when building this model's image;
imported firmware remains unchanged.

## Network

Wi-Fi uses the XR819 SDIO model with the stock XRadio driver. Select the open
`PocketBook-QEMU` access point in the guest to connect through QEMU user networking.
See [networking](networking.md#pocketbook-wi-fi) for addresses and limits.

## Input

Click or drag in the display to use the FocalTech FT5436 touchscreen.
Page Up / Page Down, or Left / Right, operate the page buttons.
Home operates the home button.

Support is experimental. Bluetooth, audio, USB data transfer, the power
button, cover sensing and orientation sensor are not implemented. Use the serial
console for a root shell. Recovery and firmware updates are unverified.
