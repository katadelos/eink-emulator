# Bellatrix3 guest setup

These files are installed into a temporary copy of the Barolo/Pisco rootfs.
The imported firmware and kernel FIT remain unchanged.

| File | Purpose |
| --- | --- |
| `console.conf` | One supervised serial shell on ttyS0, with a fresh controlling session on respawn |
| `display` | Load the original HWTCON v2 module with the selected waveform, then emit `start_mdpd` |
| `qemu-development-state.conf` | Initialize local OOBE completion, British English locale and the stock device-type override before display starts |
| `qemu-runtime-permissions` | Initialize shared-directory ownership and inheritance; migrate persistent permissions once |
| `qemu-usb-network.conf` | Configure stock g_ether ECM through QEMU's USB network backend |
| `qemu-telnet.conf` | Provide a shell on the guest USB address, forwarded only from host loopback |
| `mtp.conf` | Disable MTP's competing ownership of the USB gadget controller |
| `qemu-review-awake.conf` | Refresh the idle timer every 30 seconds for at most two hours while the display is already active |

The state job runs on `starting display`, after decrypted varlocal becomes
available. Locale and preferences are backed up under
`/var/local/system/qemu-development`; the initialization marker preserves
later user choices. The stock-supported `/var/local/deviceType.txt` override
covers DVT tattoos absent from the production lookup table and preserves
valid existing overrides. No account credentials or registration are created.

Permission setup runs when the runtime tmpfs and persistent storage are ready.
Persistent migration is tracked with a versioned marker; directories inherit
`javausers` through setgid and the stock Upstart umask. Framework restarts
check shared top-level directories. Private root storage and the stock
chroot exclusion retain their original ownership policies.

The image builder extends framework readiness to 600 seconds and stops the
stock sysctl job from respawning after success. Java verification, code-cache
size and compilation thresholds remain unchanged. Existing Bellatrix timezone
and registration capability gates are reused, while unavailable Minerva and
native wireless jobs are disabled. Power-key and suspend behavior remain enabled.

A generated synthetic waveform is installed at `/data/init_bin/wf_lut.gz` and
in FAT p2's `waveform_to_use` directory. A supplied waveform partition omits
the rootfs default. The display hook preserves an already loaded module;
otherwise it requires one selected `.wrf.gz`, or the generated default when
the selection is absent. Synthetic data does not model physical calibration.

Serial input/output use the launching terminal by default. `--serial-socket`
opts into a socket and log. Telnet is forwarded from `127.0.0.1:2323` by default;
`--telnet-port` changes the host port. It provides a local development shell.
