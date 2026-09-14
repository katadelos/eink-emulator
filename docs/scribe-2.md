# Kindle Scribe 2 (Pisco)

Pisco uses `mt8113-bellatrix3,board=pisco`, 1 GiB RAM and the same storage and
[guest setup as Scribe 1](scribe-1.md). Support is at bring-up stage;
complete Home, touch and suspend acceptance remains pending.

```sh
./eink import /path/to/update.bin --model kindle-scribe-2
./eink create my-scribe-2 --model kindle-scribe-2 --profile dvt
./eink run my-scribe-2
```

Only `production` and `dvt` are exposed; both select the source-confirmed DVT
configuration. Import retains the original five boot images, signatures and
768 MiB rootfs under `firmware/kindle-scribe-2`. The original kernel FIT and
board DT are used without replacement-kernel boot support.

Generated images include synthetic waveform support unless `waveform.img`
is supplied, a supervised serial shell, USB Ethernet/telnet, one-time local
OOBE/locale setup, permission initialization and a bounded keep-awake job.
The stock device-type override is seeded with `A3TY6T3X94EBV6` because the
firmware's production lookup table omits the DVT serial tattoo. Valid existing
overrides are retained. Java verification and compilation remain unchanged.

Serial uses the launching terminal by default; opt into socket/log redirection
with `--serial-socket`. Telnet forwards from `127.0.0.1:2323`; use `--telnet-port`
to select another host port. Native WLAN is incomplete.

The partition selectors and ext4 userstore layout match Barolo. Normal eMMC
TRIM supports stock hibernate-partition cleanup. Stock SBIOS deadlines can
still produce storage errors under host scheduling delays. The excluded
development-kernel recovery path is not required or automatically selected.
