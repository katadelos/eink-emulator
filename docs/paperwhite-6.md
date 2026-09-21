# Kindle Paperwhite 6

Paperwhite 6 (PW12) uses the monochrome Sangria board on MT8113 Bellatrix4.
It skips account setup and opens Home without registration.

## Setup

Supply the files listed by `./eink firmware`:

```sh
./eink create pw12 --model kindle-paperwhite-6 --profile production
./eink run pw12
```

Click the display to tap. Touch passes through the emulated FT5536G controller
and stock kernel driver. See [hardware profiles](firmware.md#hardware-profiles)
for development boards and [networking](networking.md) for SSH and Wi-Fi.

[Guest changes](guest-overrides.md#bellatrix) describes the startup modifications.
Use [QMP](qmp.md#bellatrix-hardware-state) to inspect a slow boot or blank display.
