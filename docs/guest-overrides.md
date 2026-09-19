# Guest compatibility changes

Some models need guest startup changes to run on the emulated hardware.
The image builder applies them to a copy of the rootfs using `debugfs`;
imported firmware files are kept intact. The files are grouped by platform
under `guest-overrides/`.

| Devices | Guest setup |
| --- | --- |
| Basic (2014), Paperwhite 2 and 3, Voyage | Wario service, keyboard, wake and suspend fixes |
| Basic (2016) | Heisenberg service and offline-mode fixes |
| [Oasis 1 and 2](oasis.md) | Offline setup, keeps the screen awake, serial console |
| [KT4](kt4.md) | Locale, setup, wake and serial console |
| [KOA3](koa3.md) | Locale, setup, wake and serial console |
| Paperwhite 1, Kindle Touch | Wake and optional text-to-speech fixes |
| Paperwhite 4 | Wake, first-boot, locale and service fixes |
| Basic 5 and 6, Colorsoft, Paperwhite 6 | Bellatrix startup and service fixes |
| [Scribe 1](scribe-1.md), [Scribe 2](scribe-2.md) | Serial shell, USB networking, initial setup skip, permissions and keep-awake |
| [Scribe 3](scribe-3.md), [Scribe Colorsoft](scribe-colorsoft.md) | Original rootfs, including AVB metadata |
| [Kobo Elipsa 2E](kobo-elipsa-2e.md) | Optional offline sideloaded mode before Hindenburg starts; serial root shell |

## Older Kindle models

Wario and Heisenberg receive fixes for the GUI keyboard process, unavailable
services, wake handling and automatic suspend. Celeste and Kindle Touch have
separate wake and optional text-to-speech fixes. Paperwhite 4 also receives
first-boot and locale setup. Prepared images for these models clear the root
password for serial access.

## Bellatrix

Basic 5 and 6, Colorsoft and Paperwhite 6 skip recursive permission repair
and the absent hibernate payload, wait longer for the framework, and skip
initial account setup before opening Home. Minerva and unsupported Wi-Fi
jobs are disabled. Other overrides prevent automatic suspend and service
respawn loops.

Colorsoft also skips native debugger stack dumps that can occupy an emulated
CPU. The job that copies the entire system log to serial is removed; kernel
output, boot messages and the login console remain available.

## Scribe 1 and 2

Barolo and Pisco provide a supervised serial shell and USB Ethernet/telnet.
On first boot, they skip OOBE, select British English and set the device type
needed for DVT boards. Existing preferences are backed up. Shared directory
permissions are set before services start, and a keep-awake job runs for up
to two hours while the display is active.

The original display module uses a supplied waveform or a generated
synthetic waveform. Java settings stay unchanged. See
[the Bellatrix3 files](../guest-overrides/bellatrix3/README.md) for details.

## Scribe 3 and Colorsoft

Paloma and Calvados use the original AVB-protected rootfs. Their image
builder prepares storage and a waveform partition without changing guest
startup scripts, Java settings or initial setup.
