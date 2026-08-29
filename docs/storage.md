# Machines and disk images

The storage layout separates immutable firmware-derived data from each
instance's writable state:

```text
firmware/MODEL/              User-supplied inputs; ignored by Git
build/images/*.qcow2         Cached read-only bases; ignored by Git
machines/NAME/machine.json   Instance configuration; ignored by Git
machines/NAME/disk.qcow2     Writable instance overlay; ignored by Git
machines/NAME/NAME.qmp.sock     Optional live QMP endpoint
machines/NAME/NAME.serial.sock  Optional live guest serial endpoint
```

Image construction uses a temporary sparse raw file and converts it to QCOW2.
Only the QCOW2 base is retained. Each instance disk is another QCOW2 layer
backed by that base, so a newly created instance consumes very little space.

Firmware changes produce a newly fingerprinted base instead of silently
altering existing instances. Existing instances continue to point at their
original base.

All models use the same endpoint convention. `./eink run NAME --qmp-socket`
creates the QMP endpoint and `--serial-socket` moves serial from the invoking
terminal to its endpoint. Including the instance name in both socket filenames
keeps endpoints unambiguous even when paths are copied out of their instance
directory.

Every run probes the instance's QMP endpoint before launch. If it is live, the
existing QEMU process is reused instead of starting another process against the
same disk. A refused QMP endpoint is removed when `--qmp-socket` requests a new
one. Serial endpoints are not removed automatically because serial can be live
without QMP; remove a stale serial socket only after confirming that its QEMU
process has exited.

## Inventory

`./eink list` reports every instance and whether both its disk and base are
present. `./eink images` reports all retained images, their virtual size,
allocated host space, and backing file.

Do not move an individual overlay without its manifest and backing base. To
archive an instance, copy its complete `machines/NAME` directory together
with the base named in `machine.json`.
