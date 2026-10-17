# PocketBook Basic 611

The Basic 611 uses a Netronix i.MX50 board with 128 MiB RAM, a 600 × 800
monochrome display and physical navigation buttons. It has no touchscreen or
frontlight.

## Firmware

Import the official 16.0.239 update ZIP, or its extracted `SWUPDATE.BIN`:

```sh
./eink import /path/to/sw_20130205_611_EURO_us_br_16.0_611_239_user.zip --model pocketbook-611
./eink create pb611 --model pocketbook-611
./eink run pb611
```

The [official package](https://download.pocketbook-int.com/fw/netronix/611/user/sw_20130205_611_EURO_us_br_16.0_611_239_user.zip)
contains the original U-Boot, Linux 2.6.35.3 kernel, root filesystem and
application filesystem. Imported firmware belongs under `firmware/pocketbook-611/`
and is excluded from Git.

The vendor-published
[Netronix i.MX508 sources](https://github.com/kobolabs/Kobo-Reader/tree/master/hw/imx508/ntx)
are related board references; an exact PocketBook `nx611` source release has
not been located. The emulator uses the original 611 binaries.

## Input and networking

Use the arrow keys to navigate, Enter to confirm, and Page Up / Page Down for
the page buttons. `P` operates the power button.

Wi-Fi uses the BCM43362 SDIO model with the original DHD driver and radio
firmware. Enable Wi-Fi and join the open `Kindle-QEMU` access point. Scanning,
association, DHCP and IP traffic use QEMU's network backend.

Standby supports power-button wake. The stock sleep interface refuses sleep
while Wi-Fi is powered. Before suspending manually from the serial console,
run `/ebrmain/bin/netagent wifi off` to unload the original Wi-Fi driver.

## Storage

The builder supplies a 2 GiB microSD on eSDHC1 with the Netronix raw boot
area and four partitions: root, applications, secure state and FAT32 user
storage. The guest identifies its internal card as `mmcblk0`. The kernel starts
at byte offset `0x100000`, the hardware configuration at `0x80000`, and the
waveform at `0x700000`. Netronix size records precede the latter two payloads.

The first boot installs the bundled factory content. The builder provisions
the controller identity and matching secure state needed by the original
applications. A generated neutral EPDC waveform supplies panel data absent
from the update; it is not physical panel calibration.

Support is experimental. RTC alarm wake is not emulated. Recovery and firmware
updates are unverified.
