/* SPDX-License-Identifier: GPL-2.0-only */
#include <linux/kexec.h>
#include <linux/mm.h>
#include <linux/of_fdt.h>
#include <asm/cacheflush.h>
#include <asm/idmap.h>
#include <asm/mach-types.h>
#include <asm/outercache.h>
#include <asm/pgalloc.h>
#include <asm/proc-fns.h>
#include <asm/uaccess.h>
#include "falcon-rearm.h"

extern const unsigned char relocate_new_kernel[];
extern const unsigned int relocate_new_kernel_size;
extern const unsigned char kindle_reboot_start[], kindle_reboot_end[];
extern unsigned long kexec_start_address, kexec_indirection_page;
extern unsigned long kexec_mach_type, kexec_boot_atags;

/* MT8113 uses identical bus and CPU physical addresses. */
long long arch_phys_to_idmap_offset;

int machine_kexec_prepare(struct kimage *image)
{
	unsigned int i;
	image->arch.dt_mem = 0;
	for (i = 0; i < image->nr_segments; i++) {
		struct kexec_segment *s = &image->segment[i];
		unsigned long pfn, end;
		__be32 magic;
		int ret;

		end = (s->mem + s->memsz) >> PAGE_SHIFT;
		for (pfn = s->mem >> PAGE_SHIFT; pfn < end; pfn++)
			if (!page_is_ram(pfn))
				return -EINVAL;
		if (s->bufsz < sizeof(magic))
			continue;
		ret = get_user(magic, (__be32 __user *)s->buf);
		if (ret)
			return ret;
		if (be32_to_cpu(magic) == OF_DT_HEADER)
			image->arch.dt_mem = s->mem;
	}
	if (!image->arch.dt_mem)
		return -EINVAL;
	return kindle_falcon_prepare();
}

void machine_kexec_cleanup(struct kimage *image) {}

void machine_kexec(struct kimage *image)
{
	void *buffer = page_address(image->control_code_page);
	unsigned long *args = buffer + 512;
	void (*transition)(unsigned long *) = (void *)kindle_reboot_start;
	unsigned long address = (unsigned long)transition;

	BUG_ON(num_online_cpus() != 1);
	BUG_ON(relocate_new_kernel_size > 256);
	BUG_ON(kindle_reboot_end - kindle_reboot_start > 256);
	kexec_start_address = image->start;
	kexec_indirection_page = image->head & PAGE_MASK;
	kexec_mach_type = machine_arch_type;
	kexec_boot_atags = image->arch.dt_mem;
	memcpy(buffer, relocate_new_kernel, relocate_new_kernel_size);
	args[0] = (unsigned long)processor.switch_mm;
	args[1] = virt_to_phys(idmap_pgd);
	args[2] = (unsigned long)&init_mm;
	args[3] = (unsigned long)v7_flush_kern_cache_all;
	args[4] = (unsigned long)processor._proc_fin;
	args[5] = virt_to_phys(processor.reset);
	args[6] = page_to_phys(image->control_code_page);
	args[7] = (unsigned long)buffer + KEXEC_CONTROL_PAGE_SIZE;
	flush_icache_range((unsigned long)buffer,
			   (unsigned long)buffer + KEXEC_CONTROL_PAGE_SIZE);
	pr_info("Bye!\n");
	local_irq_disable();
	local_fiq_disable();
	if (outer_cache.disable)
		outer_cache.disable();
	kindle_falcon_rearm();
	/* The linear map is execute-never on the stock kernel. Keep the
	 * trampoline's existing module mapping while switching to the idmap;
	 * the physical relocator is entered only after the MMU is disabled. */
	for (address &= PGDIR_MASK;
	     address < (unsigned long)kindle_reboot_end;
	     address += PGDIR_SIZE) {
		memcpy(&idmap_pgd[pgd_index(address)], pgd_offset_k(address),
		       sizeof(pgd_t));
		flush_pmd_entry((pmd_t *)&idmap_pgd[pgd_index(address)]);
	}
	transition(args);
	BUG();
}
