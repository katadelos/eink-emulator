# Bellatrix3 guest setup

Scribe 1 and 2 use these files to start the framework on emulated hardware:

| File | Purpose |
| --- | --- |
| `console.conf` | Supervise a serial shell on `ttyS0` |
| `display` | Load HWTCON v2 with a generated waveform, then start MDP |
| `qemu-development-state.conf` | Set the device type, skip initial setup and select British English |
| `qemu-runtime-permissions` | Set shared directory permissions before services start |
| `../network/qemu-usb-network.conf` | Configure USB Ethernet with `g_ether` |
| `../../guest-additions/ssh/sshd.conf` | Supervise Dropbear |
| `../network/disabled.conf` | Disable MTP and competing USB jobs |
| `qemu-review-awake.conf` | Keep an active display awake for up to two hours |

## First boot

The state job runs after encrypted persistent storage mounts and before
display starts. It backs up locale and preferences in
`/var/local/system/qemu-development`, then records setup completion. Later
boots preserve user choices. It does not create an Amazon account.

`/var/local/deviceType.txt` supplies the device type for DVT board IDs missing
from the production lookup table. A valid existing value is kept.

## Startup and permissions

Permissions are set before services create shared files. A version marker
limits updates to existing files to one pass. Shared directories use setgid
so new files inherit the `javausers` group. Framework restarts check top-level
directories instead of walking every file. The private root directory and
stock chroot exclusion retain their ownership rules.

The framework has 600 seconds to start. A successful sysctl job stops instead
of respawning. Timezone and registration jobs check their service dependencies.
Minerva is disabled; native Wi-Fi jobs remain enabled. Java settings are
unchanged.

The keep-awake job runs every 30 seconds for up to two hours. It refreshes
only an active display; it does not wake a sleeping display.

## Display and access

The generated waveform is installed in FAT p2 and `/data/init_bin/wf_lut.gz`.
The display job loads it from the rootfs unless HWTCON is already loaded.
See [networking](../../docs/networking.md#kindle-ssh) for SSH access.
