# Kindle Scribe 1

Barolo uses the `mt8113-bellatrix3` machine with `board=barolo` and 1 GiB
RAM. It shares the Bellatrix3 platform with [Scribe 2](scribe-2.md).
Home, touch and suspend still need testing with the standard images.

## Setup

Install KindleTool and e2fsprogs, then import a recovery package:

```sh
./eink import /path/to/update.bin --model kindle-scribe-1
./eink create my-scribe --model kindle-scribe-1 --profile dvt
./eink run my-scribe
```

Profiles are `production` (DVT), `dvt`, `evt`, `evt-doe`, `hvt`, `hvt-a`
and `proto` (Proto2). QEMU supplies the board identity.

The importer saves the boot images and decompressed rootfs in
`firmware/kindle-scribe-1`. Images use the original kernel and device tree.
Stock SBIOS storage requests can time out when the host delays execution.

## Display and storage

The builder creates an 8 GiB sparse disk with a prepared rootfs and fresh
persistent filesystems. See the [partition layout](storage.md#scribe-partitions).
The imported firmware files are kept intact.

The builder generates a synthetic HWTCON v2 waveform. The display job loads
the original HWTCON module with that waveform, unless the module is already
running. Synthetic waveforms enable
emulated display updates; they do not reproduce a physical panel's response.

## Guest setup

The generated rootfs provides a serial shell and SSH over USB Ethernet and Wi-Fi.
Serial opens in the launching terminal. Use `--serial-socket` to redirect
it to the instance's Unix socket and log file.

```sh
ssh -i build/ssh/id_ed25519 -p 2222 root@127.0.0.1
```

Use `--ssh-port PORT` to change the USB host port, or `--wifi-ssh-port PORT`
for Wi-Fi (default 2223). MTP is disabled so it does
not take over the USB controller. Native Wi-Fi connects to the open
`Kindle-QEMU` AP; see [networking](networking.md).

On first boot, the guest skips initial setup (OOBE), selects British English,
and sets the device type needed for the DVT board. It backs up existing
preferences and leaves later user choices alone. No Amazon account is created.

Shared directory permissions are set before services start, avoiding repeated
recursive changes during framework restarts. The guest stays awake for up
to two hours while its display is active; the power button still allows sleep.
The framework gets 600 seconds to start. Java settings remain unchanged.
See [guest setup details](../guest-overrides/bellatrix3/README.md).
