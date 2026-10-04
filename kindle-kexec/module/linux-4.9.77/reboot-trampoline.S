/* SPDX-License-Identifier: GPL-2.0-only */
#include <linux/linkage.h>
.text
.align 5
.global kindle_reboot_start
.global kindle_reboot_end
kindle_reboot_start:
    /* The idmap retains this module mapping; use a private linear stack. */
    mov r4, r0
    ldr sp, [r4, #28]
    ldr r3, [r4, #0]
    ldr r0, [r4, #4]
    ldr r1, [r4, #8]
    blx r3
    mov r0, #0
    mcr p15, 0, r0, c7, c5, 6
    mcr p15, 0, r0, c8, c7, 0
    dsb
    isb
    ldr r3, [r4, #12]
    blx r3
    ldr r3, [r4, #16]
    blx r3
    ldr r3, [r4, #12]
    blx r3
    ldr r0, [r4, #24]
    ldr r3, [r4, #20]
    bx r3
kindle_reboot_end:
.section .note.GNU-stack,"",%progbits
