# QMP inspection

QMP controls a running emulator. Use it to inspect a failed boot before
restarting and losing the device state.

## Connect

```sh
./eink run NAME --qmp-socket
```

In another terminal:

```sh
python3 scripts/eink-qmp.py --machine NAME status
```

The socket is `machines/NAME/NAME.qmp.sock`. For another socket, replace
`--machine NAME` with `--socket /absolute/path/to/qmp.sock`.

Serial stays in the launching terminal. To move it to a socket, start QEMU
with `--serial-socket` as well:

```sh
./eink run NAME --qmp-socket --serial-socket
```

Then connect from another terminal:

```sh
socat -,raw,echo=0 UNIX-CONNECT:machines/NAME/NAME.serial.sock
```

A second `run NAME` reports the active QMP process and exits; it does not
attach to its console. QMP sockets are removed before a new listener starts.
Serial sockets are left in place because they can be active without QMP.
Remove a stale serial socket only after its QEMU process exits.

## Common commands

Use `python3 scripts/eink-qmp.py --machine NAME` followed by a command:

| Command | Effect |
| --- | --- |
| `status` | Report whether the guest is running or paused |
| `stop` / `cont` | Pause / resume execution |
| `quit` | Exit QEMU without a guest shutdown |
| `screendump /tmp/eink.png` | Save guest pixels to a host file |
| `qmp query-cpus-fast` | Query CPUs through QMP |
| `hmp info registers -a` | Read CPU registers through the monitor |
| `memory ADDRESS --words 16` | Read guest memory |
| `map ADDRESS SIZE --cpu 0` | Translate virtual pages to physical addresses |
| `dump ADDRESS SIZE /tmp/region.bin` | Save guest memory to a host file |

Memory addresses are virtual unless `--physical` is set for `memory` or
`dump`. `map` pauses the guest during translation and restores its prior
run state. For related manual reads, use `stop`, collect the data, then `cont`.

For example, capture a screenshot or pass arguments to a QMP command:

```sh
python3 scripts/eink-qmp.py --machine NAME screendump /tmp/eink.png
python3 scripts/eink-qmp.py --machine NAME qmp trace-event-set-state \
  --arguments '{"name":"mt8113_gce_*","enable":true}'
```

## Bellatrix hardware state

These commands use MT8110/MT8113 Bellatrix device paths and memory addresses.
They apply to Basic 2022/2024, Paperwhite 5/6, Colorsoft and Scribe 1/2.

| Command | Use |
| --- | --- |
| `display` | Check framebuffer layout and update counters |
| `machine` | Check board identity and the Colorsoft CFA patch |
| `snapshot --output /tmp/state.json` | Capture CPU and device state during one pause |
| `sample --count 3 --interval 2` | Repeat snapshots to check progress |
| `observe-display --changes-only` | Record display changes while the guest runs |
| `tap X Y` | Inject a touchscreen press |

`snapshot` and `sample` restore the guest's prior run state. For boot display
transitions, record screenshots without pausing:

```sh
python3 scripts/eink-qmp.py --machine NAME observe-display \
  --changes-only --count 1200 --interval 0.05 \
  --screenshots /tmp/display-events --output /tmp/display-events.json
```

`--changes-only` polls `pipeline-triggers` and captures more data only when
it changes. This reduces the effect of inspection on guest execution.

### Missing or distorted display

1. Run `status` and `display`.
2. Take a `screendump`. If its pixels are correct, inspect the host display.
   Otherwise, check the framebuffer address, pitch, format and rotation.
3. Take a `snapshot` before changing state, so CPU and device data can be
   compared at the same point in execution.

The display counters should satisfy:

```text
mdp-transactions = mdp-writebacks + mdp-writeback-skips + mdp-writeback-failures
```

Investigate nonzero failures. Monochrome Y8 transactions normally write back;
Colorsoft skips RGBA/CFA source transactions because Cocoa displays that source
directly. On Colorsoft, `scanout-refreshes` advances at waveform commits.

| Property | Meaning |
| --- | --- |
| `last-pipeline-flags` | `0x1`: full update; `0x2`: Y5 input; `0x8000`: working-buffer clear |
| `last-frame-min`, `last-frame-max` | Sampled minimum and maximum values from the update region; helps identify uniform updates |
| `boot-handoff-arms`, `boot-blank-retentions` | Track splash retention during boot |

### Slow boot or display timeout

Use `sample` to check progress and `hmp info jit` to inspect TCG code-cache
pressure. A CPU waiting for a missing device response can resemble slow
execution; compare CPU locations and device counters across samples.

`[HWTCON ERR] wait marker[...] mdp submit timeout` is a guest kernel message.
It does not by itself prove a lost interrupt. Compare later counter changes
and writeback failures. If needed, enable `mt8113_gce_*` and
`mt8113_hwtcon_mdp_source` with `trace-event-set-state`, as shown above.
Compare trace and serial timestamps, then disable tracing with `"enable":false`.

### Touch

`tap X Y` maps X from `0..1272` and Y from `0..1696` to the full pointer range.
The helper uses this fixed scale; coordinates are not necessarily pixels on
other panel sizes. Compare screenshots before and after a tap to check the
guest response. Test a Cocoa click separately to verify host input delivery.
