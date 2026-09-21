# Machine state

`./eink create` makes one directory here per instance. Each directory contains
`machine.json` and a sparse QCOW2 overlay. Git ignores this runtime state.

Use `./eink list` to list instances and `./eink images` to list disks. See
[storage](../docs/storage.md) before moving or backing up an instance.
