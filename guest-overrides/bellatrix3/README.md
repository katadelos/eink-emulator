# Bellatrix3 guest setup

The Scribe 1 and 2 image builder installs these files into a copy of the
rootfs. The imported firmware and kernel are kept intact.

| File | Purpose |
| --- | --- |
| `console.conf` | Run and supervise a serial shell on ttyS0 |
| `display` | Load HWTCON v2 with the selected waveform, then start MDP |
| `qemu-development-state.conf` | Set the device type, skip initial setup and select British English on first boot |
| `qemu-runtime-permissions` | Set shared directory permissions before services start |
| `qemu-usb-network.conf` | Configure USB Ethernet with the stock g_ether driver |
| `qemu-telnet.conf` | Run telnet on the guest USB interface |
| `mtp.conf` | Disable MTP so it cannot take over the USB controller |
| `qemu-review-awake.conf` | Keep the active display awake for up to two hours |

## First boot

The state job runs before display starts, once encrypted persistent storage
is mounted. It backs up locale and preferences under
`/var/local/system/qemu-development` and records that setup is complete.
Later boots preserve the user's choices. This skips OOBE without creating
an Amazon account.

`/var/local/deviceType.txt` supplies the device type for DVT board IDs absent
from the firmware's production lookup table. A valid existing value is kept.

## Startup and permissions

Runtime permissions are set before services create shared files. Existing
persistent files are updated once, tracked by a version marker. Shared
directories use setgid so new files inherit the `javausers` group. Framework
restarts check the top-level directories rather than walking every file.
The private root directory and the stock chroot exclusion keep their original
ownership rules.

The framework gets 600 seconds to start, and a successful sysctl job stops
instead of respawning. Java settings remain unchanged. Timezone and
registration jobs check that their required services are available; Minerva
and native wireless jobs are disabled. The keep-awake job runs every 30
seconds for up to two hours and only refreshes an already active display.
Manual sleep remains available.

## Display and console

A generated waveform is installed in FAT p2 and at
`/data/init_bin/wf_lut.gz`. If a waveform partition is supplied, the rootfs
default is omitted. The display job leaves an already loaded HWTCON module
alone; otherwise, it loads the selected `.wrf.gz` file from p2, using the
generated default if p2 has no selection. Synthetic data enables display
emulation without physical panel calibration.

Serial uses the launching terminal. `--serial-socket` redirects it to the
instance's socket and log. Telnet forwards from `127.0.0.1:2323`; use
`--telnet-port PORT` to change the host port.
