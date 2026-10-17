# Kindle kexec

Static kexec-tools and loadable kexec implementations for the saved post-K4
machines in this repository. The handoff uses each model's existing firmware
kernel, its live boot parameters, and its existing root partition. It does not
build or boot a replacement kernel, create machines, or replace disk images.

The ARM implementation follows [amonakov/kexec-module](https://github.com/amonakov/kexec-module).
The modern core and ARM64 implementation derive from
[fabianishere/kexec-mod](https://github.com/fabianishere/kexec-mod).
`module/` contains the adapted GPL sources; `COPYING` contains the license.
`build.py checkout` obtains both upstream projects and kexec-tools using Git over
SSH at the revisions recorded in `build.py`.

## Device profiles

| Profile | Device | Guest architecture | Kernel family |
| --- | --- | --- | --- |
| `kt1` | Touch | ARM32 | 2.6.31, native kexec syscall |
| `pw1` | Paperwhite 1 | ARM32 | 2.6.31 |
| `pw2`, `kt2`, `kv`, `pw3` | Paperwhite 2, Basic 2014, Voyage, Paperwhite 3 | ARM32 | 3.0.35 |
| `koa1` | Oasis 1 | ARM32 | 3.0.35, Falcon |
| `kt3` | Basic 2016 | ARM32 | 3.10.53 |
| `koa2`, `koa3` | Oasis 2, Oasis 3 | ARM32 | 4.1.15, model-specific source/ABI |
| `pw4`, `kt4` | Paperwhite 4, Basic 2019 | ARM32 | 4.1.15, Falcon |
| `pw5`, `kt5`, `kt6` | Paperwhite 5, Basic 2022, Basic 2024 | ARM32 | 4.9.77, Falcon |
| `ks1`, `ks2` | Scribe 1, Scribe 2 | ARM32 | 4.9.77, Falcon |
| `pw6`, `cs` | Paperwhite 6, Colorsoft | ARM32 | 5.15.41, Falcon |
| `ks3`, `ksc` | Scribe 3, Scribe Colorsoft | ARM64 | 6.6.77 |

Paperwhite 5/6, Basic 2022/2024, Colorsoft, and Scribe 1/2 use **32-bit**
kernels. Scribe 3 and Scribe Colorsoft use the separate ARM64 loader and
architecture module.

## Build

Run commands from the repository root. Builds use the existing
`koxtoolchain:build-env` Docker image. Pass the koxtoolchain `x-tools` directory
with `--toolchains` before each build subcommand. The scripts do not pull or
create Docker images; use `--image` to select another existing image.

```sh
python3 kindle-kexec/build.py checkout
python3 kindle-kexec/build.py --toolchains /path/to/x-tools userspace

python3 kindle-kexec/build.py --toolchains /path/to/x-tools kernel pw4 --source /path/to/matching/linux-4.1.15
python3 kindle-kexec/build.py --toolchains /path/to/x-tools module pw4 --kernel kindle-kexec/build/kernel/pw4
```

`kernel` copies the supplied source into the ignored build directory, applies
the small GCC compatibility fixes, installs the saved configuration, and builds
the headers and symbol versions needed by the module. The resulting kernel is
**not** installed in the guest. `module` can also use an already prepared tree
inside `kindle-kexec`.

If symbol versions have already been extracted from the exact installed stock
kernel, pass `kernel --symvers /path/to/Module.symvers` to prepare the headers
without rebuilding `vmlinux`. The supplied file is installed after header
preparation and used by the module build.

Use the matching vendor source and configuration, including for kernels with
the same release string. Module version checks remain enabled. Do not force
module loading or substitute another model's symbol versions.

[Amazon's GPL source catalogue](https://digprjsurvey.amazon.com/csad/help/node/200203720)
provides the vendor archives. The installed Oasis 2 firmware corresponds to
`Kindle_src_5.16.2.1.1_4097450002.tar.gz`; Oasis 3 corresponds to
`Kindle_src_5.18.2.1.1_4821110015.tar.gz`; Scribe 3 corresponds to
`Kindle_src_5.19.6_4832210042.tar.gz`; Basic 2024 corresponds to
`Kindle_src_5.19.6_4832540042.tar.gz`. Extract the archive's Linux source
tarball before passing its directory to `kernel`.

Outputs are in `dist/arm`, `dist/arm64`, and `dist/<profile>`. The regular
`kexec` executable uses the native syscall. `kexec-module` uses `/dev/kexec`
directly; the upstream `LD_PRELOAD` shim is unnecessary with these static builds.
Kernel sources, upstream checkouts, and build outputs are ignored by Git.

## Reboot an existing machine

Build QEMU with `./eink build` before using the MediaTek models: their warm
handoff depends on the emulated USB and wireless controller resets.
Scribe 3/Colorsoft also require the fitted Wacom device and 16-bit I2C DMA
register accesses.
Start an existing machine with its normal firmware and disk, then select its
profile and SSH port:

```sh
./eink run kexec-colorsoft --headless --serial-socket --qmp-socket --ssh-port 2250 --wifi-ssh-port 2251
# In another terminal:
python3 kindle-kexec/reboot.py cs --port 2250
```

Paperwhite 5, Basic 2022/2024, and Scribe 1/2 prepared images also correct a
stock Wi-Fi driver's unbounded bus-protection poll. Existing instances retain
their original prepared image; see
[guest compatibility changes](../docs/guest-overrides.md) when creating an
instance with the current overrides.

The command waits for SSH, copies the loader and unchanged firmware payloads to
`/var/tmp/kindle-kexec`, loads the appropriate modules, stages the kernel,
syncs the filesystems, and executes kexec. It checks for a different boot ID,
the same kernel release, the same `root=` argument, and the same mounted root
device after SSH returns. It never creates or starts a machine itself.

`--machine NAME` selects another **existing** machine of the same model.
`--load-only` stages the handoff without executing it. The SSH port must belong
to that machine. Do not run against multiple guests sharing the same port.

An SSH timeout means automatic verification is unavailable. Inspect the
existing serial console to distinguish a running guest from a failed handoff;
Oasis 1 can boot its original root filesystem without reconnecting USB.
A cold launch of the same saved machine restores the emulator's initial
hardware state.

## Handoff details

* Old ATAG kernels receive complete core, memory, board identity, serial, MAC,
  and boot-mode tags from the running device. Device-tree kernels receive the
  live tree, including bootloader changes. Initrd addresses are relocated.
* The 3.0 ARM transition runs from the linear mapping before the old kernel
  changes its page tables. Cortex-A9 lockdown TLB entries are invalidated.
* Falcon firmware remains in memory. `falcon.py` identifies its I/O enumerators
  in the matching firmware pair and generates three cursor resets. The next
  kernel can then rebuild the BIOS I/O mappings. Firmware code signatures are
  checked before accepting a staged image. Replacing the BIOS with its raw
  on-disk image loses bootloader-installed exception hooks.
* Scribe 3 and Scribe Colorsoft require their `vadsp-infra` power domain to be
  on at handoff so the next kernel can register the audio power-domain
  hierarchy. `reboot.py` does this immediately before execution. The command
  printed by `--load-only` includes the same power-domain preparation.
* The ARM64 loader replaces `kaslr-seed` on every handoff. A kernel built
  without address randomization can leave the previous seed intact.
* PW1, PW6, and Colorsoft obtain `kallsyms_lookup_name`'s address from their
  running kernel and pass it through the `symbol_lookup` module parameter. ARM64 resolves it
  using a temporary kprobe. No symbol addresses are borrowed from another boot.
* The 4.9.77 module uses exported kernel interfaces for shutdown and the ARM
  handoff; these stock kernels provide neither kallsyms nor kprobes.
* The module interface requires `CAP_SYS_BOOT` and accepts ordinary kexec only.
  Crash dumping and preserve-context jumps are not supported. The older
  modules remain loaded until reboot; `kexec-module -u` releases a staged image.

The scope is these emulator guests. Physical Kindle hardware is not verified.
