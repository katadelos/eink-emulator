# Kindle add-ons

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
