# Networking and SSH

Kindle, Kobo and Tolino images start USB Ethernet automatically. To use Wi-Fi,
select the open `Kindle-QEMU` access point in the guest. Both interfaces can run
at the same time. [PocketBook Wi-Fi](#pocketbook-wi-fi) uses its own radio profiles.
[Guest configuration changes](guest-overrides.md) require a new instance.

## Kindle SSH

Connect over USB after boot:

```sh
ssh -i build/ssh/id_ed25519 -p 2222 root@127.0.0.1
```

After the guest joins Wi-Fi, the same command works on port 2223. For file
transfer, select the SCP protocol with `-O`; the guest has no SFTP server:

```sh
scp -O -i build/ssh/id_ed25519 -P 2222 book.txt root@127.0.0.1:/mnt/us/
```

The first Kindle image build creates one Ed25519 login key at
`build/ssh/id_ed25519`. All Kindle images use its public key. SSH accepts
public keys only. Keep the private key when you clean build files, or you
will lose this login method for existing instances.

Each guest creates a separate server key in `/var/local/eink-ssh` on first
boot. If you run different instances on the same port, use `HostKeyAlias`
to keep their host records separate:

```sh
ssh -i build/ssh/id_ed25519 -p 2222 -o HostKeyAlias=my-reader root@127.0.0.1
```

Logs are in `/var/log/sshd.log`. On Kindle Touch and later, use
`initctl status sshd` or `restart sshd` from serial to inspect or restart the
service. [Guest additions](../guest-additions/README.md) documents startup
and binary selection.

## Kobo telnet

Kobo images provide USB telnet:

```sh
telnet 127.0.0.1 2323
```

## Tolino SSH

[Tolino Vision Color](tolino-vision-color.md) and
[Shine 5 / Shine Color](tolino-shine.md) use the same local login key and
USB SSH port as Kindle images. Their stock OpenSSH server also provides SFTP:

```sh
scp -i build/ssh/id_ed25519 -P 2222 book.epub root@127.0.0.1:/mnt/onboard/
```

The USB startup hook writes `resolv.conf.head` so dhcpcd preserves the USB
DNS server when Wi-Fi connects or disconnects.

## PocketBook Wi-Fi

Select the open access point in the guest's Wi-Fi settings. The original network
manager handles association and DHCP; the guest uses `10.0.2.15`, with gateway
`10.0.2.2` and DNS `10.0.2.3`.

| Models | Radio | Access point |
| --- | --- | --- |
| 360 Plus New 512, Basic 611, Touch 622, Touch Lux 623, Ultra 650 | BCM43362 SDIO | `Kindle-QEMU` |
| Basic Lux 4 618, Verse Lite 619, Touch Lux 5 628, Verse 629, Touch HD 3 632, Color 633, Verse Pro 634, Era 700, InkPad 3 740, InkPad 3 Pro 740-2, InkPad Color 741, InkPad Lite 970, InkPad X 1040 | XR819 SDIO | `PocketBook-QEMU` |
| Touch Lux 4 627, Color Lux 801 | RTL8188EU USB | `Kindle-QEMU` |
| Era Color 700K3, InkPad Color 3 743K3 | AIC8800 SDIO | `PocketBook-QEMU` |

The Basic 613 has no Wi-Fi hardware. PocketBook images do not start an SSH server;
use the serial console for a root shell. Their Wi-Fi forward uses `--ssh-port`
(default 2222), because these models have no USB Ethernet backend. WPA and physical
radio behavior are not implemented.

## Host ports

All launcher forwards bind to `127.0.0.1`. Choose unused ports when you run
several instances. Models with both network interfaces also reserve a Wi-Fi
forward on port 2223, even when the guest has no SSH server.

| Option | Default | Service |
| --- | --- | --- |
| `--ssh-port PORT` | 2222 | Kindle / Tolino USB SSH |
| `--wifi-ssh-port PORT` | 2223 | Wi-Fi SSH forward |
| `--telnet-port PORT` | 2323 | Kobo USB telnet |

```sh
./eink run my-reader --ssh-port 4022 --wifi-ssh-port 4023
ssh -i build/ssh/id_ed25519 -p 4022 root@127.0.0.1
```

## Addresses and routing

| Interface | Guest address | Gateway | DNS |
| --- | --- | --- | --- |
| Wi-Fi | DHCP, normally `10.0.2.15/24` | `10.0.2.2` | `10.0.2.3` |
| USB | `192.168.15.244/24` | `192.168.15.201` | `192.168.15.3` |

Each interface has a separate QEMU user-network backend. Wi-Fi is usually
`wlan0`. Aura HD, Glo HD, Clara HD, Forma and PocketBooks use `eth0`.
USB is `usb0`.

Kindle images assign the USB default route metric 2048. Wi-Fi events and DHCP
completion restore USB routes and DNS after the stock network manager changes
them. This keeps USB access available during Wi-Fi changes. Kobo uses
`resolv.conf.tail` to retain USB DNS. Elipsa 2E uses configfs RNDIS because its
kernel has no `g_ether` module.

## USB ADB forwarding

MT8110 and MT8113 models accept `--usb-adb-port` for a local host connection to
an ADB USB function:

```sh
./eink run my-reader --usb-adb-port 5666
adb connect 127.0.0.1:5666
```

The guest must configure the FunctionFS ADB endpoints and run an authenticating
`adbd` with the host key authorized. The bridge carries bytes through the guest
USB controller; it does not enable the daemon's TCP listener. The host socket
binds only to `127.0.0.1`. USB gadget disconnect closes the host connection;
connect again after the gadget is configured. Use a port outside 5555–5585,
which the host `adb` server scans automatically for Android emulators.

## Wi-Fi diagnosis from serial

Prefer the guest Wi-Fi controls, which also start DHCP. For manual association
on Kindle firmware:

```sh
wpa_cli -i wlan0 add_network
wpa_cli -i wlan0 set_network 0 ssid Kindle-QEMU
wpa_cli -i wlan0 set_network 0 key_mgmt NONE
wpa_cli -i wlan0 select_network 0
```

Replace `0` with the ID returned by `add_network`. Kindle's `wpa_cli` adds SSID
quotes itself. Keep `ap_scan=2` on AR6003 devices; `ap_scan=1` exposes a bug in
their stock supplicant. MediaTek manual probes used `ap_scan=1`.

Kobo uses standard SSID syntax. For example, use
`set_network 0 ssid 4b696e646c652d51454d55` for the hex form of `Kindle-QEMU`.

## Device matrix

| Models | Wi-Fi transport | USB Ethernet |
| --- | --- | --- |
| Kindle 4, Touch, Paperwhite 1–3, Basic 2014, Voyage | AR6003 SDIO | ChipIdea `g_ether` |
| Basic 2016, Oasis 2, Paperwhite 4 | BCM43430 FullMAC SDIO | ChipIdea `g_ether` |
| Oasis 1/3, KT4 | Broadcom FullMAC SDIO | ChipIdea `g_ether` |
| Paperwhite 5, Basic 2022/2024 | MediaTek CONNAC DMA | MT8110 `g_ether` |
| Scribe 1/2, Paperwhite 6, Colorsoft | MediaTek CONNAC DMA | MT8113 `g_ether` |
| Scribe 3, Scribe Colorsoft | MT8171 CONNAC DMA | MTU3 `g_ether` / ECM |
| Kobo Mini, Touch, Aura HD, Glo HD | BCM43362 FullMAC SDIO | ChipIdea `g_ether` |
| Kobo Clara HD | RTL8189FS SDIO | ChipIdea `g_ether` |
| Kobo Forma | RTL8192ES SDIO | ChipIdea `g_ether` |
| Kobo Elipsa 2E | MediaTek CONNAC DMA | MT8113 configfs RNDIS |
| Tolino Vision Color | MediaTek CONNAC DMA | MT8113 configfs RNDIS |
| Tolino Shine 5 / Shine Color / Shine 5 TPV | MediaTek CONNAC DMA | MT8113 configfs RNDIS |

## Verification and limits

The 20 September 2026 audit recorded concurrent Wi-Fi and USB traffic on all
26 models. Checks covered Wi-Fi association, DHCP and gateway packets, plus
separate USB gateway packets. Runs used temporary `-snapshot` disks, including
fresh builder output. Local command, serial and packet logs are under
`build/network-audit/2026-09-20-fixes/`; they are not distributed in Git.

Reconnect checks covered all radio families, but some required manual
`wpa_cli reconnect`. These do not prove automatic reconnection or saved
profiles. Selected models also passed USB route/DNS restoration and cable
reconnection checks. MediaTek models passed DNS and HTTP transfers.

WPA, a configurable access point and physical radio behavior are not
implemented. Deep-suspend recovery and every firmware/profile combination
have not been tested. Network results do not establish Amazon registration
or complete GUI operation.
