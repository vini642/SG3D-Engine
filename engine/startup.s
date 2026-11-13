/* Tiny no-audio startup for an asset-free GBA ROM. */
    .syntax unified
    .arm
    .section .crt0, "ax", %progbits
    .global _start
_start:
    b reset
    .space 0xBC, 0  /* 0x04..0xBF: build.py inserts verified GBA header */
reset:
    /* Give IRQ mode its own stack. BIOS invokes the handler at 03007FFC.
       Preserve system stack below 03007F00 to avoid collision. */
    mov r0, #0x92
    msr cpsr_c, r0
    ldr sp, =0x03007FA0
    mov r0, #0x1f
    msr cpsr_c, r0
    ldr sp, =0x03007f00
    ldr r0, =__iwram_lma
    ldr r1, =__iwram_start
    ldr r2, =__iwram_end
    bl copy_words
    ldr r0, =0
    ldr r1, =__bss_start
    ldr r2, =__bss_end
    bl fill_words
    ldr r0, =0
    ldr r1, =__ewram_bss_start
    ldr r2, =__ewram_bss_end
    bl fill_words
    bl main
1:  b 1b
copy_words:
    cmp r1, r2
    ldrlo r3, [r0], #4
    strlo r3, [r1], #4
    blo copy_words
    bx lr
fill_words:
    cmp r1, r2
    strlo r0, [r1], #4
    blo fill_words
    bx lr
