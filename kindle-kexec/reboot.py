#!/usr/bin/env python3
"""Kexec an existing eink machine's installed firmware kernel and rootfs."""
import argparse
import importlib.util
import json
import shlex
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PROFILES = json.loads((HERE / "profiles.json").read_text())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", choices=PROFILES)
    parser.add_argument("--machine", help="existing machine name; defaults to the saved profile")
    parser.add_argument("--port", type=int, default=2222, help="SSH port of the running machine")
    parser.add_argument("--load-only", action="store_true", help="stage the kernel without executing it")
    parser.add_argument("--timeout", type=int, default=180, help="seconds to wait for SSH after handoff")
    args = parser.parse_args()
    profile = PROFILES[args.profile]
    name = args.machine or profile["machine"]
    machine_file = ROOT / "machines" / name / "machine.json"
    if not machine_file.is_file():
        raise SystemExit(f"No existing machine named {name}; this command never creates machines")
    if json.loads(machine_file.read_text())["model"] != profile["model"]:
        raise SystemExit("The saved machine does not match the selected device profile")
    ssh = ["ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=no",
           "-o", "UserKnownHostsFile=/dev/null", "-o", "ConnectTimeout=3",
           "-o", "ServerAliveInterval=3", "-o", "ServerAliveCountMax=2",
           "-i", str(ROOT / "build/ssh/id_ed25519"), "-p", str(args.port), "root@127.0.0.1"]

    def remote(command, timeout=30, data=None, check=True):
        return subprocess.run(ssh + [command], input=data, capture_output=True,
                              timeout=timeout, check=check)

    def put(path, payload, executable=False):
        remote("cat > " + shlex.quote(path), data=payload)
        if executable:
            remote("chmod 700 " + shlex.quote(path))

    def state():
        result = remote("cat /proc/sys/kernel/random/boot_id; uname -r; cat /proc/cmdline; cat /proc/mounts", timeout=10)
        lines = result.stdout.decode().splitlines()
        if len(lines) < 4:
            raise RuntimeError("Incomplete guest boot state")
        root = next((v for v in shlex.split(lines[2]) if v.startswith("root=")), None)
        if not root or not any(len(v.split()) > 1 and v.split()[1] == "/" for v in lines[3:]):
            raise RuntimeError("The running guest has no identifiable root filesystem")
        mountinfo = remote("cat /proc/self/mountinfo", timeout=10).stdout.decode().splitlines()
        roots = [line.split()[2] for line in mountinfo if len(line.split()) > 5 and line.split()[4] == "/"]
        if not roots:
            raise RuntimeError("Cannot identify the mounted root device")
        return lines[0], lines[1], root, lines[2], roots[-1]

    deadline = time.monotonic() + args.timeout
    while True:
        try:
            before = state()
            break
        except (subprocess.SubprocessError, RuntimeError):
            if time.monotonic() >= deadline:
                raise SystemExit(f"SSH is unavailable on port {args.port}; start the existing machine first")
            time.sleep(3)
    architecture = remote("uname -m").stdout.decode().strip()
    if (architecture == "aarch64") != (profile["arch"] == "arm64"):
        raise SystemExit("Connected guest architecture does not match the saved machine")
    if not profile.get("native") and not before[1].startswith(profile["kernel"] + ".") and before[1] != profile["kernel"] + "-lab126":
        raise SystemExit(f"Unexpected guest kernel {before[1]}")
    firmware = ROOT / "firmware" / profile["model"]
    image = firmware / profile["image"]
    spec = importlib.util.spec_from_file_location("images", HERE / "prepare-image.py")
    images = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(images)
    payloads = images.extract(image.read_bytes())
    work = "/var/tmp/kindle-kexec"
    remote("mkdir -p " + work + "; chmod 700 " + work)
    binary = "kexec" if profile.get("native") else "kexec-module"
    put(work + "/kexec", (HERE / "dist" / profile["arch"] / binary).read_bytes(), True)
    for key in ("kernel", "initrd"):
        if key in payloads:
            put(work + "/" + key, payloads[key])
    if not profile.get("native"):
        modules = sorted((HERE / "dist" / args.profile).glob("*.ko"),
                         key=lambda p: ("arm64" not in p.name, p.name))
        if not modules:
            raise SystemExit("Build this profile's module before rebooting")
        for module in modules:
            put(work + "/" + module.name, module.read_bytes())
            parameter = ""
            if profile.get("lookup_parameter"):
                address = remote("awk '$3 == \"kallsyms_lookup_name\" {print $1}' /proc/kallsyms").stdout.decode().strip()
                if not address or int(address, 16) == 0:
                    raise SystemExit("The running kernel does not expose kallsyms_lookup_name's address")
                parameter = " symbol_lookup=0x" + address
            result = remote("insmod " + shlex.quote(work + "/" + module.name) + parameter, check=False)
            if result.returncode:
                raise SystemExit(result.stderr.decode() + "\n" + remote("dmesg | tail -15").stdout.decode())
    # The live DT includes the bootloader's board identity and reserved memory.
    # Do not substitute the generic DT from the firmware archive.
    tree = remote("test -r /sys/firmware/fdt", check=False).returncode == 0
    proc_tree = remote("test -d /proc/device-tree", check=False).returncode == 0
    cmdline = before[3]
    if proc_tree:
        bootargs = remote("cat /proc/device-tree/chosen/bootargs", check=False)
        if bootargs.returncode == 0 and bootargs.stdout.rstrip(b"\0"):
            cmdline = bootargs.stdout.rstrip(b"\0").decode()
    # kexec sets the relocated initrd addresses in the DT/ATAGs itself.
    cmdline = " ".join(v for v in cmdline.split() if not v.startswith("initrd="))
    load = [work + "/kexec", "-c", "-l", work + "/kernel", "--append=" + cmdline]
    if tree:
        load.append("--dtb=/sys/firmware/fdt")
    elif not proc_tree:
        load.append("--atags")
    if "initrd" in payloads:
        load.append("--initrd=" + work + "/initrd")
    result = remote(shlex.join(load), check=False)
    if result.returncode:
        raise SystemExit(result.stdout.decode() + result.stderr.decode())
    print(f"Loaded {image.name} for {name}: {before[1]}, {before[2]}", flush=True)
    power_commands = [
        "for p in /sys/devices/platform/disable-unused/*pd-" + shlex.quote(domain) + "*/power/control; "
        "do test -f \"$p\" && echo on > \"$p\" || exit 1; done"
        for domain in profile.get("power_domains", [])
    ]
    execute = "; ".join(power_commands + ["sync", work + "/kexec -e"])
    if args.load_only:
        print("Execute with: " + shlex.join(ssh + [execute]))
        return
    try:
        result = remote(execute, timeout=10, check=False)
        if result.returncode not in (0, 255):
            raise SystemExit(result.stderr.decode())
    except subprocess.TimeoutExpired:
        pass
    deadline = time.monotonic() + args.timeout
    while time.monotonic() < deadline:
        time.sleep(3)
        try:
            after = state()
        except (subprocess.SubprocessError, RuntimeError):
            continue
        if after[0] == before[0]:
            continue
        if after[1:3] != before[1:3] or after[4] != before[4]:
            raise SystemExit(f"Boot changed kernel or root: {after[1:3]}")
        print(f"Rebooted {name}: {before[0]} -> {after[0]}; same kernel and root filesystem")
        return
    raise SystemExit("Handoff executed, but SSH did not return. Inspect the existing machine's serial console; "
                     "some USB controllers do not reconnect automatically after a warm boot.")


if __name__ == "__main__":
    main()
