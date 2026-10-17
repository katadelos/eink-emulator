#!/usr/bin/env python3
"""Build Kindle kexec tools and modules using an existing Docker image."""
import argparse
import importlib.util
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import falcon

HERE = Path(__file__).resolve().parent
PROFILES = json.loads((HERE / "profiles.json").read_text())
REPOS = {
    "kexec-mod": ("git@github.com:fabianishere/kexec-mod.git", "4ba956fd60b29d2fea324515596b392afdcfa2c5"),
    "kexec-module": ("git@github.com:amonakov/kexec-module.git", "f010e4145a35f45264912eff653c525d7489eb32"),
    "kexec-tools": ("git@github.com:horms/kexec-tools.git", "ae1bd3dde601516f9e90fdc127aa48a81c0d33bc"),
}
STUB_FALCON = "static int kindle_falcon_prepare(void) { return 0; }\nstatic void kindle_falcon_rearm(void) {}\n"


def run(*args, **kwargs):
    subprocess.run([str(a) for a in args], check=True, **kwargs)


def checkout():
    for name, (url, revision) in REPOS.items():
        target = HERE / name
        if not target.exists():
            run("git", "clone", url, target)
            run("git", "-C", target, "checkout", "--detach", revision)
        actual = subprocess.check_output(["git", "-C", str(target), "rev-parse", "HEAD"], text=True).strip()
        if actual != revision:
            raise SystemExit(f"{target} must be at {revision}; preserving the existing checkout")


class Builder:
    def __init__(self, args):
        self.args = args
        # Never pull or build a Docker image implicitly.
        run("docker", "image", "inspect", args.image, stdout=subprocess.DEVNULL)
        self.docker = ["docker", "run", "--rm", "--platform", "linux/arm64",
                       "-v", f"{HERE}:/work", "-v", f"{args.toolchains.resolve()}:/tools:ro",
                       "-w", "/work", args.image]

    def shell(self, command):
        run(*self.docker, "sh", "-ec", command)

    def userspace(self):
        checkout()
        patch = HERE / "patches/kexec-tools.patch"
        repo = HERE / "kexec-tools"
        applied = subprocess.run(["git", "-C", str(repo), "apply", "--reverse", "--check", str(patch)],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
        if not applied:
            run("git", "-C", repo, "apply", "--check", patch)
            run("git", "-C", repo, "apply", patch)
        self.shell("cd kexec-tools; ./bootstrap")
        for arch, host, prefix in [
            ("arm", "arm-kindle5-linux-gnueabi", "/tools/arm-kindle5-linux-gnueabi/bin/arm-kindle5-linux-gnueabi-"),
            ("arm64", "aarch64-linux-gnu", "aarch64-linux-gnu-")]:
            for module in (False, True):
                name = arch + ("-module" if module else "")
                flags = "-Os" + (" -DKINDLE_KEXEC_MODULE" if module else "")
                self.shell(f"mkdir -p build/{name}; cd build/{name}; "
                           f"/work/kexec-tools/configure --host={host} --without-zlib --without-lzma --without-xen "
                           f"CC={prefix}gcc LD={prefix}ld AR={prefix}ar CFLAGS='{flags}' LDFLAGS=-static; "
                           f"make -j{self.args.jobs}")
                dest = HERE / "dist" / arch
                dest.mkdir(parents=True, exist_ok=True)
                shutil.copy2(HERE / "build" / name / "build/sbin/kexec", dest / ("kexec-module" if module else "kexec"))

    def make_options(self, profile):
        p = PROFILES[profile]
        prefix = "aarch64-linux-gnu-" if p["arch"] == "arm64" else (
            "/tools/arm-kindle5-linux-gnueabi/bin/arm-kindle5-linux-gnueabi-" if p["kernel"] == "2.6.31" else
            "/tools/arm-kindlepw2-linux-gnueabi/bin/arm-kindlepw2-linux-gnueabi-")
        flags = "-Wno-error=unused-variable" if p["arch"] == "arm64" else (
            "-fno-pie -fno-stack-protector -fgnu89-inline -Wno-error=implicit-function-declaration "
            "-Wno-error=incompatible-pointer-types -Wno-error=int-conversion")
        if p["kernel"] == "4.9.77":
            flags += " -Wno-error"
        local = " LOCALVERSION=-lab126" if profile in ("koa2", "koa3") else " LOCALVERSION="
        return f"ARCH={p['arch']} CROSS_COMPILE={prefix} HOSTCFLAGS='-O2 -fcommon' KCFLAGS='{flags}'{local}"

    def kernel(self, profile, source, symvers=None):
        p = PROFILES[profile]
        if p.get("native"):
            raise SystemExit("Touch uses the existing kernel's kexec syscall")
        stock_symbols = symvers.read_bytes() if symvers is not None else None
        if stock_symbols is not None and not stock_symbols.strip():
            raise SystemExit("The supplied stock Module.symvers is empty")
        dest = HERE / "build/kernel" / profile
        if not dest.exists():
            shutil.copytree(source, dest, symlinks=True, ignore=shutil.ignore_patterns(".git"))
        shutil.copy2(HERE / "configs" / (profile + ".config"), dest / ".config")
        compiler = dest / "include/linux/compiler-gcc4.h"
        if compiler.exists():
            shutil.copy2(compiler, compiler.with_name("compiler-gcc14.h"))
        edits = {}
        if p["kernel"] == "4.1.15":
            edits = {
                "arch/arm/mm/proc-v7.S": [('.section ".proc.info.init", #alloc', '.section ".proc.info.init", "a"')],
                "arch/arm/include/asm/uaccess.h": [('register const typeof(*(p)) __r2', 'register typeof(*(p)) __r2')],
                "drivers/mxc/gpu-viv/Kbuild": [('EXTRA_CFLAGS += -Werror', 'EXTRA_CFLAGS += -Wno-error')],
                "drivers/usb/gadget/udc/udc-core.c": [('#include <linux/usb.h>', '#include <linux/usb.h>\n#include <linux/busfreq-imx.h>')],
            }
        elif p["kernel"] == "4.9.77":
            edits = {
                "scripts/Makefile.lib": [
                    ('$(ccflags-y) $(CFLAGS_$(basetarget).o)',
                     '$(ccflags-y) $(CFLAGS_$(basetarget).o) $(KCFLAGS)')],
                "arch/arm/mm/proc-v7.S": [('.section ".proc.info.init", #alloc', '.section ".proc.info.init", "a"')],
                "drivers/devfreq/Makefile": [
                    ('ccflags-y += -I$(srctree)/drivers/misc/mediatek/include/\n',
                     'ccflags-y += -I$(srctree)/drivers/devfreq/\nccflags-y += -I$(srctree)/drivers/misc/mediatek/include/\n')],
                "drivers/misc/mediatek/hwtcon_v2/Makefile": [
                    ('ccflags-y += -I$(srctree)/drivers/misc/mediatek/hwtcon_v2/hal',
                     'ccflags-y += -I$(srctree)/drivers/misc/mediatek/hwtcon_v2\nccflags-y += -I$(srctree)/drivers/misc/mediatek/hwtcon_v2/hal')],
            }
        for name, replacements in edits.items():
            path = dest / name
            text = path.read_text()
            for before, after in replacements:
                if after not in text:
                    text = text.replace(before, after)
            path.write_text(text)
        targets = "olddefconfig modules_prepare" if p["kernel"] in ("4.9.77", "5.15", "6.6") else "oldconfig modules_prepare"
        if stock_symbols is None and "CONFIG_MODVERSIONS=y" in (dest / ".config").read_text():
            targets += " vmlinux"
        self.shell(f"make -C /work/build/kernel/{profile} {self.make_options(profile)} -j{self.args.jobs} {targets} < /dev/null")
        if stock_symbols is not None:
            (dest / "Module.symvers").write_bytes(stock_symbols)
        return dest

    def module(self, profile, kernel):
        p = PROFILES[profile]
        if p.get("native"):
            raise SystemExit("Touch uses its existing CONFIG_KEXEC syscall; build userspace only")
        kernel = kernel.resolve()
        try:
            relative_kernel = kernel.relative_to(HERE)
        except ValueError:
            raise SystemExit("The prepared kernel tree must be inside kindle-kexec (use the kernel command)")
        dest = HERE / "build/modules" / profile
        shutil.copytree(HERE / "module" / ("linux-" + p["kernel"]), dest, dirs_exist_ok=True)
        config = (kernel / ".config").read_text()
        if f"CONFIG_{p['arch'].upper()}=y" not in config:
            raise SystemExit("Kernel architecture does not match the profile")
        expected = dict(re.findall(r"^(CONFIG_\w+)=(.*)$", (HERE / "configs" / (profile + ".config")).read_text(), re.M))
        actual = dict(re.findall(r"^(CONFIG_\w+)=(.*)$", config, re.M))
        for key in ("SMP", "PREEMPT", "HIGHMEM", "ARM_LPAE", "PAGE_OFFSET", "PHYS_OFFSET",
                    "NR_CPUS", "MODVERSIONS", "FALCON", "AEABI"):
            key = "CONFIG_" + key
            if expected.get(key) != actual.get(key):
                raise SystemExit(f"Prepared kernel has a different {key}; configure it for {profile} first")
        if p["kernel"] not in ("4.9.77", "5.15", "6.6"):
            orig = dest / "orig"
            orig.mkdir(exist_ok=True)
            for name, source in [("orig/kexec.c", "kernel/kexec.c"),
                                 ("orig/machine_kexec.c", "arch/arm/kernel/machine_kexec.c"),
                                 ("relocate_kernel.S", "arch/arm/kernel/relocate_kernel.S")]:
                link = dest / name
                if link.is_symlink():
                    link.unlink()
                link.symlink_to(os.path.relpath(kernel / source, link.parent))
        if p["kernel"] in ("3.0.35", "4.1.15", "4.9.77", "5.15"):
            header = STUB_FALCON
            if "falcon" in p:
                firmware = HERE.parent / "firmware" / p["model"]
                if "falcon_image" in p:
                    spec = importlib.util.spec_from_file_location("images", HERE / "prepare-image.py")
                    images = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(images)
                    nodes = images.fdt_nodes((firmware / p["falcon_image"]).read_bytes())
                    main, storage = [nodes["/images/" + key]["data"] for key in ("fbios", "sbios")]
                else:
                    main, storage = [(firmware / name).read_bytes() for name in ("bios.bin", "s-bios.bin")]
                header = falcon.generate(main, storage, *(int(v, 0) for v in p["falcon"]))
            (dest / "falcon-rearm.h").write_text(header)
        symbols = kernel / "vmlinux.symvers"
        extra = (f" KBUILD_EXTRA_SYMBOLS=/work/{relative_kernel}/vmlinux.symvers"
                 if symbols.exists() and not (kernel / "Module.symvers").exists() else "")
        self.shell(f"make -C /work/{relative_kernel} {self.make_options(profile)} "
                   f"M=/work/build/modules/{profile}{extra} -j{self.args.jobs} modules")
        output = HERE / "dist" / profile
        output.mkdir(parents=True, exist_ok=True)
        for module in dest.rglob("*.ko"):
            shutil.copy2(module, output / module.name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="koxtoolchain:build-env")
    parser.add_argument("--toolchains", type=Path, help="path to the koxtoolchain x-tools directory")
    parser.add_argument("--jobs", type=int, default=6)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("checkout")
    sub.add_parser("userspace")
    for command, argument in (("kernel", "source"), ("module", "kernel")):
        p = sub.add_parser(command)
        p.add_argument("profile", choices=PROFILES)
        p.add_argument("--" + argument, type=Path, required=True)
        if command == "kernel":
            p.add_argument("--symvers", type=Path,
                           help="Module.symvers from this exact stock kernel; skip rebuilding vmlinux")
    args = parser.parse_args()
    if args.command == "checkout":
        checkout()
        return
    if args.toolchains is None:
        parser.error("--toolchains is required for builds")
    builder = Builder(args)
    if args.command == "userspace":
        builder.userspace()
    elif args.command == "kernel":
        builder.kernel(args.profile, args.source, args.symvers)
    else:
        builder.module(args.profile, args.kernel)


if __name__ == "__main__":
    main()
