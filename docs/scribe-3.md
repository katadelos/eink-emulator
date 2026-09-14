# Kindle Scribe 3 (Paloma)

This board uses `mt8115-pa6-cs8,board=paloma`, four CPUs and 4 GiB RAM.
Its firmware platform is `platpa6`. It shares the MT8115 platform and
storage builder with [Scribe Colorsoft](scribe-colorsoft.md).
Support is at bring-up stage; ordinary catalogue launches have not completed
full Home acceptance.

```sh
./eink import /path/to/update.bin --model kindle-scribe-3
./eink create my-scribe-3 --model kindle-scribe-3 --profile dvt
./eink run my-scribe-3
```

## Firmware and profiles

Import requires KindleTool and e2fsprogs. It installs the six original boot
images, their signatures and decompressed rootfs under
`firmware/kindle-scribe-3`. Touch and connectivity firmware are extracted from
the original rootfs:

- `/lib/firmware/touch/focaltech_ts_fw_bw5c.bin`
- `/lib/firmware/soc2_2_ram_mcu_mt8171_mt6631_1_hdr.bin`

The selected touch controller is FocalTech. Profiles are `production` (DVT),
`dvt`, `evt` and `hvt1.1`. The board supplies a virtual identity;
no physical identity or account is required. Hardware phase selection does
not enable QEMU's separate `development-mode` property.

## Image and boot behavior

The shared `mt8115` builder creates an 8 GiB sparse disk with the stock
partition selectors. The original rootfs is preserved byte-for-byte, with
its AVB footer at the end of the system partition. Kernel, auxiliary firmware
and signatures are retained; userdata is fresh. No rootfs boot modifications,
Java tuning, OOBE provisioning or development-console bootstrap is installed.

If `firmware/kindle-scribe-3/waveform.img` is absent, the builder creates a
synthetic PA6 V5 waveform partition. A supplied waveform store is used
directly. Synthetic waveforms are emulator input, not factory calibration.
Serial uses the launching terminal; `--serial-socket` redirects it to the
instance socket and serial log.

The QEMU platform models display pipelines, fitted touch/sensor devices,
power controls and connectivity interfaces. WLAN association and network
traffic are unavailable. Earlier Home and suspend experiments depended on
local development boot scripts that are outside this core support set.
