# Kindle Oasis 1 and 2

Run either Oasis model in a macOS window with touchscreen and page-button
controls. Each emulator has 2 GiB of storage and saves your settings between
sessions. Oasis 1 can access the internet through your computer's connection;
Oasis 2 currently runs offline.

## Set up

Download firmware **5.16.2.1.1** for your model from
[Amazon's firmware page](https://www.amazon.com/gp/help/customer/display.html?nodeId=GKMQC26VQQMM8XSW).
Install [KindleTool](https://github.com/NiLuJe/KindleTool) if it is not already
available, then use the matching commands below. Replace `/path/to/` with
the location of your download.

### Oasis 1 — 8th generation

```sh
./eink import /path/to/update_kindle_oasis_5.16.2.1.1.bin --model kindle-oasis-1
./eink create oasis-1 --model kindle-oasis-1
./eink run oasis-1
```

### Oasis 2 — 9th generation

```sh
./eink import /path/to/update_kindle_all_new_oasis_5.16.2.1.1.bin --model kindle-oasis-2
./eink create oasis-2 --model kindle-oasis-2
./eink run oasis-2
```

On Oasis 1, select the open **Kindle-QEMU** Wi-Fi network to connect. No password
is required.

To continue to Home without registering, choose **Set up later**, then
**Finish later** during setup.

## Controls

| Action | Control |
| --- | --- |
| Tap | Click the screen |
| Previous-page button | `Page Up` or `[` |
| Next-page button | `Page Down` or `]` |
| Stop the emulator | Close its window |

To open a saved emulator again, run `./eink run oasis-1` or
`./eink run oasis-2`. Import and create are only needed during initial setup.
