/* SPDX-License-Identifier: GPL-2.0-only */
#include <linux/linkage.h>
.text
.align 5
.global kindle_reboot_start
.global kindle_reboot_end
kindle_reboot_start:
    mov r4, r0
    mov r0, #0
    ldr r3, [r4, #0]
    blx r3
    ldr r3, [r4, #4]
    blx r3
    ldr r3, [r4, #8]
    cmp r3, #0
    blxne r3
    ldr r3, [r4, #12]
    cmp r3, #0
    blxne r3
    ldr r3, [r4, #16]
    blx r3
    ldr r3, [r4, #20]
    cmp r3, #0
    blxne r3
    ldr r3, [r4, #4]
    blx r3
    /* Discard Cortex-A9 lockdown entries before the next kernel rebuilds
     * its own mappings. TLBIALL alone does not invalidate locked entries. */
    mov r0, #0
    mcr p15, 0, r0, c10, c0, 0
    mov r1, #0
1:  mcr p15, 5, r1, c15, c4, 4
    mcr p15, 5, r0, c15, c6, 2
    add r1, r1, #1
    cmp r1, #4
    bne 1b
    mcr p15, 0, r0, c8, c7, 0
    dsb
    isb
    ldr r0, [r4, #28]
    ldr r3, [r4, #24]
    bx r3
kindle_reboot_end:
.section .note.GNU-stack,"",%progbits
