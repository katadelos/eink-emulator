# Guest compatibility changes

Image builders change a copy of the rootfs so vendor firmware can run on the
emulated hardware. Imported firmware stays unchanged. Platform files are in
`guest-overrides/`; shared SSH files are in
[`guest-additions/`](../guest-additions/README.md).

Create a new instance to use changed startup files. Existing instances keep
their original base image and guest configuration.

## Network access

All new Kindle images start Dropbear SSH on USB and Wi-Fi. They keep the
vendor radio services and reserve the USB controller for Ethernet by disabling
competing MTP and USB jobs. Route and DNS hooks keep USB access available when
the guest changes its Wi-Fi connection. See [networking](networking.md).

MediaTek Kindle and Tolino images retain the stock WMT and Wi-Fi kernel modules
from the imported firmware. Connectivity power, bus protection and reset
behavior are implemented in QEMU's device models.

## Older Kindle models

Kindle 4 through Oasis 3 skip initial setup and open Home. The
`kindle/qemu-offline-setup` hook selects British English when no locale is set
and records setup completion before the UI starts. Locale and preference
changes persist across boots. The guest remains unregistered; newer firmware
shows a registration invitation on Home, while Library is usable offline.

Kindle 4, Touch and Paperwhite 1 use synthetic panel flash with the waveform
data required by the stock display service. Basic 2014 and Voyage use panel
identifiers for their 600×800 and 1072×1448 displays. If you supply a panel-flash
backing file, QEMU uses its contents.

| Models | Changes |
| --- | --- |
| Basic 2014, Paperwhite 2/3, Voyage | Keyboard, service startup, wake and suspend fixes |
| Basic 2016 | Keyboard, service startup, offline setup, wake and suspend fixes |
| Oasis 1/2 | Offline setup, serial console and automatic suspend prevention |
| KT4, Oasis 3 | Locale, initial setup, wake and serial console |
| Paperwhite 1, Touch | Wake and optional text-to-speech fixes |
| Paperwhite 4 | First-boot setup, locale, wake and service fixes |

Several builders clear the root password for serial access. SSH uses the
shared public key and does not accept passwords.

## Bellatrix

Basic 2022/2024, Paperwhite 5/6 and Colorsoft skip initial account setup and
open Home without registration. The builder removes repeated permission
repairs and skips the missing hibernate payload to reduce startup delays.
It extends the framework timeout and disables Minerva and automatic suspend.
Wi-Fi services remain enabled.

Some older releases on the MTP boards (Basic 2024, Paperwhite 6, Colorsoft),
such as Paperwhite 6 5.18.6, still load a USB storage gadget when the
userstore mounts. The builder removes it so the controller stays free for USB
Ethernet.

Releases up to at least 5.16.3 mount var-local directly in
`filesystems_var_local.conf` rather than `varlocal_functions`, and never
erase the hibernate partition. The layout depends on the firmware version,
not the model: Basic 2022 and Paperwhite 5 ship identical files in 5.16.3.
The builder patches the mount where it is and skips the hibernate step.
These releases also copy `/opt/amazon/factory_fresh` when they format a
blank var-local partition, but do not ship that directory. The copy fails,
and the system monitor hard-reboots the first boot. The builder skips the
copy when the directory is absent, as later releases do.

Colorsoft also disables native debugger stack dumps, which can occupy an
emulated CPU. See [Colorsoft](colorsoft.md) for display behavior.

## Scribe 1 and 2

Barolo and Pisco skip initial setup, select British English and supply the
missing DVT device type. An active display stays awake for up to two hours.
[The Bellatrix3 guide](../guest-overrides/bellatrix3/README.md) explains the
startup order, permission changes and service files.

## Scribe 3 and Colorsoft

Paloma and Calvados use development copies of the rootfs and boot FIT. The
builder enables a serial root shell, USB Ethernet and SSH. It disables verity
for the modified rootfs and updates the FIT device-tree hash. The rootfs
partition retains the source size and AVB footer, but its contents are changed.
The language picker retries its powerd startup call for up to 60 seconds so
delayed LIPC initialization does not immediately reboot the guest. A persistent
failure still takes the firmware's normal recovery path.

The catalogue enables QEMU development mode. This removes the production-key
requirement from U-Boot's in-memory control tree. The kernel binary stays
unchanged. This provides development access; a usable Home screen is not yet
verified.

## Kobo

Forma and Elipsa 2E accept `--sideloaded` at creation. A guest hook runs before
Hindenburg and Nickel. It sets an English locale and `SideloadedMode=true` so
the first boot opens My Books without account setup. Later boots preserve
existing settings. Both builders also enable serial root access.

All Kobo models start USB Ethernet and telnet automatically.

## Tolino Vision Color and Shine

The builder prepares a copy of the update's rootfs with serial root access,
USB RNDIS and public-key access through the stock OpenSSH server. On color
models, display startup selects the kernel's built-in `NTX_SF` CFA conversion
because the update does not include the factory color lookup table. Imported
bootloader, kernel and rootfs files remain unchanged. The WMT and Wi-Fi kernel
modules are used unmodified. See
[Tolino Vision Color](tolino-vision-color.md) and
[Shine 5 / Shine Color](tolino-shine.md) for storage and calibration limits.

## PocketBook

PocketBook images retain the stock setup wizard. B288 and B300 images prepare
the bundled fontconfig caches for their filesystem timestamps and FAT font
directories before applications start. Skipping Wi-Fi opens the licence screen
without rebuilding the font indexes.

Basic Lux 4 (618), Verse Lite (619), Verse (629), Color (633), Verse Pro (634),
Era (700), InkPad Color (741), InkPad Lite (970), Verse Pro Color (634K3),
Era Color (700K3) and InkPad Color 3 (743K3) updates omit the provisioned
IOC identity and signed partner configuration. Their prepared images select the
IOC's unprovisioned identity
response and wrap the monitor's safebox reader.
The wrapper calls the native reader first. Failed reads for the emulator's
`000000000000` serial receive a cleared response; chunk 0 supplies a local
noncontract configuration so the stock setup wizard can complete offline. Native
records and the signed write path retain their original handling. The monitor
copy is prepared at boot with firmware-specific guards; imported files remain
unchanged.

The Era Color 6.10.2359 monitor needs an aligned file gap before its writable
segment to hold that wrapper. Its prepared copy shifts ELF file offsets by one
page while preserving virtual addresses and writable data.

The B300 images omit automatic loading of the Mali module in the prepared
startup scripts. Mali 3D acceleration is not emulated; the stock interface uses
CPU rendering. The original module remains in the imported firmware.

The original network manager and radio modules handle Wi-Fi. See
[PocketBook Wi-Fi](networking.md#pocketbook-wi-fi) for the access point names.
