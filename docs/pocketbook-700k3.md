# PocketBook Era Color (700K3)

The Era Color uses an Allwinner B300 (`sun8iw15p1`), four Cortex-A7 cores,
1 GiB RAM and a 1264 × 1680 Kaleido 3 display. The native panel orientation is
portrait.

## Firmware

Import the official 6.10.2359 update ZIP, or its extracted `SWUPDATE.BIN`:

```sh
./eink import /path/to/sw_20251113_U700k3_6.10.2359_user.zip --model pocketbook-700k3
./eink create pb700k3 --model pocketbook-700k3
./eink run pb700k3
```

The [official update](https://download.pocketbook-int.com/fw/Jezetek/700k3/user/20251113/sw_20251113_U700k3_6.10.2359_user.zip)
contains the vendor Sunxi boot package, Linux 4.9.56 kernel, root filesystem,
application filesystem and recovery filesystem. Imported files live under
`firmware/pocketbook-700k3/` and are excluded from Git. The vendor publishes
[B300 U-Boot sources](https://github.com/pocketbook/uboot-b300) and
[kernel sources](https://github.com/pocketbook/kernel-b300).

The board loader supplies boot0's DRAM and package handoff, including the SCP
images and board configuration, then executes the original OP-TEE and U-Boot.
The original kernel, display module and applications use an assembled GPT/eMMC
image. The builder supplies hardware configuration, factory state, font caches
and a generated AWF waveform named `B300K3` in `/boot/default.awf`. Automatic
suspend is disabled because SoC standby and its wakeup sources are not modeled.

The prepared image adjusts the 6.10.2359 IOC library's factory-record check to
use its unprovisioned identity. The update excludes the physical device's
factory record. For this blank identity, a failed configuration read supplies
a local partner configuration with contract and lock flags set to zero. It
also clears the monitor's reply header before caching it. Valid records and
signed writes retain their stock behavior. The monitor's preparation preserves
its virtual addresses while adding file padding for the local configuration
provider. Imported firmware remains unchanged; these adjustments apply only
when building this model's image.

## Display

The native application library converts RGB content into individual Kaleido 3
filter pixels. The EINK engine constructs 32-level transition indexes and
decodes pipeline waveforms into electrical drive buffers. The index engine,
decoder and EDMA use their separate IOMMU translation contexts. EDMA and TCON
scan those buffers to update the retained panel image. The emulator interpolates
nearby red, green and blue samples from the native three-column, three-row
filter pattern.

The generated waveform uses uniform steps between gray levels, with neutral
frames for the native index handoff and final TCON drain. Physical waveform
calibration, filter transmission and the panel's measured color gamut are not
reproduced.

## Network

Wi-Fi uses the AIC8800 SDIO model with the stock BSP and FullMAC drivers. Select
the open `PocketBook-QEMU` access point in the guest to connect through QEMU
user networking. See [networking](networking.md#pocketbook-wi-fi) for addresses
and limits.

## Input

Click or drag in the display to use the FocalTech FT3518 touchscreen. Page Up /
Page Down, or Left / Right, operate the page buttons. Home operates the home
button.

Support is experimental. The prepared startup omits the optional `mali.ko`
autoload because 3D acceleration is unsupported. Bluetooth, audio, USB data
transfer, the power button, cover sensing, the orientation sensor and SoC standby
are not implemented. Use the serial console for a root shell. Recovery and
firmware updates are unverified.
