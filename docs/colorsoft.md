# Kindle Colorsoft

Follow the component checklist in [firmware setup](firmware.md), then create a
persistent machine once:

```sh
./eink build
./eink create colorsoft --model kindle-colorsoft --profile production
./eink run colorsoft --qmp-socket
```

`create` composes a sparse GPT disk from `boot.img` and `rootfs.img`, then
caches it as an immutable base shared by instance overlays. It generates the
synthetic waveform automatically. It does not
consume a physical or preassembled eMMC image.

A newly created instance formats its persistent guest filesystems once, then
reboots within the same QEMU process before continuing to the splash screen.
After the framework is ready, a guest bootmod closes the network/account setup
application and returns to the already-loaded Home app. The guest remains
deregistered because the emulator does not invent Amazon account credentials.

The normal `run` flow opens the Cocoa display and keeps serial attached to its
terminal. If QMP is enabled, another `run` invocation detects the live process
and reuses it instead of starting another boot. Use the reusable inspection
commands while that process remains running:

```sh
python3 scripts/eink-qmp.py --machine colorsoft display
python3 scripts/eink-qmp.py --machine colorsoft snapshot --output /tmp/colorsoft-state.json
python3 scripts/eink-qmp.py --machine colorsoft screendump /tmp/colorsoft.png
python3 scripts/eink-qmp.py --machine colorsoft tap 950 1540
```

The Cocoa surface follows HWTCON waveform commits, not uncommitted writes to
the mapped CFA framebuffer. During the bootloader-to-framework handoff it also
retains the splash across the single uniform staging update, matching the
stateful e-ink panel instead of briefly showing the guest's scratch frame.
`display` exposes the waveform, refresh, handoff-arm, and blank-retention
counters used to distinguish those states.

To detach serial from the launch terminal and expose the instance-scoped
serial endpoint, use:

```sh
./eink run colorsoft --qmp-socket --serial-socket
socat -,raw,echo=0 UNIX-CONNECT:machines/colorsoft/colorsoft.serial.sock
```

Cocoa pointer input and QMP touch injection both enter through the emulated
FT5536G controller, its I2C reports, and its interrupt line before reaching the
stock kernel input driver. See [QMP workflows](qmp.md) for synchronized device
snapshots and [guest compatibility changes](guest-overrides.md) for the rootfs
preparation applied to generated images.

Development hardware can instead select `dvt`, `evt`, `hvt`, or `proto` at
creation time. The selected profile is stored in the instance manifest and
controls the emulated board tattoo.
