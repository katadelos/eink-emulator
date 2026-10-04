#define CONFIG_KEXEC 1
#include <linux/kexec.h>
#undef  VMCOREINFO_SYMBOL
#define VMCOREINFO_SYMBOL(_) do {} while (0)
