/*
 * kexec_mod: Kexec functionality as loadable kernel module.
 *
 * Copyright (C) 2021 Fabian Mastenbroek.
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 */

#define MODULE_NAME "kexec_mod"
#undef pr_fmt
#define pr_fmt(fmt) MODULE_NAME ": " fmt

#include <linux/module.h>
#include <linux/err.h>
#include <linux/fs.h>
#include <linux/sysfs.h>
#include <linux/miscdevice.h>
#include <linux/reboot.h>

#include <uapi/linux/stat.h>

#include "kexec_compat.h"
#include "kexec.h"
#include "kexec_internal.h"

MODULE_LICENSE("GPL v2");
MODULE_AUTHOR("Fabian Mastenbroek <mail.fabianm@gmail.com>");
MODULE_DESCRIPTION("Kexec backport as Kernel Module");
MODULE_VERSION("1.1");

static ssize_t kexecmod_loaded_show(struct kobject *kobj,
		  		    struct kobj_attribute *attr, char *buf)
{
	extern struct kimage *kexec_image;
	return sprintf(buf, "%d\n", !!kexec_image);
}

static struct kobj_attribute kexec_loaded_attr = __ATTR(kexec_loaded, S_IRUGO, kexecmod_loaded_show, NULL);

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

static struct miscdevice kexec_device = {
    .minor = MISC_DYNAMIC_MINOR,
    .name = "kexec",
    .fops = &fops,
    .mode = 0600,
};

static int __init
kexecmod_init(void)
{
	int err;

	/* Load compatibility layer */
	if ((err = kexec_compat_load()) != 0) {
		pr_err("Failed to load: %d\n", err);
		return err;
	}

	/* Register character device at /dev/kexec */
	err = misc_register(&kexec_device);
	if (err) return err;

	/* Register sysfs object */
	err = sysfs_create_file(kernel_kobj, &(kexec_loaded_attr.attr));
	if (err) { misc_deregister(&kexec_device); return err; }

	pr_info("Kexec functionality now available at /dev/kexec.\n");

	return 0;
}

module_init(kexecmod_init)

static void __exit
kexecmod_exit(void)
{
	pr_info("Stopping...\n");

	mutex_lock(&kexec_mutex);
	kimage_free(kexec_image);
	kexec_image = NULL;
	mutex_unlock(&kexec_mutex);

	/* Unload compatibility layer */
	kexec_compat_unload();

	/* Destroy character device */
	misc_deregister(&kexec_device);

	/* Remove sysfs object */
	sysfs_remove_file(kernel_kobj, &(kexec_loaded_attr.attr));
}

module_exit(kexecmod_exit);
