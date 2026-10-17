# PocketBook Touch Lux 4 (627)

The Touch Lux 4 uses an Allwinner A13 (`sun5i`), one Cortex-A8 core,
512 MiB RAM and a 758 × 1024 monochrome display.

## Firmware

Import the official 6.5.2898 update ZIP, or its extracted `SWUPDATE.BIN`:

```sh
./eink import /path/to/sw_20220720_U627_6.5.2898_user.zip --model pocketbook-627
./eink create pb627 --model pocketbook-627
./eink run pb627
```

The [official update](https://download.pocketbook-int.com/fw/Yitoa/627/user/20220720/sw_20220720_U627_6.5.2898_user.zip)
contains the vendor Linux 3.0.8 kernel, root filesystem, applications and recovery
filesystem. Imported files live under `firmware/pocketbook-627/` and are excluded
from Git. This profile selects the original Elan XH7 touchscreen with hardware
index 30. The vendor publishes the [A13 platform sources](https://github.com/pocketbook/Platform_A13).

The update omits U-Boot. The board loads the original uncompressed ARM `Image`
at its native entry address and supplies the expected machine ID, ATAGS and
Sunxi hardware configuration. The original kernel, display module and
applications run from an assembled 2 GiB internal SD image. Its DOS partition
numbers match the stock startup script and filesystem table. The original IOC
library and monitor use their native empty-serial factory identity; the builder
seeds its matching secure factory state.

The generated waveform supplies grayscale transitions for the emulated panel
through the native software EPDC and display DMA pipeline. Bundled user content
and fonts are installed on first boot, with the original ARM fontconfig indexes
matched to the prepared filesystems. Automatic suspend is disabled because SoC
standby and its wakeup sources are not modeled.

## Network

Wi-Fi uses the internal RTL8188EU USB adapter with the stock Realtek driver.
Select the open `Kindle-QEMU` access point in the guest to connect through QEMU
user networking. See [networking](networking.md#pocketbook-wi-fi) for addresses
and limits.

## Input

Click or drag in the display to use the Elan touchscreen. Page Up / Page Down,
or Left / Right, operate the page buttons. Home operates the home button;
Enter, Escape, Backspace or Menu operates the menu button.

Support is experimental. USB data transfer, the power button, cover sensing
and external microSD storage are not implemented. Use the serial console for a
root shell. Recovery and firmware updates are unverified.
