# PocketBook InkPad Color 3 (743K3)

The InkPad Color 3 uses an Allwinner B300 (`sun8iw15p1`), four Cortex-A7 cores,
1 GiB RAM and a 1404 × 1872 Kaleido 3 display. Black-and-white content uses
the full panel resolution; color content has a 468 × 624 effective resolution.

## Firmware

Import the official 6.10.2854 update ZIP, or its extracted `SWUPDATE.BIN`:

```sh
./eink import /path/to/sw_20260105_U743k3_6.10.2854_user.zip --model pocketbook-743k3
./eink create pb743k3 --model pocketbook-743k3
./eink run pb743k3
```

The [official update](https://download.pocketbook-int.com/fw/Yitoa/743k3/user/20260105/sw_20260105_U743k3_6.10.2854_user.zip)
contains the vendor Sunxi boot package, Linux 4.9.56 kernel, root filesystem,
application filesystem and recovery filesystem. Imported files live under
`firmware/pocketbook-743k3/` and are excluded from Git. The vendor publishes
[B300 U-Boot sources](https://github.com/pocketbook/uboot-b300) and
[kernel sources](https://github.com/pocketbook/kernel-b300).

The board loader supplies boot0's DRAM and eMMC calibration handoff, including
the SCP images and board configuration, then executes the original OP-TEE and
U-Boot. The original kernel, display module and applications use an assembled
GPT/eMMC image. The builder supplies hardware configuration, factory state,
font caches and a generated neutral `default.awf` waveform named `B300K3`. Automatic
suspend and Mali module loading are disabled because SoC standby, its wakeup
sources and the separate 3D GPU are not modeled. The native CPU and EINK
rendering path remains in use.

The prepared image adjusts the 6.10.2854 IOC library's factory-record check to
use its unprovisioned identity. The update excludes the physical device's
factory record. For this blank identity, a failed configuration read supplies
a local partner configuration with contract and lock flags set to zero. It
also clears the monitor's reply header before caching it. Valid records and
signed writes retain their stock behavior. Imported firmware remains unchanged;
these adjustments apply only when building this model's image.

## Display

The native application library converts RGB content into individual Kaleido 3
filter pixels. The EINK engine constructs 32-level transition indexes and
decodes pipeline waveforms into electrical drive buffers. EDMA and TCON scan
those buffers to update the retained panel image. The emulator interpolates
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

Click or drag in the display to use the Parade touchscreen. Page Up / Page Down,
or Left / Right, operate the page buttons. Home operates the home button.

Support is experimental. Bluetooth, audio, USB data transfer, the power button,
cover sensing, the orientation sensor and SoC standby are not implemented. Use
the serial console for a root shell. Recovery and firmware updates are unverified.
