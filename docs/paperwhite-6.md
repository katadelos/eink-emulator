# Kindle Paperwhite 6

Paperwhite 6 is the 12th-generation Paperwhite, also referred to as PW12. It
uses the monochrome Sangria board on the shared MT8113 Bellatrix4 platform.

Follow the component checklist in [firmware setup](firmware.md), then create a
persistent machine once:

```sh
./eink build
./eink create pw12 --model kindle-paperwhite-6 --profile production
./eink run pw12 --qmp-socket
```

The normal run flow opens the Cocoa display and keeps serial attached to its
terminal. The first boot initializes persistent filesystems, shows the Kindle
splash, and reaches Home after roughly a minute. A guest bootmod closes the
network/account setup application without inventing registration data.

The instance reuses its writable overlay on subsequent launches. When QMP is
enabled, another `run` invocation detects the live process instead of starting
a second QEMU process:

```sh
python3 scripts/eink-qmp.py --machine pw12 machine
python3 scripts/eink-qmp.py --machine pw12 display
python3 scripts/eink-qmp.py --machine pw12 screendump /tmp/pw12.png
```

Cocoa pointer input enters through the emulated FT5536G controller, its I2C
reports, and interrupt line before reaching the stock kernel input driver.
Use `--serial-socket` only when the console must be detached from the launch
terminal.

Development units can select `dvt`, `evt`, `hvt1.1`, `hvt`, or `proto` instead
of `production` at creation time. The profile is stored with the instance and
selects the matching stock board tattoo.
