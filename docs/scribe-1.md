# Kindle Scribe 1 (Barolo)

Barolo uses `mt8113-bellatrix3,board=barolo`, 1 GiB RAM and the Bellatrix3
storage builder. Support is at bring-up stage; complete Home, touch and
suspend acceptance for this image configuration remains pending.

```sh
./eink import /path/to/update.bin --model kindle-scribe-1
./eink create my-scribe --model kindle-scribe-1 --profile dvt
./eink run my-scribe
```

Import requires KindleTool and e2fsprogs. It retains the original bootloader,
BL2, TEE, quickboot, kernel FIT, signatures and decompressed rootfs in
`firmware/kindle-scribe-1`. The image uses the original kernel and board DT.
No replacement kernel or automatic U-Boot console setup is included.

Profiles are `production` (DVT), `dvt`, `evt`, `evt-doe`, `hvt`, `hvt-a`
and `proto` (Proto2). The machine supplies a virtual board identity;
no physical device identity or account is required.

## Storage and display

The builder creates an 8 GiB sparse disk, preserving the stock partition
selectors: kernel p1, waveform p2, keys p3, pdata p5, snapshot p6,
hibernate metadata p7, rootfs p8, varlocal p9 and userstore p10. Intermediate
partition sizes and the unused p4 reservation are emulator geometry.

The imported rootfs remains unchanged. A temporary 768 MiB copy receives
[the guest setup](../guest-overrides/bellatrix3/README.md) before installation.
The host initializes pdata, varlocal and the ext4 userstore with compatible
filesystem features and initialized inode tables. The eMMC model supports
normal TRIM for stock hibernate-partition cleanup.

Without `firmware/kindle-scribe-1/waveform.img`, the builder generates an
explicitly synthetic HWTCON v2 waveform and installs it in FAT p2 and at
`/data/init_bin/wf_lut.gz`. A supplied waveform partition is used directly.
The display job preserves an already loaded stock HWTCON module; otherwise,
it loads the module with the selected waveform. These fixtures enable
emulated display updates and do not represent physical panel calibration.

## Guest setup

Generated images provide a supervised serial shell, USB Ethernet and telnet.
Serial uses the launching terminal; `--serial-socket` redirects it to the
instance socket and serial log. Connect to telnet at `127.0.0.1:2323`, or
select another forwarding port with `--telnet-port`. MTP is disabled because
it competes for the same USB gadget controller.

The setup initializes local OOBE completion and British English locale once,
with backups, and supplies the stock device-type override for the DVT board.
It creates no account registration. Permission initialization is moved before
services create shared files; existing persistent permissions migrate once.
A bounded keep-awake job refreshes the idle timer while the display is active
and preserves manual sleep. Java verification and compilation settings stay
as shipped. The framework readiness timeout is extended for TCG.

The timezone/registration capability gates are reused, and unavailable native
wireless and Minerva jobs are disabled. USB Ethernet supplies networking.
Stock SBIOS transfer deadlines can still cause storage errors under host
scheduling delays; replacement-kernel recovery is outside this support set.

[Scribe 2 (Pisco)](scribe-2.md) shares the platform with separate fitted hardware.
