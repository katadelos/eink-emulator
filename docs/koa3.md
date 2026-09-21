# Kindle Oasis 3 (KOA3)

KOA3 is the 10th generation Oasis, board name Stinger. The emulator has touch
and page-button controls, 2 GiB of persistent storage, Wi-Fi and USB Ethernet.
It can occasionally exit during startup.

## Setup

Supply firmware **5.18.2.1.1** from
[Amazon's firmware page](https://www.amazon.com/gp/help/customer/display.html?nodeId=GKMQC26VQQMM8XSW)
and install the [host requirements](../README.md#host-requirements).
Replace `/path/to/` with the package location:

```sh
./eink import /path/to/update_kindle_all_new_oasis_v2_5.18.2.1.1.bin --model kindle-oasis-3
./eink create koa3 --model kindle-oasis-3
./eink run koa3
```

See [networking](networking.md) for Wi-Fi and SSH access.

## Controls

| Action | Control |
| --- | --- |
| Tap | Click the display |
| Previous page | `Page Up` or `[` |
| Next page | `Page Down` or `]` |
| Stop QEMU | Close the window |

The display does not reproduce frontlight brightness or colour temperature.
To save pending warmth settings before stopping, log in as `root` from serial
without a password and run:

```sh
sync
shutdown -r now
```

The launcher uses `-no-reboot`, so the guest reboot request exits QEMU.
