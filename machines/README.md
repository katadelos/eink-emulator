# Machine state

`./eink create` stores each persistent machine in a subdirectory here. The
contents are runtime state and are ignored by Git. Each directory contains a
small JSON manifest and a sparse QCOW2 overlay.

Use `./eink list` for the machine inventory and `./eink images` for the full
disk-image inventory.
