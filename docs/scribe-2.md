# Kindle Scribe 2

Pisco uses `mt8113-bellatrix3,board=pisco` with 1 GiB RAM. Its image layout
and guest setup are shared with [Scribe 1](scribe-1.md). Home, touch and
suspend still need testing with the standard images.

## Setup

Install KindleTool and e2fsprogs, then import a recovery package:

```sh
./eink import /path/to/update.bin --model kindle-scribe-2
./eink create my-scribe-2 --model kindle-scribe-2 --profile dvt
./eink run my-scribe-2
```

Profiles are `production` and `dvt`; both select the DVT hardware. QEMU
supplies the board identity.

Firmware is stored in `firmware/kindle-scribe-2`. Images use the original
kernel and device tree. Stock SBIOS storage requests can time out when the
host delays execution.

## Guest behavior

The image includes a serial shell, USB Ethernet/telnet, initial setup skip,
British English locale, permission fixes and a two-hour keep-awake job.
Java settings remain unchanged. The device-type override accounts for the
DVT board ID missing from the firmware's production lookup table.

Serial opens in the launching terminal. `--serial-socket` redirects it to
a Unix socket and log file. Telnet is available at `127.0.0.1:2323`; change
the host port with `--telnet-port PORT`. Native Wi-Fi is not available.

The builder uses `firmware/kindle-scribe-2/waveform.img` when supplied,
or generates a synthetic waveform. See [Scribe 1](scribe-1.md) for display
setup and [storage](storage.md#scribe-partitions) for the partition layout.
