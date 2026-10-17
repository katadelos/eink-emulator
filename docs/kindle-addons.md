# Kindle add-ons

There are two ways to give an instance a jailbroken environment:

- **`create --jbsh`** (Paperwhite 2 and later): runs the payload that current
  real-device jailbreaks install. Use this to reproduce what users of a
  jailbroken Kindle have. See [Jailbreak with jb.sh](#jailbreak-with-jbsh).
- **`create --jailbreak`, `--kual` or `--mrpi`** (Kindle 4 through Oasis 3):
  prepare the jailbreak, and optionally KUAL and MRPI, offline while the
  image is built. Kindle 4, Touch and Paperwhite 1 need this route.

`--jbsh` cannot be combined with the other three flags.

## Build-time add-ons

Use `--mrpi` when creating a Kindle to install KUAL, MRPI and their jailbreak
prerequisites:

```sh
./eink create k4-dev --model kindle-4 --mrpi
./eink create pw4-dev --model kindle-paperwhite-4 --profile production --mrpi
./eink run k4-dev
```

| Flag | Components |
| --- | --- |
| `--jailbreak` | Developer update key, execution and debugging flags, and the MKK root helper on Touch and later |
| `--kual` | Jailbreak prerequisites and KUAL |
| `--mrpi` | Jailbreak prerequisites, KUAL and MRPI |

Supported models are Kindle 4, Touch, Paperwhite 1–4, Basic 2014/2016/2019,
Voyage and Oasis 1–3, using their final firmware. The builder selects the KUAL
Kindlet for K4, Touch and PW1, and the KUAL booklet for later models.

Add-ons are selected at creation. Create another instance to change its
selection. Offline setup is automatic with or without add-ons; see
[guest compatibility changes](guest-overrides.md).

## Host requirements

- K4, Touch and PW1: `openssl` and a JDK's `keytool` on `PATH` to prepare the
  KUAL Kindlet keystore.
- PW2 and later: [KindleTool](https://github.com/NiLuJe/KindleTool) on `PATH`
  to extract the KUAL and root-helper packages.

## Install a package

Copy an update `.bin` to `/mnt/us/mrpackages/`, open KUAL and choose
**Helper → Install MR Packages**. To run MRPI over SSH instead:

```sh
/bin/sh /mnt/us/extensions/MRInstaller/bin/mrinstaller.sh launch_installer
```

See [networking](networking.md#kindle-ssh) for SSH and file-transfer commands.

## Downloads

Archives are downloaded once to `guest-additions/kindle/downloads/`, grouped
by version and excluded from Git. The pinned URLs are defined in
[`assets.json`](../guest-additions/kindle/assets.json).

| Asset | Version and direct download |
| --- | --- |
| jailbreak | [1.8.N-r18977](https://storage.gra.cloud.ovh.net/v1/AUTH_2ac4bfee353948ec8ea7fd1710574097/mr-public/Touch/kindle-k4-jailbreak-1.8.N-r18977.tar.xz) |
| mkk | [20141129-r18833](https://storage.gra.cloud.ovh.net/v1/AUTH_2ac4bfee353948ec8ea7fd1710574097/mr-public/Touch/kindle-mkk-20141129-r18833.tar.xz) |
| hotfix | [2.5.0](https://github.com/KindleModding/Hotfix/releases/download/2.5.0/Update_hotfix_universal.bin) |
| kual_kindlet | [2.7.37-gfcb45b5-20250419](https://storage.gra.cloud.ovh.net/v1/AUTH_2ac4bfee353948ec8ea7fd1710574097/mr-public/KUAL/KUAL-v2.7.37-gfcb45b5-20250419.tar.xz) |
| kual_booklet | [c6ac782-20250419](https://storage.gra.cloud.ovh.net/v1/AUTH_2ac4bfee353948ec8ea7fd1710574097/mr-public/KUAL/KUAL-c6ac782-20250419.tar.xz) |
| mrpi | [1.7.N-r19303-khf-08f8c5a](https://media.githubusercontent.com/media/KindleModding/kindlemodding.github.io/08f8c5add11ce931123fbaf9417c87d9f1685415/content/jailbreaking/Legacy/post-jailbreak/installing-kual-mrpi/kual-mrinstaller-khf.zip) |
| jbsh | [2.2.1](https://github.com/KindleModding/jb.sh/releases/download/v2.2.1/jb.sh), SHA-256 checked on every use |

The Hotfix package supplies the root helper; its full installer is not run.
This setup does not provide jailbreak persistence through vendor firmware updates.

## Startup and troubleshooting

Installation finishes during the first boot, before the Kindle framework
starts. If KUAL is missing or installation fails, inspect
`/var/local/eink-addons/install.log` over SSH. Incomplete installation retries
at the next framework startup. Installed versions and source URLs are recorded
in the machine's `machine.json` and the guest's `/etc/eink-addons.json`.

The guest remains unregistered. On firmware that shows a registration
invitation on Home, use Library to access sideloaded books and KUAL.

## Jailbreak with jb.sh

[jb.sh](https://github.com/KindleModding/jb.sh) is the payload that current
jailbreaks run as root after their exploit. The emulator needs no exploit;
`--jbsh` installs the pinned script in the image and runs it once:

```sh
./eink create pw6-jb --model kindle-paperwhite-6 --profile production --firmware 5.20.1 --jbsh
./eink run pw6-jb
```

On the first boot, an Upstart task (`qemu-jbsh`) runs jb.sh when the
framework is about to start, and holds the framework until it finishes.
The script shows its progress on screen. Later boots skip the task, because
`/var/local/kmc/bin` exists. Failed runs retry on the next boot, at most
three times. The log is `/var/local/eink-addons/jbsh.log`.

On a real device, jb.sh runs from the running framework and then reboots,
so that the framework rereads what it installed: the update keys, the
Kindlet keystore, the `appreg.db` handlers and the patched command lists.
Here the framework has not started yet, so the reboot is redundant. A
`reboot` stub on jb.sh's `PATH` records the request instead. The pinned
script is unchanged. jb.sh's closing `mount -o exec /mnt/us` adds a second
FUSE userstore mount on top of the first, which a reboot would clear.
`qemu-jbsh` instead unmounts both and mounts the userstore once with
`exec`, as the stock userstore job does when `/MNTUS_EXEC` exists.

| Tested | Userspace | Time to jailbroken Home, one run |
| --- | --- | --- |
| Paperwhite 6, 5.20.1 | `kindlehf` | About 5 minutes |
| Basic 2016, 5.16.2.1.1 | `kindlepw2` | About 3 minutes |

To jailbreak an existing instance instead, copy the script in and run it
over SSH. It takes about 15 seconds when the guest is idle:

```sh
scp -O -i build/ssh/id_ed25519 -P 2222 \
  guest-additions/kindle/downloads/2.2.1/jb.sh root@127.0.0.1:/mnt/us/jb.sh
ssh -i build/ssh/id_ed25519 -p 2222 root@127.0.0.1 'sh /mnt/us/jb.sh 2>&1 | tee /mnt/us/jb-run.log'
```

The cached copy exists after any `--jbsh` build. Otherwise, download the
release from the table above and check its SHA-256 against `assets.json`.

jb.sh:

- installs the setuid root helper `gandalf` (`/var/local/kmc/bin/su`), FBInk
  and the KPM package manager under `/var/local/kmc/`;
- installs the developer update key and Kindlet keystore;
- adds the `/MNTUS_EXEC` flag, so `/mnt/us` is mounted without `noexec`;
- adds the `kmc` Upstart job, the `appreg.db` hooks and shell-script
  integration;
- renames `otaupd` and `otav3` to block updates;
- writes `/mnt/us/documents/JAILBROKEN.txt`.

It does not install KUAL. After the reboot, check with:

```sh
ssh -i build/ssh/id_ed25519 -p 2222 root@127.0.0.1 \
  'cat /mnt/us/documents/JAILBROKEN.txt; ls -l /var/local/kmc/bin/gandalf; status kmc; mount | grep " /mnt/us "'
```

The jailbreak is stored in the instance overlay. On a `--jbsh` instance,
`./eink reset` returns to the prepared image, so the next boot jailbreaks
again. On an instance jailbroken by hand, `reset` removes the jailbreak. To
start each test from the same jailbroken state, run with `-- -snapshot` (for
example `./eink run my-reader --headless -- -snapshot`); all guest writes are
discarded on exit.

On both tested models, the guest returned to Home, the userstore permitted
execution, the `kmc` job ran and the jailbreak survived reboots. Paperwhite 6
was also jailbroken by hand. One `chattr` warning about `gandalf` is
harmless; the flag is set.

The script skips its system patches when the kernel command line contains
`androidboot.veritymode`. Scribe 3 and Scribe Colorsoft images carry
`androidboot.veritymode=disabled`, so there it behaves as on a rootless
device. Other models and firmware versions are untested.
