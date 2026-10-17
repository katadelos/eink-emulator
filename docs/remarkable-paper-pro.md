# reMarkable Paper Pro

The Ferrari board uses the shared i.MX8M Mini SoC with four Cortex-A53
cores, 2 GiB RAM and a 64 GiB eMMC. Its QEMU machine is
`imx8mm-remarkable-paper-pro`. The board connects the Cumulus display
bridge, ELAN SPI pen and touch controller, LPC804 hardware monitor,
LIS2DW12 orientation sensor and power-management devices.

## Firmware

```sh
./eink import /path/to/remarkable-production-image-3.27.1.0-ferrari-public.swu --model remarkable-paper-pro
./eink create paperpro --model remarkable-paper-pro
./eink run paperpro
```

The [3.27.1.0 package](https://remarkable-software.s3.us-east-2.amazonaws.com/remarkable-production-image-3.27.1.0-ferrari-public.swu)
contains the vendor `imx-boot` package, Linux 6.12.49, device trees,
Xochitl and peripheral firmware. The importer extracts the boot package,
root filesystem and hardware-monitor firmware without running the update
scripts. It also creates a synthetic factory image. These files belong in
`firmware/remarkable-paper-pro/` and are excluded from Git.

Vendor sources are available for
[U-Boot](https://github.com/reMarkable/uboot-imx-rm/tree/rmpp_2025.05_v3.27.x)
and [Linux](https://github.com/reMarkable/linux-imx-rm/tree/rmpp_6.12.49_v3.27.x).
GnuTLS development files are required to build this machine.

The original SPL, TF-A, OP-TEE and U-Boot load the original kernel and
device tree. Prepared images change system configuration; the firmware
executables and trusted applications are not patched.

## Interface and input

Prepared images open at **My files** for offline notebook use. The native
setup flag is `[General] Setup=false` in `/data/xochitl.conf`.
The user's `SetupState` setting selects an onboarding page independently
of that flag. Notebooks and user settings persist in the instance disk.

The pointer starts in pen mode. Left-click or drag to tap and write.
`T` selects finger input; `P` returns to the pen. Mouse input supplies
fixed pressure and zero tilt. Use the notebook toolbar for other writing
tools and the eraser. QEMU's Power key operates the SNVS power button to
sleep and wake the tablet. Native idle autosuspend and automatic light
sleep are enabled. RTC alarms can wake the suspended guest; the panel
retains its image during suspend.

Xochitl drives the native DRM/LCDIF pipeline and Cumulus FPGA interface.
The panel decodes eight three-bit source-driver lanes as four columns
with alternating upper/lower rows, producing a 1620 × 2160 portrait
display. Pigment travel is retained separately from visible reflectance.

## Storage and serial

The eMMC is attached to USDHC1. Its GPT contains a 32 MiB data partition,
two 640 MiB system slots, a 1536 MiB swap partition and a home partition.
The boot partitions are reconstructed from `imx-boot` and `factory.img`
at launch. Factory provisioning represents an unfused, unlocked device.

Home uses plain ext4. The native keystore and TEE supplicant remain
enabled; trusted applications store their files on the data partition.
CAAM provides RNG, hashing, AES, ECC key generation, manufacturing-key
regeneration and emulated sealed key storage. Its key derivation and
wrapping are specific to the emulator and are not compatible with
physical-device keys or key blobs.

The serial console logs in as root automatically. `--serial-socket`
provides a socket and log; otherwise use the launching terminal.
Prepared images disable encrypted home/swap setup and network socket
activation.

Support is experimental. Display output is grayscale; Gallery 3 color
reproduction is not implemented. Analog pigment response and ghosting
are approximations. Wi-Fi, USB networking, cloud services, the NFC marker
charger, disk hibernation and firmware updates are not implemented.
Recovery paths are unverified.
