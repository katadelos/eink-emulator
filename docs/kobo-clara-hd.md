# Kobo Clara HD

The Clara HD (N249, Netronix E60K02) uses an i.MX6SLL, 512 MiB RAM,
a 1072 × 1448 display and an internal microSD card. Its Netronix hardware
configuration identifies the board as PCB 74 (E60K00).

## Firmware

The capture utility reads the boot area and the two Linux partitions. It
opens the card read-only and never reads partition 3, the userstore.
Identify the whole SD device with `diskutil list` on macOS, then run:

```sh
sudo python3 scripts/capture-clara-hd.py /dev/rdiskN
```

Replace `/dev/rdiskN` with the card's device. The script checks the Clara HD
hardware identity and partition layout, and refuses to replace an existing
firmware directory. It produces these files in `firmware/kobo-clara-hd/`:

| File | Source |
| --- | --- |
| `u-boot.imx` | U-Boot image extracted from sector 2 using its IVT and boot-data length |
| `boot-region.img` | First 49,152 sectors (24 MiB), including kernel, DTB, waveform and hardware configuration |
| `rootfs.img` | Partition 1: 524,289 sectors starting at sector 49,152 |
| `recoveryfs.img` | Partition 2: 524,289 sectors starting at sector 573,441 |

No separate userstore image is required or accepted by the builder.

## Create and run

```sh
./eink create clara-hd --model kobo-clara-hd
./eink run clara-hd
```

The captured firmware is 4.28.18220 with Linux 4.1.15 and starts at Kobo's
setup screen. It predates Kobo's `SideloadedMode` setting, so this model does
not accept `--sideloaded`. The builder repairs and adapts a copy of the root
filesystem, preserving the captured files.

For offline use on this firmware, boot once to create
`.kobo/KoboReader.sqlite` on the fresh userstore, then stop Nickel and its
watchdog before copying the database to the host. Keep any SQLite WAL file
with it until SQLite has checkpointed the database. Add a local account:

```sh
python3 scripts/kobo-empty-account.py /path/to/KoboReader.sqlite
```

Copy the database back while Nickel is stopped and restart the guest.
The utility refuses databases that already contain an account. The local
account uses `offline` as its ID, with empty name, email, key and device ID;
Nickel requires a nonempty ID to recognize an account. This skips account
setup without registration or credentials.

The virtual SD card is 2 GiB, with the original boot, root and recovery
offsets. Partition 3 is exactly 1 GiB (1,073,741,824 bytes) of fresh FAT32
storage. The remaining capacity is unpartitioned because QEMU's SD model
requires a power-of-two card size. The original userstore is not copied.

Serial accepts `root` without a password. USB telnet uses localhost port
2323; see [networking](networking.md). Click or drag for touch input, and
press `P` for the power button.

## Hardware model

The independent board implementation is
`qemu/hw/arm/imx6sll-kobo-clara-hd.c`, exposed as `imx6sll-kobo-clara-hd`.
Internal storage connects to USDHC2;
RTL8189FS Wi-Fi connects to USDHC3. The I2C devices include Ricoh619 power
management, TPS65185 display power, CYTTSP5 touch and LM3630A frontlight control.

Linux and U-Boot source references live in the ignored `clarahd-work/`
directory. Both checkouts use SSH remotes and the `kobolabs/imx6sll-clara`
source branch from [linux-ereader](https://github.com/katadelos/linux-ereader/tree/kobolabs/imx6sll-clara)
and [u-boot-ereader](https://github.com/katadelos/u-boot-ereader/tree/kobolabs/imx6sll-clara).
They are hardware references; running the emulator uses the captured
firmware and does not require building either source tree.

Support is experimental. Firmware 4.28.18220 boots through U-Boot to Nickel's
home screen; touch, USB networking and RTL8189FS association, DHCP and packet
traffic are supported. Display scanout uses this kernel's framebuffer address
and stride; other firmware versions are unverified. Physical e-ink response,
battery discharge and frontlight optics are not reproduced.
