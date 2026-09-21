# Kindle guest additions

Every Kindle image receives a Dropbear SSH server, key generator, client and
SCP executable. The image builder installs these in `/usr/sbin` and `/usr/bin`;
the source firmware is never changed.

## Binaries

`dropbear/` contains Dropbear 2026.94 binaries for the supported Kindle ABIs.
Each architecture directory includes its `LICENSE`.

| Directory | Guest userspace |
| --- | --- |
| `kindle5` | ARMv7 soft float: Kindle 4, Touch and Paperwhite 1 |
| `kindlepw2` | ARMv7 soft float: Paperwhite 2 and later with older firmware |
| `kindlehf` | ARMv7 hard float: firmware with `/lib/ld-linux-armhf.so.3` |

Selection follows the rootfs ABI, not the QEMU CPU architecture. The MediaTek
Kindles use the ARMv7 hard-float build even though QEMU emulates an ARM64 CPU.
These are dynamically linked binaries using the guest's matching loader/libc.
They support public-key authentication and SCP; password authentication and
SFTP are disabled in the supplied build.

## Startup and identity

`ssh/sshd.conf` replaces the stock Upstart SSH job. Kindle 4 instead receives
an init-supervised `sshd` entry in `/etc/inittab`. Both run `ssh/qemu-sshd`
in the foreground after persistent storage is available. Dropbear listens on
port 22 on all guest interfaces. The image builder permits incoming SSH in
the USB and Wi-Fi firewall rules.

The host generates one login identity at `build/ssh/id_ed25519`, shared by all
Kindles. Only the public key is embedded at `/etc/eink-ssh/authorized_keys`.
No private key is stored in this directory or committed to the repository.
Each guest generates its own persistent Ed25519 host key in
`/var/local/eink-ssh`. Framework permission changes exclude this directory.

See [networking](../docs/networking.md#kindle-ssh) for login commands, host port
options and service diagnostics. New additions and login keys participate in
the base-image cache key; existing saved disks remain unchanged.
