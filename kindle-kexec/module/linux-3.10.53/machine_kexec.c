#include "orig/machine_kexec.c"

#ifdef CONFIG_X86
void disable_IO_APIC(void) {}
unsigned long max_pfn;
#include <linux/moduleparam.h>
module_param(max_pfn, ulong, 0);
#endif
