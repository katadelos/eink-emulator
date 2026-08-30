# Guest compatibility changes

Firmware inputs are treated as immutable. Image creation makes a temporary
rootfs copy and applies the small guest-side changes required by the emulated
hardware before converting the completed disk to QCOW2.

The committed files under `guest-overrides/` are grouped by platform. The
shared Python rootfs component installs them with `debugfs`; board image
modules do not contain their own copies of filesystem-editing logic.

## Wario and Heisenberg

Wario models receive service fixes for the GUI keyboard process, the
unavailable performance daemon, wake handling, and automatic suspend. These
apply to Kindle Basic (2014), Paperwhite 2, Paperwhite 3, and Voyage.

Heisenberg has its own complete override set for Kindle Basic (2016). It also
disables services which rely on unmodelled device backends and keeps the guest
in its supported offline mode. Files are intentionally kept separate where
their current behavior matches Wario so each platform can evolve independently.

## Celeste, Kindle Touch, and Paperwhite 4

Celeste and Kindle Touch each keep separate wake and optional text-to-speech
service fixes. Paperwhite 4 receives wake, first-boot, locale, and
unavailable-service fixes. All three also receive a longer first-boot
framework timeout for TCG execution.

## Bellatrix

Kindle Basic 5, Kindle Basic 6, Colorsoft, and Paperwhite 6 preparation copies
the supplied `rootfs.img` before the disk builder places it in the generated
GPT image. It skips the stock recursive permission repair and absent hibernate
payload, waits indefinitely for the framework under TCG, marks account setup
complete before Home is selected, disables both unavailable Minerva telemetry
daemons, and omits the Wi-Fi jobs whose MTK transport has no emulated hardware.
This prevents the transport driver's power-on timeout queue from starving the
guest. Colorsoft also disables native `gdb` stack dumps which can monopolize an
emulated CPU; the other Bellatrix root filesystems do not require that change.
The old debug-only job which mirrored the complete system log through the
emulated serial UART is also omitted; kernel, boot milestone, and login console
output remain available. The remaining overrides prevent automatic suspend and
avoid respawn loops in capability-gated services.

Prepared Kindle root filesystems have the guest root password cleared so the
serial console remains usable. This affects only generated, ignored images;
the supplied firmware files are never modified.
