#include <linux/module.h>
#undef  module_init
#define module_init(initfn) __attribute__((unused)) static int initfn(void);

#include "orig/kexec.c"

int panic_on_oops;

int insert_resource(struct resource *parent, struct resource *res) { return 0; }

__attribute__((weak))
void machine_crash_shutdown(struct pt_regs *regs) {}
