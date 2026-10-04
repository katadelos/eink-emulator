/*
 * Arch-generic compatibility layer for enabling kexec as loadable kernel
 * module.
 *
 * Copyright (C) 2021 Fabian Mastenbroek.
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 */

#undef pr_fmt
#define pr_fmt(fmt) "kexec_mod: " fmt

#include <linux/version.h>
#include <linux/mm_types.h>
#include <linux/kexec.h>
#include <linux/kallsyms.h>
#include "kindle_symbols.h"
#include <linux/slab.h>
#include <asm/uaccess.h>
#include <asm/virt.h>

#include "kexec_compat.h"

/* These kernel symbols need to be dynamically resolved at runtime
 * using kallsym due to them not being exposed to kernel modules */
static int (*platform_can_secondary_boot_ptr)(void);
int platform_can_secondary_boot(void) { return platform_can_secondary_boot_ptr(); }
static int (*platform_can_cpu_hotplug_ptr)(void);
int platform_can_cpu_hotplug(void) { return platform_can_cpu_hotplug_ptr(); }
static void (*soft_restart_ptr)(unsigned long addr);
void soft_restart(unsigned long addr) { soft_restart_ptr(addr); }
static int (*memblock_is_region_memory_ptr)(phys_addr_t base, phys_addr_t size);
int memblock_is_region_memory(phys_addr_t base, phys_addr_t size) { return memblock_is_region_memory_ptr(base, size); }
/* MT8512 uses the same physical addresses with the MMU on and off. */
long long arch_phys_to_idmap_offset;

static void (*machine_shutdown_ptr)(void);
static void (*kernel_restart_prepare_ptr)(char*);
static void (*migrate_to_reboot_cpu_ptr)(void);
static void (*cpu_hotplug_enable_ptr)(void);

void machine_shutdown(void)
{
	machine_shutdown_ptr();
}

void kernel_restart_prepare(char *cmd)
{
	kernel_restart_prepare_ptr(cmd);
}

void migrate_to_reboot_cpu(void)
{
	migrate_to_reboot_cpu_ptr();
}

void cpu_hotplug_enable(void)
{
	cpu_hotplug_enable_ptr();
}

static void *ksym(const char *name)
{
	return (void *)kindle_lookup_name(name);
}

int kexec_compat_load()
{
	if (!(platform_can_secondary_boot_ptr = ksym("platform_can_secondary_boot")) || !(platform_can_cpu_hotplug_ptr = ksym("platform_can_cpu_hotplug")) || !(soft_restart_ptr = ksym("soft_restart")) || !(memblock_is_region_memory_ptr = ksym("memblock_is_region_memory")) || !(machine_shutdown_ptr = ksym("machine_shutdown"))
	    || !(migrate_to_reboot_cpu_ptr = ksym("migrate_to_reboot_cpu"))
	    || !(kernel_restart_prepare_ptr = ksym("kernel_restart_prepare"))
	    || !(cpu_hotplug_enable_ptr = ksym("cpu_hotplug_enable")))
		return -ENOENT;
	return 0;
}

void kexec_compat_unload(void)
{}
