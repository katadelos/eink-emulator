# Machines and disk images

Each instance stores its changes in a QCOW2 overlay. Instances can share a
read-only base image, which reduces disk use.

```text
firmware/MODEL/                 Imported firmware
build/images/*.qcow2            Shared base images
build/ssh/id_ed25519            Kindle SSH private key
build/ssh/id_ed25519.pub        Public key installed in Kindle images
machines/NAME/machine.json      Instance configuration
machines/NAME/disk.qcow2        Writable overlay
machines/NAME/NAME.qmp.sock     Optional QMP socket
machines/NAME/NAME.serial.sock  Optional serial socket
machines/NAME/NAME.serial.log   Serial log with --serial-socket
```

Git ignores runtime files. An overlay starts empty and grows as the guest
writes data.

Changes to firmware, builder code, guest files or the SSH public key cause
future instances to use a new base. Existing instances keep their original
base.

## Inventory and backups

`./eink list` shows instances and checks that their disks and bases exist.
`./eink images` shows virtual sizes, allocated host space and backing files.

Stop QEMU before copying an instance. Back up its complete `machines/NAME/`
directory and the base named in `machine.json`. Preserve their relative paths;
the overlay depends on its base. Keep the model's firmware directory because
launch still needs the bootloader and any separate machine firmware. Keep
`build/ssh/` for Kindle SSH access.

## Scribe partitions

Both Scribe builders create 8 GiB sparse disks. Partition numbers match the
firmware; sizes are selected for emulation.

| Partition | Scribe 1 / 2 (Bellatrix3) | Scribe 3 / Colorsoft (MT8115) |
| --- | --- | --- |
| 1 | Kernel | Kernel |
| 2 | Waveform | Waveform |
| 3 | Keys | Auxiliary firmware |
| 4 | Reserved | Persistent data |
| 5 | Persistent data | Diagnostics kernel |
| 6 | Snapshot | Diagnostics |
| 7 | Hibernate metadata | Keys |
| 8 | Rootfs | Reserved |
| 9 | Varlocal | Hibernate metadata |
| 10 | Userstore | Snapshot |
| 11 | — | System rootfs |
| 12 | — | Varlocal |
| 13 | — | Userstore |

Scribe 1/2 use a prepared 768 MiB rootfs and fresh pdata and varlocal filesystems.
Their ext4 userstore has fully initialized inode tables to avoid discard
errors during Linux 4.9 startup.

Scribe 3 and Scribe Colorsoft keep the source rootfs size and AVB footer at
the partition boundary, although [guest preparation](guest-overrides.md#scribe-3-and-colorsoft)
changes the filesystem contents. Both use a fresh ext4 userstore. On all
Scribes, the userstore filesystem starts 8 KiB into its partition, as required
by the guest loop device.

## KT4 partitions

[KT4](kt4.md) uses a 2 GiB sparse disk. Rootfs is p8 (512 MiB), varlocal is
p9 (64 MiB) and userstore is p10 (remaining space). The layout also retains
keys and hibernation partitions. Vendor BIOS and synthetic IDME are stored in
emulated eMMC boot areas, separate from the user-area GPT.

## KOA3 partitions

[KOA3](koa3.md) uses a 2 GiB sparse disk. System is p5 (512 MiB), local settings
are p6 (64 MiB) and userstore is p7 (remaining space). The layout retains
Zelda's absolute hibernation and key regions. As on KT4, vendor BIOS and
synthetic IDME use separate eMMC boot areas.
