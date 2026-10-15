# Kobo Glo

The original Glo (Netronix E606B0) uses an i.MX507, 256 MiB RAM,
a 758 × 1024 display and an internal microSD card. Its Netronix hardware
configuration identifies the board as PCB 24.

## Firmware

Carve the original internal-card image with:

```sh
python3 scripts/carve-kobo.py /path/to/glo-sd.img --model kobo-glo
```

The utility also accepts a whole SD device. It opens the source read-only,
checks the hardware configuration and partition boundaries, and never reads
partition 3, the userstore. Existing destinations are not overwritten.

Artifacts are written to `firmware/kobo-glo/`:

| File | Source |
| --- | --- |
| `u-boot.bin` | Complete U-Boot prefix, including the DDR plug-in and main IVTs |
| `boot-region.img` | First 19,456 sectors (9.5 MiB), including hardware configuration, environment, kernel and waveform |
| `rootfs.img` | Partition 1: 524,289 sectors starting at sector 19,456 |
| `recoveryfs.img` | Partition 2: 524,289 sectors starting at sector 543,745 |

Partition boundaries come from the image's MBR. The captured firmware is
2.1.5, with Linux 2.6.35.3-850-gbc67621+ #604, built October 15, 2012.

## Create and run

```sh
./eink create glo --model kobo-glo
./eink run glo
```

The builder prepares a copy of the root filesystem and creates exactly
1 GiB of fresh FAT32 userstore at the original partition 3 offset. The
virtual SD card is 2 GiB, with the original boot, root and recovery offsets.
Remaining capacity is unpartitioned to satisfy QEMU's power-of-two SD
capacity requirement. The source image and captured firmware remain unchanged.

This firmware predates Kobo's `SideloadedMode` setting, so the model does
not accept `--sideloaded`. Creation retains the normal setup flow, but the
original 2012 online setup endpoint fails even after Wi-Fi association and
DHCP succeed. For offline use, follow the
[empty-account procedure](kobo-clara-hd.md#create-and-run) after booting once
to create the database on the fresh userstore. The utility supports this
firmware's account table.

USB telnet uses localhost port 2323, and serial accepts `root` without a
password. See [networking](networking.md) for port options when running
multiple readers. Click or drag for touch input; press `P` for power and
`F` for the frontlight button.

## Hardware model

`qemu/hw/arm/imx50-kobo-glo.c` defines the independent `imx50-kobo-glo`
machine. Internal storage uses eSDHC1, the external card slot uses eSDHC2,
and Broadcom BCM43362 Wi-Fi uses eSDHC3. Touch uses Neonode zForce v2;
the frontlight button connects through the i.MX keypad matrix.

Reference sources live under the ignored `glo-work/` directory. Both
checkouts use Git SSH and the `kobolabs/imx507` branch of
[linux-ereader](https://github.com/katadelos/linux-ereader/tree/kobolabs/imx507)
and [u-boot-ereader](https://github.com/katadelos/u-boot-ereader/tree/kobolabs/imx507).
The emulator uses captured firmware; neither source tree needs to be built.

Support is experimental. Firmware 2.1.5 boots to Nickel with portrait display,
touch input, the frontlight key, USB networking, and Wi-Fi association and
DHCP. Physical e-ink response, battery discharge and frontlight optics are
not reproduced.

The firmware enters deep idle after seven seconds without activity, even
while Home is visible. Touch wakes this idle state. To enter or leave the
visible Sleep Mode, hold `P` briefly (about 300–400 ms); longer holds request
power-off. The CPU enters the stock RAM-resident sleep routine with DDR in
self-refresh. Touch, USB networking and Wi-Fi work after power-key resume.

The virtual USB cable stays connected, and its host suspends the bus after
two seconds without traffic. USB traffic cannot wake deep suspend when the
guest disables USB wake interrupts; wake with `P` before connecting to
telnet. RTC alarm wake is not modeled.
