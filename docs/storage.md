# Machines and disk images

Each instance stores its changes in a QCOW2 overlay. Prepared image revisions
share a read-only base for the same model and virtual disk size. A revision
stores only the blocks that differ from that base; identical image inputs
reuse the same revision.

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
future instances to use a new prepared revision. Existing instances keep their
original revision and contents. Revisions layer directly on a standalone
base, so a machine's backing chain has at most three images.

## Resetting an instance

Stop the instance, then run:

```sh
./eink reset NAME --dry-run
./eink reset NAME
```

Reset replaces the writable overlay with an empty one backed by the prepared
image recorded in `machine.json`. It restores the creation-time state,
including boot modifications and any add-ons baked into that image. Guest
files, settings and software installed after creation are discarded. First-boot
setup runs again on the next launch. The machine's name, configuration and
host logs are preserved; reset does not rebuild firmware or apply newer guest
overrides.

The replacement is created and checked before the old overlay is replaced.
Reset refuses running machines, disks opened by another process, symlinked
machine directories or disks, and overlays used as backing images by other
workspace disks, including snapshots in the same instance directory.

## Deleting instances and reclaiming space

Stop the instance, then run `./eink delete NAME`. This removes its directory
and prunes shared bases that no remaining disk uses. Use `--dry-run` to preview
the deletion. Instances with identical image inputs share a single base;
deleting one of them preserves that base until the last dependent disk is gone.

To reclaim old bases after manually removing instance directories:

```sh
./eink images --prune --dry-run
./eink images --prune
```

To deduplicate existing standalone base revisions, stop their instances and run:

```sh
./eink images --compact --dry-run
./eink images --compact
```

Compaction computes each revision's differences from the oldest standalone
base of the same model and disk size. It checks the new QCOW2 and compares all
guest-visible contents before atomically replacing the original, keeping its
path and every machine's data. It keeps the original if the result is not
smaller. Bases with internal snapshots, persistent bitmaps or external data
files are left alone. Compaction requires enough temporary space for one
revision's differences. Interrupted operations leave the original intact;
rerunning compaction processes the remaining standalone revisions.

Pruning checks machine manifests and actual QCOW2 backing chains throughout
the workspace, including snapshots and development disks outside `machines/`.
It recognizes QCOW2 disks with `.qcow2`, `.qcow`, `.img` and `.raw` extensions.
It requires `lsof` to preserve open bases and refuse deletion of files in use.
Symlinked bases are retained. An unreadable manifest or backing chain stops
cleanup before any deletion. Creation, reset, deletion, compaction and pruning are
serialized so cleanup cannot remove a base while an instance is being created.

Backups outside the workspace must include their bases as described below;
pruning cannot discover dependencies in external, stopped disks. Stop manual
QEMU/image operations before storage maintenance, since they do not take the
CLI's lock.

## Inventory and backups

`./eink list` shows instances and checks that their disks and bases exist. Its
`OVERLAY` column measures only the instance's writable disk. Both `list` and
`images` report total allocated host storage for `machines/` and `build/images/`,
counting shared bases once and including other files such as serial logs.
Imported firmware, QEMU builds and development directories are outside that
total. `./eink images` also shows virtual sizes and backing files; virtual
capacity is not allocated host space.

Stop QEMU before copying an instance. Back up its complete `machines/NAME/`
directory and every image in its backing chain, starting with the revision
named in `machine.json`. Inspect the complete chain with
`qemu/build/qemu-img info --backing-chain machines/NAME/disk.qcow2`.
Preserve their relative paths; each overlay depends on its backing image.
Keep the model's firmware directory because launch still needs the bootloader
and any separate machine firmware. Keep `build/ssh/` for Kindle SSH access.

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
