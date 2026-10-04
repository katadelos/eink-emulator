/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef KINDLE_SYMBOLS_H
#define KINDLE_SYMBOLS_H
#include <linux/kprobes.h>
static unsigned long kindle_lookup_name(const char *name)
{
    static unsigned long (*lookup)(const char *);
    if (!lookup) {
        struct kprobe probe = { .symbol_name = "kallsyms_lookup_name" };
        if (register_kprobe(&probe)) return 0;
        lookup = (void *)probe.addr;
        unregister_kprobe(&probe);
    }
    return lookup(name);
}
#endif
