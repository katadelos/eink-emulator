# Kobo Forma

The `kobo-forma` model boots the stock Forma U-Boot, Linux 4.1.15 and
Nickel UI from a compact eMMC image. The implemented board is Netronix
E80K02 with an i.MX6SLL, 512 MiB RAM and a 1440 × 1920 portrait display.
Bring-up uses the live-device dumps from firmware 4.38.23171.

## Firmware

Place these files in `firmware/kobo-forma/`:

| File | Source |
| --- | --- |
| `u-boot.imx` | `upgrade/mx6sll-ntx/u-boot-mx6sll-E80K00-LPDDR2-512MB.imx` from the Forma update |
| `boot-region.img` | First 49,152 sectors (24 MiB) of the device's eMMC |
| `rootfs.img` | Device partition 1 |
| `recoveryfs.img` | Device partition 2 |

The update is listed by [pgaskin's firmware index](https://pgaskin.net/KoboStuff/kobofirmware.html).
The reference update used here is [4.38.23171 for Kobo mark 7](https://ereaderfiles.kobo.com/firmwares/kobo7/Oct2024/kobo-update-4.38.23171.zip).
Extract its bootloader without installing the update over the live dump:

```sh
mkdir -p firmware/kobo-forma
unzip -p kobo-forma-work/kobo-update-4.38.23171.zip \
  upgrade/mx6sll-ntx/u-boot-mx6sll-E80K00-LPDDR2-512MB.imx \
  > firmware/kobo-forma/u-boot.imx
```

The original dumps in `kobo-forma-work/` can be linked into that firmware
directory. The image builder repairs the journal on a copy of the live
root filesystem before installing the guest overrides. Originals remain
untouched. The kernel, device tree, hardware configuration and waveform
are loaded by U-Boot from their original offsets in the boot region.
The separate eMMC boot-partition dumps are not required for this boot path.

[Kobo's Forma kernel and U-Boot sources](https://github.com/kobolabs/Kobo-Reader/tree/master/hw/imx6sll-forma)
are reference material only; neither is built. The downloaded archives and
extracted sources are retained in `kobo-forma-work/reference/`.

## Create and run

```sh
./eink create forma-ui --model kobo-forma --sideloaded
./eink run forma-ui --serial-socket --qmp-socket
```

On macOS the normal run command opens Cocoa. Click for touch and drag for
a single-finger swipe. Page Up / Left and Page Down / Right drive the two
physical page buttons; P drives the power button. QEMU's mouse-release
shortcut is Control–Option–G.

`--sideloaded` adds `eink.sideloaded=1` to the vendor kernel command line.
The guest hook initializes a new userstore with `SideloadedMode=true` and
an English locale **before Hindenburg starts**, so the first boot opens
My Books without language selection or account setup. Existing settings
are preserved on later boots. Omit the flag to use the normal setup flow.

The complete virtual eMMC is 2 GiB. The root and recovery partition offsets
are preserved, leaving about 1.48 GiB for a fresh FAT32 userstore. Each
instance uses a writable qcow2 overlay over the shared base image.

The serial socket and log are under `machines/forma-ui/`. The development
image permits the `root` serial login without a password.

## Implementation notes

The model includes the Ricoh619 PMIC/RTC, TPS65185 display supply, Cypress
TrueTouch Gen5 touchscreen, page/power GPIOs, eMMC, RNG and the EPDC/PxP
display path. Scanout follows the PxP source format as boot changes from
RGB565 to Nickel's 32-bit framebuffer. Touch reports follow both the
kernel's sensor mounting transform and Nickel's portrait transform.

EPDC working-buffer completion precedes LUT completion. Signalling both
in one interrupt triggers a double free in this vendor kernel's marker
handling; the model keeps them separate without patching the kernel.

Wi-Fi, automatic rotation, physical battery discharge, frontlight optics
and e-ink waveform/ghosting effects are not emulated. The display uses
the stock kernel's reserved framebuffer address; other kernel builds and
firmware versions have not been validated.
