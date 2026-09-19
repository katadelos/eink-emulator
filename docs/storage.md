# Machines and disk images

Instances share a base image and store their own changes in a writable disk:

```text
firmware/MODEL/                  Imported firmware
build/images/*.qcow2             Shared base images
machines/NAME/machine.json       Instance configuration
machines/NAME/disk.qcow2          Writable disk overlay
machines/NAME/NAME.qmp.sock       Optional QMP socket
machines/NAME/NAME.serial.sock   Optional serial socket
machines/NAME/NAME.serial.log    Serial output with --serial-socket
```

These files are ignored by Git. Image creation builds a temporary sparse raw
disk and converts it to a QCOW2 base. Each instance starts with an empty
QCOW2 overlay and uses more host space as the guest writes to it.

Changes to firmware or image-building code produce a new base. Existing
instances keep using the base they were created with.

[Oasis 1 and 2](oasis.md) each have 2 GiB of virtual storage. Their disk
files grow as needed rather than reserving the full amount on your Mac.

## Console sockets

`./eink run NAME --qmp-socket` creates the QMP socket. `--serial-socket`
redirects serial from the terminal to a socket and records output in a log.

Before launching, `eink` checks the instance's QMP socket. If QEMU is already
running, it reports that process instead of launching another one against
the same disk. A stale QMP socket is removed when starting a new QMP listener.
Serial sockets are left alone because they can be in use without QMP.
Remove a stale serial socket only after its QEMU process has exited.

## Scribe partitions

Both Scribe image builders create 8 GiB sparse disks. They use the partition
numbers expected by the firmware; partition sizes are chosen for emulation.

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

Scribe 1 and 2 use a prepared 768 MiB rootfs, with fresh pdata and varlocal
filesystems. Their ext4 userstore has fully initialized inode tables to
avoid discard errors during Linux 4.9's lazy initialization. The eMMC model
supports normal TRIM for the firmware's hibernate cleanup.

Scribe 3 and Colorsoft copy the original rootfs into a partition of exactly
the same size, keeping its AVB footer at the partition boundary. Both use a
fresh ext4 userstore. On all four Scribes, the userstore filesystem starts
8 KiB into its partition, as expected by the guest's loop device.

## KT4 partitions

[KT4](kt4.md) uses a sparse 2 GiB disk. Jaeger retains rootfs p8, varlocal p9
and userstore p10, plus its keys and hibernation partitions. The stock rootfs
has 512 MiB and local settings have 64 MiB; userstore fills the remaining
space. The emulated eMMC boot areas hold vendor BIOS and synthetic IDME
separately from the user-area GPT.

## KOA3 partitions

[KOA3](koa3.md) uses a sparse 2 GiB disk. Stinger retains the Zelda platform's
system p5, local settings p6 and userstore p7, as well as its absolute
hibernation and key regions. The stock rootfs has 512 MiB and local settings
have 64 MiB; userstore fills the remaining space. The emulated eMMC boot areas
hold vendor BIOS and synthetic IDME separately from the user-area GPT.

## Inventory and backups

`./eink list` shows the instances and whether their disks and bases exist.
`./eink images` lists image sizes, allocated host space and backing files.

To back up an instance, copy its complete `machines/NAME` directory and the
base named in `machine.json`. The overlay cannot be used without its base.
