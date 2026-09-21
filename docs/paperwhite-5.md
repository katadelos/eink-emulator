# Kindle Paperwhite 5

The 2021 Paperwhite uses the Malbec board. It skips account setup and opens
Home without registration. Automatic sleep is disabled.

## Setup

Supply Amazon's [firmware 5.19.2](https://s3.amazonaws.com/firmwaredownloads/update_kindle_all_new_paperwhite_11th_5.19.2.bin)
and install the [host requirements](../README.md#host-requirements). Replace
`/path/to/` with the package location:

```sh
./eink import /path/to/update_kindle_all_new_paperwhite_11th_5.19.2.bin \
  --model kindle-paperwhite-5
./eink create pw5 --model kindle-paperwhite-5 --profile production
./eink run pw5
```

Only `production` is supported. Click the display to tap. See [networking](networking.md) for SSH and Wi-Fi,
and [guest changes](guest-overrides.md#bellatrix) for startup modifications.

Amazon's [5.19.2 source archive](https://s3.amazonaws.com/kindledownloads/Kindle_src_5.19.2_4670760040.tar.gz)
contains the vendor U-Boot and Linux sources for development work.
