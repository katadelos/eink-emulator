# Kobo Aura HD

The Aura HD (N204B, Netronix E606C0) uses an i.MX507, 512 MiB RAM,
a 1080 × 1440 display and an internal microSD card. Its Netronix hardware
configuration identifies the board as PCB 28.

## Firmware

Carve the original internal-card image with:

```sh
python3 scripts/carve-kobo.py Kobo_N204B_Aura_HD.img --model kobo-aura-hd
```

The same utility accepts a whole SD device. It reads the MBR and hardware
configuration to identify the model and partition boundaries, opens the
source read-only, and never reads partition 3, the userstore. The optional
`--model` argument checks the detected identity; `--output` selects a
destination. Existing destinations are not overwritten.

The Aura HD artifacts are written to `firmware/kobo-aura-hd/`:

| File | Source |
| --- | --- |
| `u-boot.bin` | U-Boot prefix and complete image, including its DDR plug-in and main IVTs |
| `boot-region.img` | First 19,456 sectors (9.5 MiB), including hardware configuration, environment, kernel and waveform |
| `rootfs.img` | Partition 1: 524,289 sectors starting at sector 19,456 |
| `recoveryfs.img` | Partition 2: 524,289 sectors starting at sector 543,745 |

The carver supports Aura HD, Glo HD and Clara HD. Partition offsets come from the
image's MBR; the model profile validates the hardware identity and boot format.

## Create and run

```sh
./eink create aura-hd --model kobo-aura-hd
./eink run aura-hd
```

The supplied image contains firmware 4.38.21908 and Linux
2.6.35.3-850-gbc67621+. To skip account setup and use Kobo's offline mode,
create the instance with `--sideloaded`:

```sh
./eink create aura-hd --model kobo-aura-hd --sideloaded
```

This initializes `SideloadedMode=true` on the fresh userstore before Nickel
starts. The default creation command retains the normal setup flow.

The builder prepares a copy of the root filesystem and creates a fresh,
exactly 1 GiB FAT32 userstore. The virtual SD card is 2 GiB with its original
boot, root and recovery offsets; remaining capacity is unpartitioned to meet
QEMU's power-of-two SD capacity requirement. The source image and captured
firmware remain unchanged.

USB telnet uses localhost port 2323, and serial accepts `root` without a
password. See [networking](networking.md) for port options when running
multiple readers. Click or drag for touch input; press `P` for power and
`F` for the frontlight button.

## Hardware model

`qemu/hw/arm/imx50-kobo-aura-hd.c` defines the independent
`imx50-kobo-aura-hd` machine. Internal storage uses eSDHC3, and Wi-Fi uses
eSDHC2. The board includes MC13892 power management on SPI3, TPS65185 display
power, a Netronix MSP430 controller and zForce v2 infrared touch.

Hardware references use the `kobolabs/imx507-aurahd` branch of
[linux-ereader](https://github.com/katadelos/linux-ereader/tree/kobolabs/imx507-aurahd)
and [u-boot-ereader](https://github.com/katadelos/u-boot-ereader/tree/kobolabs/imx507-aurahd).
The emulator uses captured firmware; neither source tree needs to be built.

Support is experimental. The captured firmware boots to Nickel with touch
input, Wi-Fi association and DHCP, and USB networking. Physical e-ink
response, battery discharge and frontlight optics are not reproduced.

Deep suspend keeps the virtual USB cable connected. The USB host suspends
the bus after two seconds without traffic and resumes it for networking
after the reader wakes. To sleep or wake Nickel, hold `P` briefly
(about 400 ms). Very short taps can be missed during resume, while longer
holds request power-off. RTC alarm wake is not modeled.
