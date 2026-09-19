# KT4

Run KT4, the 10th generation basic Kindle, in a macOS window with touchscreen
controls. The emulator has 2 GiB of storage, saves your settings between
sessions and connects through your computer's internet connection.

## Set up

Download firmware **5.18.1.1.1** from
[Amazon's firmware page](https://www.amazon.com/gp/help/customer/display.html?nodeId=GKMQC26VQQMM8XSW).
Install [KindleTool](https://github.com/NiLuJe/KindleTool) if it is not already
available, then replace `/path/to/` with the location of your download:

```sh
./eink import /path/to/update_kindle_10th_5.18.1.1.1.bin --model kindle-kt4
./eink create kt4 --model kindle-kt4
./eink run kt4
```

Select the open **Kindle-QEMU** Wi-Fi network to connect. No password is
required.

## Controls

| Action | Control |
| --- | --- |
| Tap | Click the screen |
| Stop the emulator | Close its window |

KT4 has no physical page buttons.

To open the saved emulator again, run `./eink run kt4`. Import and create are
only needed during initial setup.
