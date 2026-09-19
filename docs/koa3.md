# KOA3

Run KOA3, the 10th generation Kindle Oasis, in a macOS window with touchscreen
and page-button controls. The emulator has 2 GiB of storage, saves your
settings between sessions and connects through your computer's internet
connection.

## Set up

Download firmware **5.18.2.1.1** from
[Amazon's firmware page](https://www.amazon.com/gp/help/customer/display.html?nodeId=GKMQC26VQQMM8XSW).
Install [KindleTool](https://github.com/NiLuJe/KindleTool) if it is not already
available, then replace `/path/to/` with the location of your download:

```sh
./eink import /path/to/update_kindle_all_new_oasis_v2_5.18.2.1.1.bin --model kindle-oasis-3
./eink create koa3 --model kindle-oasis-3
./eink run koa3
```

Select the open **Kindle-QEMU** Wi-Fi network to connect. No password is
required.

## Controls

| Action | Control |
| --- | --- |
| Tap | Click the screen |
| Previous-page button | `Page Up` or `[` |
| Next-page button | `Page Down` or `]` |
| Stop the emulator | Close its window |

The display does not reproduce frontlight brightness or color temperature.
To save pending warmth settings before stopping, log in as `root` in the
launching terminal (no password) and run `sync; shutdown -r now`.

To open the saved emulator again, run `./eink run koa3`. Import and create are
only needed during initial setup.

KOA3 can occasionally exit during startup.
