# PocketBook Verse Pro Color (634K3)

The Verse Pro Color uses an Allwinner B300 (`sun8iw15p1`), four Cortex-A7 cores,
1 GiB RAM and a 1072 × 1448 Kaleido 3 display.

## Firmware

Import the official 6.10.2544 update ZIP, or its extracted `SWUPDATE.BIN`:

```sh
./eink import /path/to/sw_20251201_U634k3_6.10.2544_user.zip --model pocketbook-634k3
./eink create pb634k3 --model pocketbook-634k3
./eink run pb634k3
```

The [official update](https://download.pocketbook-int.com/fw/Yitoa/634k3/user/20251201/sw_20251201_U634k3_6.10.2544_user.zip)
contains the vendor U-Boot/OP-TEE package, Linux 4.9.56 kernel, root filesystem,
applications and recovery filesystem. Imported files live under
`firmware/pocketbook-634k3/` and are excluded from Git. Hardware index 88 selects
the original FocalTech touchscreen revision.

The board loader supplies boot0's DRAM and package-loading handoff, then executes
the original boot chain. The original kernel, display module and applications
run from a 2 GiB eMMC image with the native GPT partition numbering and an ext2
boot volume for U-Boot's `ext4load` command. The builder
supplies hardware configuration, secure factory state and a generated AWF
waveform in `/boot/default.awf`. The applications partition is 511 MiB and the
user volume is approximately 1.25 GiB.

Bundled user content and Adobe fonts are installed on first boot. The bundled
ARM fontconfig v8 indexes retain their contents with directory stamps adjusted
for the prepared filesystems. Automatic suspend is disabled because SoC standby
and its wakeup sources are not modeled.

The prepared startup omits automatic loading of the Mali module. The stock
interface uses CPU rendering; Mali 3D acceleration is not emulated.

The prepared IOC library uses its unprovisioned identity when the factory record
is absent. The monitor supplies a local non-contract configuration only after
a failed native read for that blank identity. This emulator default is not a
vendor-signed factory record. Valid configuration reads and signature checks
for writes retain their original behavior. Failed read headers are initialized
so the stock monitor's cache cannot copy an uninitialized length. Imported
firmware remains unchanged; preparation applies to this model's image.

Complete setup with the stock wizard and use Skip at account screens for local
reading. Manufacturer account and device enrolment services are not emulated.

## Display

The native application library converts RGB content into individual Kaleido 3
filter pixels. The EINK engine constructs 32-level transition indexes and
decodes pipeline waveforms into electrical drive buffers. The index engine,
decoder and EDMA use their separate IOMMU translation contexts. EDMA and TCON
scan those buffers to update the retained panel image. The emulator interpolates
nearby red, green and blue samples from the native filter pattern.

The generated waveform uses uniform steps between gray levels, with neutral
frames for the native index handoff and final TCON drain. Physical waveform
calibration, filter transmission and the panel's measured color gamut are not
reproduced.

## Network

Wi-Fi uses the AIC8800 SDIO model with the stock vendor drivers. See
[networking](networking.md#pocketbook-wi-fi) for addresses and limits.

## Input

Click or drag in the display to use the FocalTech touchscreen. Page Up / Page Down,
or Left / Right, operate the page buttons. Home operates the home button.

Support is experimental. Bluetooth, audio, USB data transfer, the power button,
cover sensing, the orientation sensor and SoC standby are not implemented.
Use the serial console for a root shell. Recovery and firmware updates are
unverified.
