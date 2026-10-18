<div align="center">
  <h1>E-ink emulator</h1>
  <img src="images/header.png" alt="E-ink emulator">
</div>

Run Kindle, Kobo, Tolino, PocketBook and reMarkable firmware in QEMU with
persistent storage and input. Network support varies by model. Scribe
support is experimental; see the model pages below.

Supply your own firmware. The project is not affiliated with Amazon or
Rakuten Kobo.

## Host requirements

- Python 3.10 or newer
- A C compiler, Ninja and the standard QEMU build dependencies
- `mke2fs`, `e2fsck`, `resize2fs`, `tune2fs` and `debugfs` from e2fsprogs
- `ssh-keygen` from OpenSSH for Kindle and Tolino SSH access
- `zstd` to import Tolino updates
- [KindleTool](https://github.com/NiLuJe/KindleTool) to import Kindle recovery packages

On macOS, install e2fsprogs through Homebrew.

### Nix users

If you use [Nix](https://nixos.org/), you can enter an environment with all host requirements and dependencies preconfigured:

```sh
nix develop
```

Alternatively, if you use [direnv](https://direnv.net/) / [nix-direnv](https://github.com/nix-community/nix-direnv), run:

```sh
direnv allow
```

and the development environment will be loaded automatically when entering this directory.

## Quick start

```sh
git clone git@github.com:katadelos/eink-emulator.git
cd eink-emulator
./eink models
./eink firmware
```

Choose a model and supply the files listed by `./eink firmware`. For example,
with a [Paperwhite 5 recovery package](docs/paperwhite-5.md):

```sh
./eink import /path/to/update.bin --model kindle-paperwhite-5
./eink create my-reader --model kindle-paperwhite-5 --profile production
./eink run my-reader
```

`create` builds QEMU if needed and prepares the instance disk. On macOS,
`run` opens a Cocoa window. Click to tap; serial uses the launching terminal.
To reopen the saved instance, use `run` again.

Other models need different files and, in some cases, a hardware profile.
See [firmware setup](docs/firmware.md). Kobo Forma and Elipsa 2E accept
`--sideloaded` at creation to skip account setup.

Kindle 4 through Oasis 3 also support `create --mrpi` to pre-install KUAL,
MRPI and their jailbreak prerequisites. Use `--kual` or `--jailbreak` for a
smaller setup; see [Kindle add-ons and pinned downloads](docs/kindle-addons.md).
New instances in this family start at Home with offline setup already prepared.

## Everyday use

```sh
./eink list                         # List saved instances.
./eink images                       # Show disk use.
./eink reset my-reader              # Discard guest changes; restore the prepared image.
./eink delete my-reader             # Delete a stopped instance and unused bases.
./eink images --prune               # Reclaim bases left by manual deletions.
./eink images --compact             # Deduplicate stopped base revisions.
./eink run my-reader --qmp-socket    # Start with QMP control.
./eink run --help                   # List launch options.
```

`--serial-socket` sends serial output to a socket and log. `--headless`
disables the display; `--vnc ENDPOINT` selects VNC. Use `--dry-run` to print
the QEMU command. See [QMP inspection](docs/qmp.md) for remote control and
[storage](docs/storage.md) for backups.

Kindle images start SSH over USB automatically:

```sh
ssh -i build/ssh/id_ed25519 -p 2222 root@127.0.0.1
```

Select `Kindle-QEMU` in the guest for Wi-Fi; SSH then also works on port 2223.
Kobo provides USB telnet on port 2323. See [networking](docs/networking.md)
for file transfer, port options and limits.

## Taking a screenshot

With serial in the terminal, press `Ctrl-A C` to open the QEMU monitor:

```text
(qemu) screendump /tmp/eink-screen.png -f png
```

Press `Ctrl-A C` again to return to serial. With `--serial-socket`, use
[QMP screendump](docs/qmp.md#common-commands).

## Using a raw QEMU machine

For bootloader work, supply QEMU options directly:

```sh
./eink qemu -- \
  -machine imx6sl-wario -m 512M \
  -bios /path/to/u-boot.bin -serial mon:stdio -no-reboot
```

This does not load a saved instance. Supply any required disks and machine
properties. To boot a kernel directly, replace `-bios /path/to/u-boot.bin`
with `-kernel /path/to/uImage -append '<kernel command line>'`.
Use `--arch aarch64` before `--` for AArch64 machines.

Arguments after `--` also pass through on `run`; see
[device identity](docs/firmware.md#qemu-device-identity) for the required option order.

## Supported models

| Full name | Abbreviation | Board name | Notes |
| --- | --- | --- | --- |
| Kindle 4 | K4 | Tequila | |
| Kindle Touch | K5 | Whitney | |
| Kindle Paperwhite 1 | PW1 | Celeste | |
| Kindle Paperwhite 2 | PW2 | Pinot | |
| Kindle Basic (2014) | KT2 | Bourbon | |
| Kindle Voyage | KV | Icewine | |
| Kindle Paperwhite 3 | PW3 | Muscat | |
| Kindle Basic 2 (2016) | KT3 | Eanab | |
| [Kindle Oasis 1](docs/oasis.md) | KOA1 | Whisky / Duet | |
| [Kindle Oasis 2](docs/oasis.md) | KOA2 | Cognac / Zelda | |
| Kindle Paperwhite 4 | PW4 | Moonshine | |
| [Kindle Basic 4 (2019)](docs/kt4.md) | KT4 | Jaeger | |
| [Kindle Oasis 3](docs/koa3.md) | KOA3 | Stinger | |
| [Kindle Paperwhite 5](docs/paperwhite-5.md) | PW5 | Malbec | |
| Kindle Basic 5 (2022) | KT5 | Cava | |
| [Kindle Scribe 1](docs/scribe-1.md) | KS1 | Barolo | Experimental |
| Kindle Basic 6 (2024) | KT6 | Rossini | |
| [Kindle Basic 7 (2026)](docs/kt7.md) | KT7 | Prosecco | Experimental |
| [Kindle Colorsoft](docs/colorsoft.md) | CS | Sangria Color | |
| [Kindle Paperwhite 6](docs/paperwhite-6.md) | PW6 / PW12 | Sangria | |
| [Kindle Scribe 2](docs/scribe-2.md) | KS2 | Pisco | Experimental |
| [Kindle Scribe 3](docs/scribe-3.md) | KS3 | Paloma | Experimental |
| [Kindle Scribe Colorsoft](docs/scribe-colorsoft.md) | KSC | Calvados | Experimental |
| Kobo Mini | N705 | E50610 | |
| Kobo Touch | N905 | E60610 | |
| [Kobo Glo](docs/kobo-glo.md) | N613 | E606B0 | Experimental |
| [Kobo Aura HD](docs/kobo-aura-hd.md) | N204B | E606C0 | Experimental |
| [Kobo Glo HD](docs/kobo-glo-hd.md) | N437 | E60Q9X | Experimental |
| [Kobo Clara HD](docs/kobo-clara-hd.md) | N249 | E60K02 | Experimental |
| [Kobo Forma](docs/kobo-forma.md) | Forma | E80K02 | Stock UI, offline sideloaded mode |
| [Kobo Elipsa 2E](docs/kobo-elipsa-2e.md) | N605 | EA0T00 | Stock UI, offline sideloaded mode |
| [Tolino Shine (5th generation)](docs/tolino-shine.md) | Shine 5 | E60T00 / Kobo Clara BW; E60V00 / TPV revision | Experimental |
| [Tolino Shine Color](docs/tolino-shine.md) | Shine Color | E60T00 / Kobo Clara Colour | Experimental |
| [Tolino Vision Color](docs/tolino-vision-color.md) | Vision Color | E70T04 / Kobo Libra Colour | Experimental |
| [PocketBook 360 Plus New](docs/pocketbook-512.md) | PB512 | i.MX50 | Experimental |
| [PocketBook Basic 611](docs/pocketbook-611.md) | PB611 | i.MX50 | Experimental |
| [PocketBook Basic 613](docs/pocketbook-613.md) | PB613 | EP8 | Experimental |
| [PocketBook Touch 622](docs/pocketbook-622.md) | PB622 | EP7 | Experimental |
| [PocketBook Touch Lux 623](docs/pocketbook-623.md) | PB623 | EP7A | Experimental |
| [PocketBook Ultra 650](docs/pocketbook-650.md) | PB650 | i.MX6 SoloLite | Experimental |
| [PocketBook Basic Lux 4](docs/pocketbook-618.md) | PB618 | Allwinner B288 | Experimental |
| [PocketBook Verse Lite](docs/pocketbook-619.md) | PB619 | Allwinner B288 | Experimental |
| [PocketBook Touch Lux 4](docs/pocketbook-627.md) | PB627 | Allwinner A13 | Experimental |
| [PocketBook Touch Lux 5](docs/pocketbook-628.md) | PB628 | Allwinner B288 | Experimental |
| [PocketBook Verse](docs/pocketbook-629.md) | PB629 | Allwinner B288 | Experimental |
| [PocketBook Touch HD 3](docs/pocketbook-632.md) | PB632 | Allwinner B288 | Experimental |
| [PocketBook Color](docs/pocketbook-633.md) | PB633 | Allwinner B288 | Experimental |
| [PocketBook Verse Pro](docs/pocketbook-634.md) | PB634 | Allwinner B288 | Experimental |
| [PocketBook Verse Pro Color](docs/pocketbook-634k3.md) | PB634K3 | Allwinner B300 | Experimental |
| [PocketBook Era](docs/pocketbook-700.md) | PB700 | Allwinner B288 | Experimental |
| [PocketBook Era Color](docs/pocketbook-700k3.md) | PB700K3 | Allwinner B300 | Experimental |
| [PocketBook InkPad 3](docs/pocketbook-740.md) | PB740 | Allwinner B288 | Experimental |
| [PocketBook InkPad 3 Pro](docs/pocketbook-740-2.md) | PB740-2 | Allwinner B288 | Experimental |
| [PocketBook InkPad Color](docs/pocketbook-741.md) | PB741 | Allwinner B288 | Experimental |
| [PocketBook InkPad Color 3](docs/pocketbook-743k3.md) | PB743K3 | Allwinner B300 | Experimental |
| [PocketBook InkPad Lite](docs/pocketbook-970.md) | PB970 | Allwinner B288 | Experimental |
| [PocketBook InkPad X](docs/pocketbook-1040.md) | PB1040 | Allwinner B288 | Experimental |
| [PocketBook Color Lux 801](docs/pocketbook-801.md) | PB801 | i.MX50 | Experimental |
| [reMarkable 1](docs/remarkable-1.md) | RM1 | Zero Gravitas / i.MX6 SoloLite | Experimental; offline UI |
| [reMarkable 2](docs/remarkable-2.md) | RM2 | Zero Sugar / i.MX7D | Experimental; offline UI |
| [reMarkable Paper Pro](docs/remarkable-paper-pro.md) | Ferrari | i.MX8M Mini | Experimental; offline UI, grayscale output |

[Guest compatibility changes](docs/guest-overrides.md) explains how the builders
adapt vendor firmware to the emulated hardware.
