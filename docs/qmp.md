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

## Bellatrix hardware state

The remaining commands understand the shared MT8110/MT8113 Bellatrix device
models used by Kindle Basic 5, Kindle Basic 6, Colorsoft, and Paperwhite 6.
They were the most effective probes during bring-up because they expose device
contracts directly rather than inferring them from delayed serial output.

```sh
python3 scripts/eink-qmp.py --machine pw12 display
python3 scripts/eink-qmp.py --machine pw12 machine
python3 scripts/eink-qmp.py --machine pw12 snapshot \
  --output /tmp/pw12-state.json
python3 scripts/eink-qmp.py --machine pw12 sample \
  --count 3 --interval 2 --output /tmp/pw12-samples.json
python3 scripts/eink-qmp.py --machine kt5 observe-display \
  --changes-only --count 1200 --interval 0.05 \
  --screenshots /tmp/kt5-display-events \
  --output /tmp/kt5-display-events.json
```

`display` reports the active and base scanout addresses, guest virtual address,
source and output dimensions, pitch, pixel format, rotation, MDP transaction
and writeback counts, writeback failures, CFA source reports, refresh and
capture counts, and scanout read failures. This is the quickest way to
distinguish a bad framebuffer address or layout from a UI that simply has not
drawn yet. `mdp-transactions` should equal `mdp-writebacks` plus
`mdp-writeback-skips` plus `mdp-writeback-failures`. Monochrome devices normally
write back every Y8 transaction; Colorsoft legitimately counts its RGBA/CFA
source transactions as skips because Cocoa presents the CFA source directly.
Zero failures is the important contract check. Width, pitch, format, and
rotation then explain wrapping or distortion.

`observe-display` leaves the VM running while correlating HWTCON pipeline and
waveform counters with screendumps. Use `--changes-only` for boot transitions:
it polls only `pipeline-triggers` between updates, then captures the full small
display-state set and a screenshot when that counter changes. This perturbs TCG
far less than taking a screendump and querying every property on every sample.
The last pipeline flags use the driver contract (`0x1` full update, `0x2` Y5
input, `0x8000` working-buffer clear); the last LUT and frame minimum/maximum
show whether an update was ordinary artwork, uniform staging content, or a
clear. `boot-handoff-arms` and `boot-blank-retentions` make MT8110 splash
retention and Colorsoft's CFA handoff directly observable. On Colorsoft,
`scanout-refreshes` advances on waveform commits rather than continuously;
that distinction is useful when a guest staging framebuffer differs from the
image retained by the physical e-ink panel.

`machine` reports the selected board and hardware profile, its board ID,
product name, and device type. On Colorsoft it also reports whether the CFA
runtime patch was applied, its matched addresses, and its attempt count. This
makes identity and runtime-hook failures visible without waiting for their
downstream boot timeouts.

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
   larger Bellatrix translation-block cache.
3. Check timer, DVFSRC, GCE, interrupt, and device state in the synchronized
   snapshots before treating a delay as inherent TCG performance. A stable
   wait can be a missed driver contract or timeout rather than expensive guest
   work.

For touch diagnosis, `tap X Y` injects one QEMU absolute-pointer click through
the selected Bellatrix model's emulated touchscreen controller. Compare device
counters and a subsequent screendump to separate input delivery from UI
redraw. Use actual Cocoa clicks for the final host-input test; an injected QMP
tap proves the guest hardware path, not the Cocoa event path.

Lines such as `[HWTCON ERR] wait marker[...] mdp submit timeout` come from the
guest kernel, not QEMU tracing. The stock marker wait is only 100 ms. If the
marker still reports state `0`, QMP counters later advance, and writeback
failures remain zero, the task missed that advisory deadline before entering
MDP; it does not establish a lost emulated interrupt. When the distinction is
unclear, enable the existing GCE and MDP tracepoints on the running process and
correlate them with the serial timestamp:

```sh
python3 scripts/eink-qmp.py --machine NAME qmp trace-event-set-state \
  --arguments '{"name":"mt8113_gce_*","enable":true}'
python3 scripts/eink-qmp.py --machine NAME qmp trace-event-set-state \
  --arguments '{"name":"mt8113_hwtcon_mdp_source","enable":true}'
```

Disable the same events with `"enable":false` after collecting the relevant
burst. This keeps tracing attached to the existing slow-to-boot process.

Keep the slow machine alive while investigating. QMP status, snapshots, memory
inspection, screen capture, and input injection all operate on the existing
process, which avoids repeating the roughly minute-long Bellatrix boot.
