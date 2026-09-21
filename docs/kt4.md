# Kindle Basic 4 (2019)

KT4 is the 10th generation basic Kindle, board name Jaeger. The emulator has
touch controls, 2 GiB of persistent storage, Wi-Fi and USB Ethernet.

## Setup

Supply firmware **5.18.1.1.1** from
[Amazon's firmware page](https://www.amazon.com/gp/help/customer/display.html?nodeId=GKMQC26VQQMM8XSW)
and install the [host requirements](../README.md#host-requirements).
Replace `/path/to/` with the package location:

```sh
./eink import /path/to/update_kindle_10th_5.18.1.1.1.bin --model kindle-kt4
./eink create kt4 --model kindle-kt4
./eink run kt4
```

See [networking](networking.md) for Wi-Fi and SSH access.

## Controls

On macOS, click the display to tap and close the window to stop QEMU.
KT4 has no physical page buttons.
