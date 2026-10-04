/* SPDX-License-Identifier: GPL-2.0-only */
#include <linux/moduleparam.h>
static unsigned long symbol_lookup;
module_param(symbol_lookup, ulong, 0400);
static unsigned long kindle_lookup_name(const char *name)
{
    unsigned long (*lookup)(const char *) = (void *)symbol_lookup;
    return lookup ? lookup(name) : 0;
}
