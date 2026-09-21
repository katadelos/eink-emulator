# Kindle Colorsoft

Colorsoft uses the Sangria Color board on MT8113 Bellatrix4. It skips account
setup and opens Home without registration.

## Setup

Supply the files listed by `./eink firmware`:

```sh
./eink create colorsoft --model kindle-colorsoft --profile production
./eink run colorsoft
```

First boot formats persistent filesystems and restarts within the same QEMU
process. Click the display to tap. See [hardware profiles](firmware.md#hardware-profiles)
for development boards and [networking](networking.md) for SSH and Wi-Fi.

## Display behavior

The display changes when HWTCON commits a waveform update. It retains the
splash across a uniform staging frame during boot, so the guest's temporary
work buffer does not appear on screen. Touch passes through the emulated
FT5536G controller and stock kernel driver.

Use the [QMP display commands](qmp.md#bellatrix-hardware-state) to inspect
update counters or capture a screenshot. [Guest changes](guest-overrides.md#bellatrix)
describes the startup modifications.
