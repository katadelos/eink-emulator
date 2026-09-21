# Networking and SSH

New images start USB Ethernet automatically. To use Wi-Fi, select the open
`Kindle-QEMU` access point in the guest. Both interfaces can run at the same
time. [Guest configuration changes](guest-overrides.md) require a new instance.

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

## Host ports

All launcher forwards bind to `127.0.0.1`. Choose unused ports when you run
several instances. Each instance also reserves a Wi-Fi forward on port 2223,
even when its guest has no SSH server.

| Option | Default | Service |
| --- | --- | --- |
| `--ssh-port PORT` | 2222 | Kindle USB SSH |
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
`wlan0`; Forma uses `eth0`. USB is `usb0`.

Kindle images assign the USB default route metric 2048. Wi-Fi events and DHCP
completion restore USB routes and DNS after the stock network manager changes
them. This keeps USB access available during Wi-Fi changes. Kobo uses
`resolv.conf.tail` to retain USB DNS. Elipsa 2E uses configfs RNDIS because its
kernel has no `g_ether` module.

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
| Kobo Mini, Touch | BCM43362 FullMAC SDIO | ChipIdea `g_ether` |
| Kobo Forma | RTL8192ES SDIO | ChipIdea `g_ether` |
| Kobo Elipsa 2E | MediaTek CONNAC DMA | MT8113 configfs RNDIS |

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
