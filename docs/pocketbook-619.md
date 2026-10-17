# PocketBook Verse Lite (619)

The Verse Lite uses an Allwinner B288 (`sun8iw10p1`), two Cortex-A7 cores,
512 MiB RAM and a 758 × 1024 monochrome display.

## Firmware

Import the official 6.11.2022 update ZIP, or its extracted `SWUPDATE.BIN`:

```sh
./eink import /path/to/sw_20260902_U619_6.11.2022_user.zip --model pocketbook-619
./eink create pb619 --model pocketbook-619
./eink run pb619
```

The [official update](https://download.pocketbook-int.com/fw/Yitoa/619/user/20260902/sw_20260902_U619_6.11.2022_user.zip)
contains the vendor U-Boot package, Linux kernel, root filesystem,
application filesystem and recovery filesystem. Imported files live under
`firmware/pocketbook-619/` and are excluded from Git. This profile supports
the original FT6336 touchscreen revision selected by hardware index 90.

The board loader supplies boot0's DRAM and package-loading handoff, then
executes the original U-Boot. The original kernel, display module and
applications run from an assembled eMMC image. The builder supplies the
hardware configuration, secure factory state and a generated waveform.
Bundled user content and fonts are installed on first boot. Automatic suspend
is disabled because SoC standby and its wakeup sources are not modeled.

Release 6.11.2022 bundles the Adobe fonts as regular files in its factory archive.
The builder extracts those files and refreshes the bundled ARM fontconfig v9
directory stamps for the prepared filesystems, preserving the stock font indexes.

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

Click or drag in the display to use the FT6336 touchscreen. Use the stock touch
controls: tap a side region to advance, a bottom corner above the page-number
bar to go back, the centre to open the reader menu, or the upper-left corner to
close the book. The physical Verse Lite has only a power button; navigation
follows its touch interface.

Support is experimental. USB data transfer, the power button and cover sensing
are not implemented. Use the serial console for a root shell.
