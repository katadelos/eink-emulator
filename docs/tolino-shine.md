# Tolino Shine 5 and Shine Color

The `spa` firmware family uses the Kobo Clara BW and Clara Colour hardware
platforms. QEMU exposes Kobo board names; the CLI models prepare Tolino
firmware and identify themselves as Tolino through the hardware configuration.

| CLI model | QEMU machine | Update kernel | Hardware |
| --- | --- | --- | --- |
| `tolino-shine-5` | `mt8113-kobo-clara-bw` | `spa-bw/kernel.img` | E60T00, MT8113L, one Cortex-A53 |
| `tolino-shine-color` | `mt8113-kobo-clara-colour` | `spa-colour/kernel.img` | E60T00, MT8113T, two Cortex-A53 cores |
| `tolino-shine-5-tpv` | `mt8113-kobo-clara-bw-tpv` | `spa-tpv-bw/kernel.img` | E60V00, MT8113L, one Cortex-A53 |

All three use 512 MiB RAM and a 1072 × 1448 portrait display. Shine Color
uses a Kaleido 3 color filter. The TPV entry selects a hardware revision of
Shine 5, with different GPIO assignments and an LM3697 frontlight controller.
It is not a separate Tolino retail model.

Firmware 5.12.232736 boots Linux 4.9.77 and the stock Tolino setup interface
on all three boards.

## Firmware

Install `zstd` alongside the [host requirements](../README.md#host-requirements).
`--firmware` downloads a pinned release from Kobo's CDN and imports it; see
[downloads](firmware.md#download-a-firmware-version):

```sh
./eink versions --model tolino-shine-5
./eink create shine-5 --model tolino-shine-5 --firmware 5.12.232736
./eink run shine-5
```

For the color model:

```sh
./eink create shine-color --model tolino-shine-color --firmware 5.12.232736
./eink run shine-color
```

Use `tolino-shine-5-tpv` and an instance name such as `shine-5-tpv` for the
TPV revision. One update contains all three kernels. The selected model
determines which kernel is imported; U-Boot, BL2, TEE and rootfs are shared.

To use a file you already have, import it into `firmware/MODEL/` and create
without `--firmware`:

```sh
./eink import /path/to/update.tar --model tolino-shine-5
./eink create shine-5 --model tolino-shine-5
```

The importer accepts the update tar, Kobo's zip-wrapped update or an
extracted update directory, and checks each file against the update's
`sha2-256sums`. It refuses to overwrite an existing firmware directory.

## Controls and networking

Click to tap. These boards have no page-turn buttons. Serial accepts `root`
without a password. USB SSH starts automatically and uses the local login key:

```sh
ssh -i build/ssh/id_ed25519 -p 2222 root@127.0.0.1
```

The stock OpenSSH server also provides SFTP. Select `Kindle-QEMU` in the
guest to connect Wi-Fi; SSH is then available on port 2223. The emulated Wi-Fi
firmware reports the virtual NIC's MAC address through the V2 capability
interface, satisfying the stock driver's permanent identity check. See
[networking](networking.md) for port options and file transfer.

## Storage and limitations

Support is experimental. The builder prepares a 4 GiB development disk with
the stock partition numbering, a modified copy of the update rootfs, synthetic
hardware configuration, an empty Netronix calibration container and a waveform
fixture. Imported firmware stays unchanged. The prepared rootfs enables serial
and keyed SSH access. The stock WMT and Wi-Fi kernel modules run unmodified
against the emulated connectivity hardware, as on
[Vision Color](tolino-vision-color.md).

The update omits factory calibration and recovery data. Factory reset is
unavailable and frontlight brightness tables are absent. On Shine Color, the
prepared display startup selects the stock driver's built-in `NTX_SF` conversion. Emulated
colors are approximate. Bluetooth, physical ghosting, frontlight optics,
other firmware versions and OTA updates are unverified.

## Hardware references

Kobo's [Clara BW / Shine 5 sources](https://github.com/kobolabs/Kobo-Reader/blob/master/hw/mt8113-claraBW_shine5BW)
and [Clara Colour / Shine Color sources](https://github.com/kobolabs/Kobo-Reader/blob/master/hw/mt8113-claraC_shine5C)
point to the shared
[MT8113 U-Boot and Linux source bundle](https://github.com/kobolabs/Kobo-Reader/tree/master/hw/mt8113-libraC_vision7).
The E60T00 device trees describe the original SPA boards. The TPV E60V00
wiring comes from the `spa-tpv-bw` kernel's device tree in the official update;
that revision is absent from the published source bundle.

The update's `driver.sh` selects `spa-tpv-bw` for PCB `0xA0` / `E60V00`.
The stock rootfs detects that PCB as `spaTolinoBW`, while E60T00 selects
`spaTolinoBW` or `spaTolinoColour` according to its CFA flag.
RAM and CPU configurations follow the
[Shine 5](https://mytolino.de/produkte/tolino-shine/) and
[Shine Color](https://mytolino.de/produkte/tolino-shine-color/) specifications
and shipped device trees. QEMU enters U-Boot after the BL2 handoff; Boot ROM
and DRAM training are not emulated.
