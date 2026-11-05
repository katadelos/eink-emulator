# Kindle guest additions

Each Kindle image receives Dropbear SSH, a key generator, an SSH client and
SCP, installed under `/usr/sbin` and `/usr/bin`. See
[networking](../docs/networking.md#kindle-ssh) for login and service commands.

## Binaries

`dropbear/` contains Dropbear 2026.94. Each directory includes its licence.
The builder selects binaries for the guest userspace ABI:

| Directory | Guest userspace |
| --- | --- |
| `kindle5` | ARMv7 soft float: Kindle 4, Touch and Paperwhite 1 |
| `kindlepw2` | ARMv7 soft float: later models without the hard-float loader |
| `kindlehf` | ARMv7 hard float: rootfs contains `/lib/ld-linux-armhf.so.3` |

MediaTek firmware can use ARMv7 soft float or hard float, even on an emulated
ARM64 CPU; the guest loader determines the selection.
The binaries link to the guest loader and C library. They support public-key
authentication and SCP. Password authentication and SFTP are disabled.

## Startup and keys

`ssh/sshd.conf` replaces the stock Upstart SSH job. Kindle 4 uses a respawning
`/etc/inittab` entry. Both run `ssh/qemu-sshd` after persistent storage is
available. Dropbear listens on port 22; guest firewall rules allow USB and
Wi-Fi SSH traffic.

The login public key is installed at `/etc/eink-ssh/authorized_keys`. Each
guest creates its own server key in `/var/local/eink-ssh`. Framework permission
changes exclude that directory to keep the key private.

## Login message

New Kindle instances replace `/etc/motd` with [`kindle/eink-motd`](kindle/eink-motd).
The file contains the `cyberlarge` banner, repository URL, and a list of Kindle
projects. The banner is rendered on the host with `toilet` and
`lolcat -F 0.5 -f`; project names are cyan and descriptions and URLs are plain. Run
`python3 scripts/render-eink-motd.py` to regenerate it; redundant colour escapes
are removed to fit Dropbear's 2000-byte MOTD limit. Guests display the stored
ANSI colours on serial and SSH login; neither rendering tool is installed or
needed there. SSH commands and file transfers do not display the banner.

Use `eink create --no-motd` to retain the stock login message. This option is
independent of `--no-opkg` and the jailbreak flags. Existing instances retain
the message in their prepared image.

## opkg

New Kindle instances include `kindle/qemu-opkg` in the startup install hook.
It installs opkg from the public bootstrap and activates the SDK immediately
on the first boot, before the framework starts. No reboot is required. Later
boots restore the SDK runtime without reinstalling it. The bootstrap selects
`kindle5`, `kindlepw2` or `kindlehf` from the running firmware. Optional jailbreak
setup runs before this hook.

For `kindle5`, the builder stages the selected feed's installer and bootstrap
bundle for offline installation, avoiding the firmware's old TLS implementation.
Other ABIs download the bootstrap in the guest during the first boot.

Use `eink create --no-opkg` to omit it, or `--opkg-feed URL` to select another
feed. See [opkg setup](../docs/kindle-addons.md#opkg-beta) for package commands,
storage and logs.

## Optional KUAL and MRPI

`eink create --jailbreak`, `--kual` and `--mrpi` opt into the pinned inputs in
[`kindle/assets.json`](kindle/assets.json). `--jbsh` instead installs the
pinned jb.sh with `kindle/qemu-jbsh`, which runs it once before the first
framework start. Downloaded archives stay in the ignored
`kindle/downloads/` directory. See [Kindle add-ons](../docs/kindle-addons.md) for dependencies,
supported models and first-boot installation logs.
