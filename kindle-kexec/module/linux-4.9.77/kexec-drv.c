/* SPDX-License-Identifier: GPL-2.0-only */
#include <linux/module.h>
#include <linux/cpu.h>
#include <linux/device.h>
#include <linux/fs.h>
#include <linux/kexec.h>
#include <linux/reboot.h>
#include <linux/sched.h>
#include <linux/syscore_ops.h>
#include <linux/syscalls.h>
#include <linux/uaccess.h>
#include "kexec_internal.h"

static bool executing;

/* The stock Scribe kernel has neither kallsyms nor kprobes. Enter from
 * kernel_restart's syscore phase, after its normal device shutdown, using
 * only exported interfaces. Registering last makes this run first: the
 * native 4.9 kexec path also leaves syscore shutdown callbacks untouched.
 * Ordinary reboots never take this callback. */
static void kexec_shutdown(void)
{
	if (executing)
		machine_kexec(kexec_image);
}

static struct syscore_ops kexec_syscore = { .shutdown = kexec_shutdown };

int kernel_kexec(void)
{
	unsigned int cpu;
	int ret;

	if (!mutex_trylock(&kexec_mutex))
		return -EBUSY;
	if (!kexec_image) {
		ret = -EINVAL;
		goto out;
	}
	ret = set_cpus_allowed_ptr(current, cpumask_of(0));
	if (ret)
		goto out;
	for_each_online_cpu(cpu) {
		if (cpu == 0)
			continue;
		ret = cpu_down(cpu);
		if (ret)
			goto out;
	}
	cpu_hotplug_disable();
	if (num_online_cpus() != 1) {
		cpu_hotplug_enable();
		ret = -EBUSY;
		goto out;
	}
	executing = true;
	pr_emerg("Starting new kernel\n");
	kernel_restart(NULL);
	ret = -EIO;
out:
	mutex_unlock(&kexec_mutex);
	return ret;
}

static long kexecmod_ioctl(struct file *file, unsigned req, unsigned long arg)
{
	struct {
		unsigned long entry, nr_segs;
		struct kexec_segment *segs;
		unsigned long flags;
	} ap;
	if (!capable(CAP_SYS_BOOT))
		return -EPERM;
	switch (req) {
	case LINUX_REBOOT_CMD_KEXEC - 1:
		if (copy_from_user(&ap, (void *)arg, sizeof(ap)))
			return -EFAULT;
		if (ap.flags & ~KEXEC_ARCH_MASK)
			return -EINVAL;
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

static int __init kexecmod_init(void)
{
	int maj;
	struct class *class;
	struct device *device;

	maj = register_chrdev(0, "kexec", &fops);
	if (maj < 0)
		return maj;
	class = class_create(THIS_MODULE, "kexec");
	if (IS_ERR(class)) {
		unregister_chrdev(maj, "kexec");
		return PTR_ERR(class);
	}
	device = device_create(class, NULL, MKDEV(maj, 0), NULL, "kexec");
	if (IS_ERR(device)) {
		class_destroy(class);
		unregister_chrdev(maj, "kexec");
		return PTR_ERR(device);
	}
	register_syscore_ops(&kexec_syscore);
	return 0;
}
module_init(kexecmod_init);
MODULE_LICENSE("GPL v2");
