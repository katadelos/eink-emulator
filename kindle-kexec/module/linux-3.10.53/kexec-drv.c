#include <linux/module.h>
#include <linux/err.h>
#include <linux/fs.h>
#include <linux/device.h>
#include <linux/reboot.h>
#include <asm/uaccess.h>
#include <linux/kexec.h>
#include <linux/kallsyms.h>

static void (*set_cpu_online_ptr)(unsigned int, bool);
void set_cpu_online(unsigned int cpu, bool online) { set_cpu_online_ptr(cpu, online); }

static void (*machine_shutdown_ptr)(void);
static void (*kernel_restart_prepare_ptr)(char*);
static void (*soft_restart_ptr)(unsigned long);
static int  (*memblock_is_region_memory_ptr)(phys_addr_t, phys_addr_t);

void machine_shutdown(void)
{
	machine_shutdown_ptr();
}
void kernel_restart_prepare(char *cmd)
{
	kernel_restart_prepare_ptr(cmd);
}
void soft_restart(unsigned long addr)
{
	soft_restart_ptr(addr);
}
int memblock_is_region_memory(phys_addr_t base, phys_addr_t size)
{
	return memblock_is_region_memory_ptr(base, size);
}

static long kexecmod_ioctl(struct file *file, unsigned req, unsigned long arg)
{
	struct {
		unsigned long entry;
		unsigned long nr_segs;
		struct kexec_segment *segs;
		unsigned long flags;
	} ap;
	if (!capable(CAP_SYS_BOOT)) return -EPERM;
	switch (req) {
	case LINUX_REBOOT_CMD_KEXEC - 1:
		if (copy_from_user(&ap, (void*)arg, sizeof ap))
			return -EFAULT;
		if (ap.flags & ~KEXEC_ARCH_MASK) return -EINVAL;
		return sys_kexec_load(ap.entry, ap.nr_segs, ap.segs, ap.flags);
	case LINUX_REBOOT_CMD_KEXEC:
		return kernel_kexec();
	}
	return -EINVAL;
}

static const struct file_operations fops = {
	.owner = THIS_MODULE,
	.unlocked_ioctl = kexecmod_ioctl,
};

static void *ksym(const char *name)
{
	return (void *)kallsyms_lookup_name(name);
}

static int __init
kexecmod_init(void)
{
	int maj;
	struct class *class;
	struct device *device;
	if (!(set_cpu_online_ptr = ksym("set_cpu_online"))
            || !(machine_shutdown_ptr = ksym("machine_shutdown"))
#ifdef CONFIG_ARM
	    //|| !(machine_shutdown_ptr = ksym("disable_nonboot_cpus"))
	    || !(soft_restart_ptr = ksym("soft_restart"))
	    || !(memblock_is_region_memory_ptr = ksym("memblock_is_region_memory"))
#endif
	    || !(kernel_restart_prepare_ptr = ksym("kernel_restart_prepare")))
		return -ENOENT;

	maj = register_chrdev(0, "kexec", &fops);
	if (maj < 0)
		return maj;
	class = class_create(THIS_MODULE, "kexec");
	if (IS_ERR(class)) {
		unregister_chrdev(maj, "kexec");
		return PTR_ERR(class);
	}
	device = device_create(class, 0, MKDEV(maj, 0), 0, "kexec");
	if (IS_ERR(device)) {
		class_destroy(class);
		unregister_chrdev(maj, "kexec");
		return PTR_ERR(device);
	}
	return 0;
}

module_init(kexecmod_init)

MODULE_LICENSE("GPL v2");
