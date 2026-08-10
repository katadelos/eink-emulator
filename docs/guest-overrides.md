# Guest compatibility changes

Firmware inputs are treated as immutable. Image creation makes a temporary
rootfs copy and applies the small guest-side changes required by the emulated
hardware before converting the completed disk to QCOW2.

The committed files under `guest-overrides/` are grouped by platform. The
shared Python rootfs component installs them with `debugfs`; board image
modules do not contain their own copies of filesystem-editing logic.

## Wario family

All Wario-family models receive the required service fixes for the GUI
keyboard process, the unavailable performance daemon, wake handling, and
automatic suspend. These apply to Kindle Basic (2014), Paperwhite 2,
Paperwhite 3, and Voyage.

## Kindle Touch and Paperwhite 4

Kindle Touch receives its wake and optional text-to-speech service fixes.
Paperwhite 4 receives wake, first-boot, locale, and unavailable-service fixes.
Both also receive a longer first-boot framework timeout for TCG execution.

Prepared Kindle root filesystems have the guest root password cleared so the
serial console remains usable. This affects only generated, ignored images;
the supplied firmware files are never modified.
