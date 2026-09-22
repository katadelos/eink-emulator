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
