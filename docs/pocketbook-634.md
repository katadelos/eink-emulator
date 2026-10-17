# PocketBook Verse Pro (634)

The Verse Pro uses an Allwinner B288 (`sun8iw10p1`), two Cortex-A7 cores,
512 MiB RAM and a 1072 × 1448 monochrome display.

## Firmware

Import the official 6.10.3425 update ZIP, or its extracted `SWUPDATE.BIN`:

```sh
./eink import /path/to/sw_20260324_U634_6.10.3425_user.zip --model pocketbook-634
./eink create pb634 --model pocketbook-634
./eink run pb634
```

The [official update](https://download.pocketbook-int.com/fw/Yitoa/634/user/20260324/sw_20260324_U634_6.10.3425_user.zip)
contains the vendor U-Boot package, Linux 3.10.65 kernel, root filesystem,
application filesystem and recovery filesystem. Imported files live under
`firmware/pocketbook-634/` and are excluded from Git. This profile supports
the original Cypress touchscreen revision selected by hardware index 81.

The board loader supplies boot0's DRAM and package-loading handoff, then
executes the original U-Boot. The original kernel, display module and
applications run from an assembled eMMC image. The builder supplies the
hardware configuration, secure factory state and a generated waveform.
Bundled user content and fonts are installed on first boot. Automatic suspend
is disabled because SoC standby and its wakeup sources are not modeled.

The prepared IOC library uses its unprovisioned identity when the factory record
is absent. The monitor supplies a local non-contract configuration only after
a failed native read for that blank identity. This emulator default is not a
vendor-signed factory record. Valid configuration reads and signature checks
for writes retain their original behavior. The provider also initializes failed
read headers so the stock monitor's cache cannot copy an uninitialized length.
Imported firmware remains unchanged; preparation applies to this model's image.

The 2 GiB eMMC image has a 511 MiB applications partition and a 1.25 GiB user
partition. Complete setup with the stock wizard and use Skip at account screens
for local reading. Manufacturer account and device enrolment services are not
emulated.

## Network

Wi-Fi uses the XR819 SDIO model with the stock XRadio driver. Select the open
`PocketBook-QEMU` access point in the guest to connect through QEMU user networking.
See [networking](networking.md#pocketbook-wi-fi) for addresses and limits.

## Input

Click or drag in the display to use the Cypress touchscreen. Page Up / Page Down,
or Left / Right, operate the page buttons. Home operates the home button.

Support is experimental. Bluetooth, audio, USB data transfer, the power
button and cover sensing are not implemented. Use the serial console for a
root shell.
