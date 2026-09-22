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

MediaTek guests use the ARMv7 hard-float build even on an emulated ARM64 CPU.
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

## Optional KUAL and MRPI

`eink create --jailbreak`, `--kual` and `--mrpi` opt into the pinned inputs in
[`kindle/assets.json`](kindle/assets.json). Downloaded archives stay in the ignored
`kindle/downloads/` directory. See [Kindle add-ons](../docs/kindle-addons.md) for dependencies,
supported models and first-boot installation logs.
