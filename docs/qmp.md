# QMP inspection

QMP is the reliable control and inspection path for a running emulator. It can
query CPU and device state, capture the scanout, pause the guest for a coherent
snapshot, and control a long-running process without rebooting it.

## Enable an endpoint

QMP is opt-in for every persistent model:

```sh
./eink run NAME --qmp-socket
```

Serial remains attached to that `eink` process. Add `--serial-socket` only when
serial must be accessed by a separate process:

```sh
./eink run NAME --qmp-socket --serial-socket
```

The endpoints are deterministic and scoped by instance name:

```text
machines/NAME/NAME.qmp.sock
machines/NAME/NAME.serial.sock
```

Starting two differently named instances therefore cannot collide. A later
`./eink run NAME` probes the known QMP endpoint and keeps using the live QEMU
process rather than attempting another boot against its disk.

The QMP client accepts either the instance name or an explicit path. One is
required:

```sh
python3 scripts/eink-qmp.py --machine NAME status
python3 scripts/eink-qmp.py --socket /absolute/path/to/qmp.sock status
```

## Commands that work on every model

These commands use standard QMP or HMP facilities:

```sh
# Process state and lifecycle
python3 scripts/eink-qmp.py --machine NAME status
python3 scripts/eink-qmp.py --machine NAME stop
python3 scripts/eink-qmp.py --machine NAME cont
python3 scripts/eink-qmp.py --machine NAME quit

# Standard QMP and monitor commands
python3 scripts/eink-qmp.py --machine NAME qmp query-cpus-fast
python3 scripts/eink-qmp.py --machine NAME hmp info registers -a
python3 scripts/eink-qmp.py --machine NAME hmp info jit

# Guest pixels, without Cocoa scaling, decorations, or cursor state
python3 scripts/eink-qmp.py --machine NAME screendump /tmp/eink.png
```

Use `qmp COMMAND --arguments '{...}'` for an arbitrary QMP command. Use `hmp`
for monitor-only facilities such as register dumps, `info jit`, `gva2gpa`, and
physical memory reads. The client performs the QMP greeting and capability
negotiation and matches replies by request ID, so asynchronous events do not
get mistaken for command responses.

The `memory`, `map`, and `dump` commands are also general inspection tools:

```sh
python3 scripts/eink-qmp.py --machine NAME memory 0xADDRESS --words 16
python3 scripts/eink-qmp.py --machine NAME memory 0xADDRESS --physical
python3 scripts/eink-qmp.py --machine NAME map 0xVIRTUAL 0xSIZE --cpu 0
python3 scripts/eink-qmp.py --machine NAME dump 0xADDRESS 0xSIZE /tmp/region.bin
```

`map` pauses and resumes a running guest while translating pages. For several
related manual reads, issue `stop`, collect the state, and always issue `cont`
afterward. Do not leave a machine paused unintentionally.

## Colorsoft hardware state

The remaining commands understand the Colorsoft MT8113 model. They were the
most effective probes during bring-up because they expose device contracts
directly rather than inferring them from delayed serial output.

```sh
python3 scripts/eink-qmp.py --machine colorsoft display
python3 scripts/eink-qmp.py --machine colorsoft machine
python3 scripts/eink-qmp.py --machine colorsoft snapshot \
  --output /tmp/colorsoft-state.json
python3 scripts/eink-qmp.py --machine colorsoft sample \
  --count 3 --interval 2 --output /tmp/colorsoft-samples.json
```

`display` reports the active scanout address, guest virtual address, source and
output dimensions, pitch, pixel format, rotation, MDP transaction count, CFA
source reports, refresh and capture counts, and scanout read failures. This is
the quickest way to distinguish a bad framebuffer address or layout from a UI
that simply has not drawn yet. In particular, an advancing refresh count with
zero read failures confirms that QEMU can read the guest buffer; width, pitch,
format, and rotation then explain wrapping or distortion.

`machine` reports whether the Colorsoft CFA runtime patch was applied, the
matched address and attempt count, and the emulated IDME device type. It makes
runtime-hook failures visible without waiting for their downstream boot
timeouts.

`snapshot` briefly pauses a running guest, then collects mutually consistent
process status, CPU locations, register-derived stacks, machine and display
properties, active GCE threads, and the APXGPT, DVFSRC, IOMMU, GCE, HWTCON, and
MDP RDMA MMIO regions. It resumes the guest in a `finally` path. `sample`
repeats the same pause-safe capture and is useful for finding a CPU, GCE thread,
or counter that is making no progress.

## Workflows that save a reboot

For a missing or distorted display:

1. Run `status`, then `display` to validate the scanout contract.
2. Take a QMP `screendump`. If it is correct, investigate Cocoa presentation;
   if it is wrong, continue with pitch, format, rotation, and source geometry.
3. Capture a `snapshot` before changing state so CPU, IOMMU, GCE, HWTCON, and
   RDMA evidence can be compared together.

For unexpectedly slow boot or long pauses:

1. Use `sample` to determine whether CPUs and device counters are progressing.
2. Run `hmp info jit` to inspect TCG code-cache use, flushes, and direct block
   chaining. This previously identified code-cache pressure and justified the
   larger Colorsoft translation-block cache.
3. Check timer, DVFSRC, GCE, interrupt, and device state in the synchronized
   snapshots before treating a delay as inherent TCG performance. A stable
   wait can be a missed driver contract or timeout rather than expensive guest
   work.

For touch diagnosis, `tap X Y` injects one QEMU absolute-pointer click through
the emulated Colorsoft FT5536G controller. Compare device counters and a
subsequent screendump to separate input delivery from UI redraw. Use actual
Cocoa clicks for the final host-input test; an injected QMP tap proves the
guest hardware path, not the Cocoa event path.

Keep the slow machine alive while investigating. QMP status, snapshots, memory
inspection, screen capture, and input injection all operate on the existing
process, which avoids repeating the roughly minute-long Colorsoft boot.
