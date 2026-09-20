# Kindle Paperwhite 5

Run the 2021 Kindle Paperwhite (11th Generation) with touchscreen controls
and persistent storage. Initial account setup is skipped, so the emulator
opens Home without an Amazon account. Network connectivity is not available.

## Set up

Download Amazon's [firmware 5.19.2](https://s3.amazonaws.com/firmwaredownloads/update_kindle_all_new_paperwhite_11th_5.19.2.bin)
and install the [host requirements](../README.md#host-requirements), including
KindleTool and e2fsprogs. Replace `/path/to/` with your download location:

```sh
./eink import /path/to/update_kindle_all_new_paperwhite_11th_5.19.2.bin \
  --model kindle-paperwhite-5
./eink create pw5 --model kindle-paperwhite-5 --profile production
./eink run pw5
```

`create` builds QEMU if needed and prepares the instance. Only the
`production` profile is supported; QEMU supplies a synthetic device identity.
Import and create are only needed once. To reopen the saved emulator, run
`./eink run pw5`.

## Controls

Click the screen to tap, and close the window to stop the emulator. Your
settings and library are saved between sessions. Automatic sleep is disabled.
See [guest compatibility changes](guest-overrides.md#bellatrix) for the
startup modifications applied during image creation.

## Source code

Amazon's matching [5.19.2 source archive](https://s3.amazonaws.com/kindledownloads/Kindle_src_5.19.2_4670760040.tar.gz)
contains U-Boot and Linux source for reference. It is not needed to run the
emulator, which uses the binaries supplied in the firmware package.
