# Machine state

`./eink create` makes one directory here per instance. Each directory contains
`machine.json` and a sparse QCOW2 overlay. Git ignores this runtime state.

Use `./eink list` to list instances and `./eink images` to list disks. See
[storage](../docs/storage.md) before moving or backing up an instance.

Use `./eink reset NAME` to discard guest changes and restore the original
prepared image, including its boot modifications and preinstalled add-ons.

Use `./eink delete NAME` to remove a stopped instance and reclaim unused shared
bases. After manual deletions, run `./eink images --prune` to reclaim them.
