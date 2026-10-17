# Tolino Vision Color

Tolino Vision Color uses the Kobo Libra Colour hardware platform: Netronix
E70T04, MediaTek MT8113, two Cortex-A53 cores, 1 GiB RAM and a 1680 × 1264
panel. The CLI model is `tolino-vision-color`; the shared QEMU machine is
`mt8113-kobo-libra-colour`.

Support is experimental. The firmware input is the Tolino update, including
its root filesystem, U-Boot FIT and `monza` kernel FIT. A prepared rootfs copy
contains the emulator's guest configuration; imported files stay unchanged.
Firmware 5.12.232736 boots Linux 4.9.77 and the stock Tolino setup interface.

## Firmware

Install `zstd` alongside the [host requirements](../README.md#host-requirements).
`--firmware` downloads a pinned release from Kobo's CDN and imports it; see
[downloads](firmware.md#download-a-firmware-version):

```sh
./eink create vision-color --model tolino-vision-color --firmware 5.12.232736
```

To use an update you already have, import it instead, then create without
`--firmware`:

```sh
./eink import /path/to/update --model tolino-vision-color
```

The importer accepts an extracted update directory, the update tar or Kobo's
zip-wrapped update, and checks each file against the update's `sha2-256sums`.
It selects these components and decompresses them into
`firmware/tolino-vision-color/`:

| Update component | Imported file |
| --- | --- |
| `uboot.img` | `uboot.img` |
| `monza/kernel.img` | `kernel.img` |
| `rootfs.img` | `rootfs.img` |
| `bl2.img` | `bl2.img` |
| `tee.img` | `tee.img` |

The `spa-*` kernels belong to [Shine 5 / Shine Color](tolino-shine.md).
Use the `monza` kernel for Vision Color. Import refuses to overwrite an
existing firmware directory.

## Create and run

```sh
./eink create vision-color --model tolino-vision-color
./eink run vision-color
```

Click to tap. `Page Up` / `Left` and `Page Down` / `Right` operate the page
buttons. The display and touch coordinates use the firmware's portrait
orientation.

For a serial log and QMP control:

```sh
./eink run vision-color --headless --serial-socket --qmp-socket
```

Serial accepts `root` without a password. USB SSH uses the shared local key:

```sh
ssh -i build/ssh/id_ed25519 -p 2222 root@127.0.0.1
```

The stock OpenSSH server accepts the prepared public key and provides SFTP.
Use `--ssh-port PORT` to change the host port. Select `Kindle-QEMU` in the
guest for Wi-Fi; SSH is then also available on port 2223. The emulated Wi-Fi
firmware reports the virtual NIC's MAC address through the driver's V2
capability interface, providing the permanent identity required by the
stock driver without factory Wi-Fi NVRAM.

The stock WMT and Wi-Fi kernel modules run unmodified against the emulated
connectivity power, bus-protection and firmware interfaces.

## Storage and display

The builder creates a 4 GiB disk with system, recovery and user partitions at
the numbers expected by the firmware. It supplies a synthetic hardware
configuration, an empty Netronix calibration table and a waveform fixture.
The recovery slot is empty because the supplied update has no recovery image;
factory reset is unavailable.

The prepared display startup selects the stock driver's `NTX_SF` conversion.
This lets the CFA display pipeline operate without the factory `cfa_lut.gz`.
QEMU reconstructs color from the panel's documented filter pattern. Colors are
approximate; factory color calibration, physical ghosting and frontlight
optics are not reproduced. The update also lacks the factory frontlight
brightness tables. Bluetooth, stylus input, other firmware versions and OTA
updates are unverified.

## Hardware reference

[Kobo's shared Libra Colour / Vision 7 sources](https://github.com/kobolabs/Kobo-Reader/tree/master/hw/mt8113-libraC_vision7)
contain `bootloader.tar.zst` and the split `kernel.tar.zst.part-aa` /
`kernel.tar.zst.part-ab` archive. The board model follows the MT8113 U-Boot
handoff and E70T04 hardware description from those sources. The emulator
enters U-Boot after the BL2 handoff; it does not emulate the Boot ROM or DRAM
training.
