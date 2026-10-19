# Agent guide

This repo runs stock Kindle, Kobo and Tolino firmware in QEMU. Use it to test
homebrew against specific device models and firmware versions. Everything goes
through `./eink`; run `./eink <command> --help` for options.

## Pick a model and firmware

```sh
./eink models                                   # Model IDs and required --profile values
./eink versions --model kindle-paperwhite-6     # Downloadable releases, newest first
```

`--firmware VERSION` (or `latest`) downloads, verifies and imports a release on
first use. It works for `kindle-basic-2014/2016`, `kindle-kt4`,
`kindle-basic-2022/2024`, `kindle-colorsoft`, `kindle-voyage`,
`kindle-oasis-1/2/3`, `kindle-paperwhite-2/3/4/5/6`, `kindle-scribe-1/2/3`,
`kindle-scribe-colorsoft` and the four `tolino-*` models.
Other models use manually supplied files in `firmware/MODEL/`; see
`docs/firmware.md`. Kindle downloads need KindleTool; Tolino downloads need
`zstd`.

## Create one instance per model/version

Instance names allow only `[a-z0-9_-]`, with no dots. Encode the version
without them:

```sh
./eink create pw6-5186 --model kindle-paperwhite-6 --profile production --firmware 5.18.6
./eink create pw6-5201 --model kindle-paperwhite-6 --profile production --firmware 5.20.1
./eink list                                     # FIRMWARE column shows the pinned version
```

The version is fixed at creation. To test another version, create another
instance. Instances with the same model, version and options share one base
image (~650 MB), so extra ones are cheap. Each new version adds a base image.

## Run headless

`./eink run` replaces itself with QEMU and blocks, so start it in the
background. Give each concurrent instance its own ports:

```sh
./eink run pw6-5186 --headless --serial-socket --qmp-socket --ssh-port 4022 --wifi-ssh-port 4023
```

- Serial log: `machines/NAME/NAME.serial.log`
- Control: `python3 scripts/eink-qmp.py --machine NAME status|screendump FILE.png|tap X Y|quit`
- `tap` uses a fixed 0..1272 × 0..1696 scale. Screenshot before and after
  to confirm the effect.
- `quit` kills QEMU without a guest shutdown. Run `sync` over SSH first if
  guest changes must persist.

## Wait for readiness actively

Measured on Paperwhite 6 with screenshots every 4 s:

- SSH answers 35–50 s after launch.
- The framework starts at about 65–85 s of guest uptime (`framework:starting`
  in the serial log).
- A boot progress bar shows from about 70–85 s, then a blank screen.
- Home appears 2½–3 minutes after launch.

Poll for the condition you need, with a deadline, and check the evidence:

```sh
ssh -o BatchMode=yes -o ConnectTimeout=3 -o StrictHostKeyChecking=no \
    -o UserKnownHostsFile=/dev/null -i build/ssh/id_ed25519 -p 4022 root@127.0.0.1 true
```

Confirm the UI with `screendump`. SSH being up does not mean Home is ready.

If SSH never answers, read the serial log:

- **Log ends with `Unmounting UserStore`**, with no `fs50` milestone: an
  intermittent first-boot stall, seen once in four fresh boots. `quit` and
  `run` again; the next boot succeeded.
- **`couldn't find an available UDC - added [g_ether]`**: another USB gadget
  claimed the controller, so USB networking is down.

## Deploy and test homebrew

SSH logs in as root on every Kindle image. The guest has no SFTP, so `scp`
needs `-O`:

```sh
KEY="-i build/ssh/id_ed25519 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
scp -O $KEY -P 4022 ./myapp root@127.0.0.1:/mnt/us/
ssh $KEY -p 4022 root@127.0.0.1 '/mnt/us/myapp; echo exit=$?'
```

(In zsh, use a bash wrapper or write the options out; zsh does not
word-split `$KEY`.)

- On a stock guest, `/mnt/us` is mounted `noexec`, as on a real device.
  Binaries there fail with `Permission denied`; scripts run only as
  `sh /mnt/us/script.sh`. Jailbreak the instance (below) to test homebrew
  as users run it.
- Userstore: `/mnt/us` on Kindle, `/mnt/onboard` on Kobo and Tolino. Kobo
  uses telnet on port 2323 instead of SSH.
- Check the userspace ABI on each instance; it can change between firmware
  versions of one model. If `ls /lib/ld-linux-armhf.so.3` succeeds, build
  ARMv7 hard-float; otherwise build soft-float. This applies even on ARM64
  machines.
- `cat /etc/version.txt` confirms the running firmware build.

## Match a jailbroken device

Real users run homebrew on jailbroken Kindles, so test there too.

- **Paperwhite 2 and later:** add `--jbsh` to `create`. It runs jb.sh, the
  payload that current jailbreaks install, during the first boot, before
  the framework starts. You get:
  - `/mnt/us` mounted executable;
  - a setuid `su` at `/var/local/kmc/bin/su`;
  - FBInk and KPM in `/var/local/kmc/bin/`;
  - developer update keys and blocked OTA updates.

  It does not install KUAL.
- **Kindle 4 through Oasis 3:** use `create --jailbreak`, `--kual` or
  `--mrpi`. These are prepared offline at build time and target final
  firmware. Kindle 4, Touch and Paperwhite 1 need this route.

```sh
./eink create pw6-5201-jb --model kindle-paperwhite-6 --profile production --firmware 5.20.1 --jbsh
```

The framework then starts already jailbroken, so no extra boot or second
`run` is needed:

| Tested | Time to jailbroken Home, one run |
| --- | --- |
| Paperwhite 6, 5.20.1 | About 5 minutes |
| Basic 2022, 5.16.3 | About 3 minutes |
| Basic 2016, 5.16.2.1.1 | About 3 minutes |

Confirm the jailbreak before testing. If `/var/local/kmc/bin` is missing,
read `/var/local/eink-addons/jbsh.log`:

```sh
cat /mnt/us/documents/JAILBROKEN.txt
```

To jailbreak an existing instance instead, run the script over SSH; see
`docs/kindle-addons.md#jailbreak-with-jbsh`.

## Reset between tests

```sh
./eink run NAME --headless -- -snapshot         # Throwaway run; all guest writes discarded on exit
./eink reset NAME                               # Back to the prepared image
./eink delete NAME                              # Remove the instance and unused base images
```

Keep a launcher option such as `--headless` between `NAME` and `--`.

For a jailbroken baseline, finish the `--jbsh` first boot normally, then use
`-- -snapshot` for every test run; each run then starts jailbroken. Starting
with `-snapshot` before the jailbreak completes repeats it on every run.
After `reset`, a `--jbsh` instance jailbreaks again on its next boot. On a
hand-jailbroken instance, `reset` removes the jailbreak.

## When older firmware fails to build

The image builders patch stock startup files and stop when a pattern is
missing, e.g. `stock userstore ext4 mount command was not found exactly once`.
Patches are in `eink_emulator/images/rootfs.py`. Make the pattern accept both
the old and new forms instead of loosening it, and keep current firmware
unchanged. Then delete and recreate the instance; base images rebuild
automatically when builder code changes. Note version-specific changes in
`docs/guest-overrides.md`.

## Repo map

- `models.json`: model catalogue (QEMU machine, firmware roles,
  `ftvdb_package`, `recovery_import`)
- `eink_emulator/cli.py`: commands. `eink_emulator/ftvdb.py`: release lookup
  and download
- `eink_emulator/images/`: per-family disk builders.
  `guest-overrides/`: files installed into guests
- `firmware/MODEL/`: manual firmware. `firmware/versions/MODEL/VERSION/`:
  downloaded firmware. `machines/NAME/`: instances. `build/`: QEMU, base
  images, SSH key
