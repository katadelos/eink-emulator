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
    ldr r0, [r4, #28]
    ldr r3, [r4, #24]
    bx r3
kindle_reboot_end:
.section .note.GNU-stack,"",%progbits
