# Kindle Oasis 1 and 2

Both Oasis models have touch and page-button controls, 2 GiB of persistent
storage, Wi-Fi and USB Ethernet.

## Setup

Supply firmware **5.16.2.1.1** for your model from
[Amazon's firmware page](https://www.amazon.com/gp/help/customer/display.html?nodeId=GKMQC26VQQMM8XSW)
and install the [host requirements](../README.md#host-requirements).
Replace `/path/to/` with the package location.

### Oasis 1 (8th generation)

```sh
./eink import /path/to/update_kindle_oasis_5.16.2.1.1.bin --model kindle-oasis-1
./eink create oasis-1 --model kindle-oasis-1
./eink run oasis-1
```

### Oasis 2 (9th generation)

```sh
./eink import /path/to/update_kindle_all_new_oasis_5.16.2.1.1.bin --model kindle-oasis-2
./eink create oasis-2 --model kindle-oasis-2
./eink run oasis-2
```

Instances skip initial setup and open Home without an Amazon account.
See [networking](networking.md) for Wi-Fi and SSH access.

## Controls

| Action | Control |
| --- | --- |
| Tap | Click the display |
| Previous page | `Page Up` or `[` |
| Next page | `Page Down` or `]` |
| Stop QEMU | Close the window |
