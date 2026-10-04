/* SPDX-License-Identifier: GPL-2.0 */
#ifndef LINUX_KEXEC_H
#define LINUX_KEXEC_H

#define IND_DESTINATION_BIT 0
#define IND_INDIRECTION_BIT 1
#define IND_DONE_BIT        2
#define IND_SOURCE_BIT      3

#define IND_DESTINATION  (1 << IND_DESTINATION_BIT)
#define IND_INDIRECTION  (1 << IND_INDIRECTION_BIT)
#define IND_DONE         (1 << IND_DONE_BIT)
#define IND_SOURCE       (1 << IND_SOURCE_BIT)
#define IND_FLAGS (IND_DESTINATION | IND_INDIRECTION | IND_DONE | IND_SOURCE)

#if !defined(__ASSEMBLY__)

#include <linux/crash_core.h>
#include <asm/io.h>

#include <uapi/linux/kexec.h>

#include <linux/list.h>
#include <linux/compat.h>
#include <linux/ioport.h>
#include <linux/module.h>
#include <asm/kexec.h>

/* Verify architecture specific macros are defined */

#ifndef KEXEC_SOURCE_MEMORY_LIMIT
#error KEXEC_SOURCE_MEMORY_LIMIT not defined
#endif

#ifndef KEXEC_DESTINATION_MEMORY_LIMIT
#error KEXEC_DESTINATION_MEMORY_LIMIT not defined
#endif

#ifndef KEXEC_CONTROL_MEMORY_LIMIT
#error KEXEC_CONTROL_MEMORY_LIMIT not defined
#endif

#ifndef KEXEC_CONTROL_MEMORY_GFP
#define KEXEC_CONTROL_MEMORY_GFP (GFP_KERNEL | __GFP_NORETRY)
#endif

#ifndef KEXEC_CONTROL_PAGE_SIZE
#error KEXEC_CONTROL_PAGE_SIZE not defined
#endif

#ifndef KEXEC_ARCH
#error KEXEC_ARCH not defined
#endif

/*
 * This structure is used to hold the arguments that are used when loading
 * kernel binaries.
 */

typedef unsigned long kimage_entry_t;

struct kexec_segment {
	/*
	 * This pointer can point to user memory if kexec_load() system
	 * call is used or will point to kernel memory if
	 * kexec_file_load() system call is used.
	 *
	 * Use ->buf when expecting to deal with user memory and use ->kbuf
	 * when expecting to deal with kernel memory.
	 */
	union {
		void __user *buf;
		void *kbuf;
	};
	size_t bufsz;
	unsigned long mem;
	size_t memsz;
};

struct kimage {
	kimage_entry_t head;
	kimage_entry_t *entry;
	kimage_entry_t *last_entry;

	unsigned long start;
	struct page *control_code_page;
	struct page *swap_page;

	unsigned long nr_segments;
	struct kexec_segment segment[KEXEC_SEGMENT_MAX];

	struct list_head control_pages;
	struct list_head dest_pages;
	struct list_head unusable_pages;

	/* Address of next control page to allocate for crash kernels. */
	unsigned long control_page;

	/* Flags to indicate special processing */
	unsigned int preserve_context : 1;
	/* If set, we are using file mode kexec syscall */
	unsigned int file_mode:1;

#ifdef ARCH_HAS_KIMAGE_ARCH
	struct kimage_arch arch;
#endif
};

long sys_kexec_load(unsigned long entry, unsigned long nr_segments,
		    struct kexec_segment __user *segments,
		    unsigned long flags);

/* kexec interface functions */
extern void machine_kexec(struct kimage *image);
extern int machine_kexec_prepare(struct kimage *image);
extern void machine_kexec_cleanup(struct kimage *image);
extern int kernel_kexec(void);
extern struct page *kimage_alloc_control_pages(struct kimage *image,
					       unsigned int order);
extern struct kimage *kexec_image;
extern int kexec_load_disabled;

#ifndef kexec_flush_icache_page
#define kexec_flush_icache_page(page)
#endif

/* List of defined/legal kexec flags */
#define KEXEC_FLAGS    0

/* List of defined/legal kexec file flags */
#define KEXEC_FILE_FLAGS	(KEXEC_FILE_UNLOAD | KEXEC_FILE_ON_CRASH | \
				 KEXEC_FILE_NO_INITRAMFS)

/* flag to track if kexec reboot is in progress */
extern bool kexec_in_progress;

#ifndef page_to_boot_pfn
static inline unsigned long page_to_boot_pfn(struct page *page)
{
	return page_to_pfn(page);
}
#endif

#ifndef boot_pfn_to_page
static inline struct page *boot_pfn_to_page(unsigned long boot_pfn)
{
	return pfn_to_page(boot_pfn);
}
#endif

#ifndef phys_to_boot_phys
static inline unsigned long phys_to_boot_phys(phys_addr_t phys)
{
	return phys;
}
#endif

#ifndef boot_phys_to_phys
static inline phys_addr_t boot_phys_to_phys(unsigned long boot_phys)
{
	return boot_phys;
}
#endif

static inline unsigned long virt_to_boot_phys(void *addr)
{
	return phys_to_boot_phys(__pa((unsigned long)addr));
}

static inline void *boot_phys_to_virt(unsigned long entry)
{
	return phys_to_virt(boot_phys_to_phys(entry));
}

#ifndef arch_kexec_post_alloc_pages
static inline int arch_kexec_post_alloc_pages(void *vaddr, unsigned int pages, gfp_t gfp) { return 0; }
#endif

#ifndef arch_kexec_pre_free_pages
static inline void arch_kexec_pre_free_pages(void *vaddr, unsigned int pages) { }
#endif

#endif /* !defined(__ASSEBMLY__) */

#endif /* LINUX_KEXEC_H */
