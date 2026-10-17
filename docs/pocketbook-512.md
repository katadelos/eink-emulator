# PocketBook 360 Plus New (512)

The 360 Plus New uses a Netronix E50602 i.MX50 board with 128 MiB RAM,
a 600 × 800 monochrome display and physical navigation buttons.
Its official update identifies the device as `512`, with firmware revision
`D512.15.7` and bootloader board name `nx512`. This port uses the model name
`pocketbook-512` to preserve that identity.

## Firmware

Import the official 15.7.0 update ZIP, or its extracted `SWUPDATE.BIN`:

```sh
./eink import /path/to/sw_20120423_512_EURO_obreeysync_br_15.7_0_user.zip --model pocketbook-512
./eink create pb512 --model pocketbook-512
./eink run pb512
```

The [official package](https://download.pocketbook-int.com/fw/netronix/360pn/user/sw_20120423_512_EURO_obreeysync_br_15.7_0_user.zip)
contains the original U-Boot, Linux 2.6.35.3 kernel, root filesystem and
application filesystem. Imported firmware belongs under `firmware/pocketbook-512/`
and is excluded from Git. The importer checks the `D512` revision identifier in
this release's update header.

The vendor-published
[Netronix i.MX508 sources](https://github.com/kobolabs/Kobo-Reader/tree/master/hw/imx508/ntx)
provide related bootloader and kernel references.
An exact PocketBook `nx512` source release has not been located.
The emulator uses the original 512 binaries.

## Input and networking

Use the arrow keys to navigate, Enter to confirm, and Page Up / Page Down for
the page buttons. `P` operates the power button and stock screen lock.

Wi-Fi uses the BCM43362 SDIO model with the original DHD driver and radio
firmware. Enable Wi-Fi and join the open `Kindle-QEMU` access point. Scanning,
association, DHCP and IP traffic use QEMU's network backend.

Standby supports button wake. Before suspending manually from the serial
console, run `/ebrmain/bin/netagent disconnect` to unload the original Wi-Fi
driver.

The MMA7660 accelerometer supplies a fixed resting orientation. Host motion,
tap and shake input are not emulated.

## Storage

The builder supplies a 2 GiB microSD on eSDHC1 with the Netronix raw boot
area and four partitions: root, applications, secure state and FAT32 user
storage. The guest identifies its internal card as `mmcblk0`. The kernel starts
at byte offset `0x100000`, the hardware configuration at `0x80000`, and the
waveform at `0x700000`. Netronix size records precede the latter two payloads.

The first boot installs the bundled factory content. The builder provisions
the E50602 disk identity, controller serial and matching secure state needed
by the original applications. A generated neutral EPDC waveform supplies
panel data absent from the update; it is not physical panel calibration.

Support is experimental. RTC alarm wake is not emulated. Recovery and firmware
updates are unverified.
