# Kobo Glo HD

The Glo HD (N437, Netronix E60Q9X) uses an i.MX6SL, 512 MiB RAM,
a 1072 × 1448 display and an internal microSD card. Its Netronix hardware
configuration identifies the board as PCB 46.

## Firmware

Carve the original internal-card image with:

```sh
python3 scripts/carve-kobo.py Kobo_N437_Glo_HD.img --model kobo-glo-hd
```

The utility also accepts a whole SD device. It opens the source read-only,
checks the hardware configuration and partition boundaries, and never reads
partition 3, the userstore. Existing destinations are not overwritten.

Artifacts are written to `firmware/kobo-glo-hd/`:

| File | Source |
| --- | --- |
| `u-boot.imx` | U-Boot image beginning at its IVT, extracted using the boot-data length |
| `boot-region.img` | First 30,720 sectors (15 MiB), including hardware configuration, environment, kernel and waveform |
| `rootfs.img` | Partition 1: 524,289 sectors starting at sector 30,720 |
| `recoveryfs.img` | Partition 2: 524,289 sectors starting at sector 555,010 |

This image labels partition 1 as FAT32 in the MBR even though it contains
an ext filesystem. The Glo HD profile accepts that partition type and
checks the filesystem signature before copying it.

## Create and run

```sh
./eink create glo-hd --model kobo-glo-hd
./eink run glo-hd
```

The supplied image contains firmware 3.14.0 and Linux 3.0.35+ #4063,
built February 26, 2015. It predates Kobo's `SideloadedMode` setting,
so this model does not accept `--sideloaded`.
For offline use, follow the [empty-account procedure](kobo-clara-hd.md#create-and-run)
after booting once to create the database on the fresh userstore.

The builder prepares a copy of the root filesystem and creates exactly
1 GiB of fresh FAT32 userstore. The virtual SD card is 2 GiB with the
original boot, root and recovery offsets. Remaining capacity is unpartitioned
to satisfy QEMU's power-of-two SD capacity requirement. The source image and
captured firmware remain unchanged.

Startup waits up to ten seconds for the battery driver's first capacity
reading before launching Nickel, avoiding a false empty-battery shutdown.

USB telnet uses localhost port 2323, and serial accepts `root` without a
password. See [networking](networking.md) for port options when running
multiple readers. Click or drag for touch input; press `P` for power.

## Hardware model

`qemu/hw/arm/imx6sl-kobo-glo-hd.c` defines the independent
`imx6sl-kobo-glo-hd` machine. Internal storage uses USDHC2 and Broadcom
BCM43362 Wi-Fi uses USDHC3. The board includes Neonode v3 infrared touch,
Ricoh619 power management, TPS65185 display power and a Netronix MSP430
frontlight controller.

Reference sources live under the ignored `kobo-glohd-work/` directory.
Both checkouts use Git SSH and the `kobolabs/imx6sl-glohd` branch of
[linux-ereader](https://github.com/katadelos/linux-ereader/tree/kobolabs/imx6sl-glohd)
and [u-boot-ereader](https://github.com/katadelos/u-boot-ereader/tree/kobolabs/imx6sl-glohd).
The emulator uses captured firmware; neither source tree needs to be built.

Support is experimental. Firmware 3.14.0 boots to Nickel's home screen
with portrait display, touch input, Wi-Fi association and DHCP, and USB
networking. Physical e-ink response, battery discharge and frontlight optics
are not reproduced.

Deep suspend keeps the virtual USB cable connected. The USB host suspends
the bus after two seconds without traffic and resumes it for networking
after the reader wakes. To sleep or wake Nickel, hold `P` briefly
(about 400 ms). Very short taps can be missed during resume, while longer
holds request power-off. RTC alarm wake is not modeled.
