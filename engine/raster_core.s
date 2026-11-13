@ Standalone extraction: retains SMG GBA ARM triangle rasterizer, removes
@ original game-specific transform, stage and figure functions.
@ Original source is preserved under reference/.
    .syntax unified
    .arm

    .equ FRAME_STRIDE, 240
    .equ FRAME_WIDTH, 120
    .equ FRAME_HEIGHT, 80
    .equ CLIP_NEAR_Z, 160
    .equ GUARD_SHIFT, 2

    .equ DE_NEXT, 0
    .equ DE_MODE, 2
    .equ DE_COLOUR, 3
    .equ DE_S, 4
    .equ DE_UV, 16
    .equ DE_TEX, 28

    .equ RM_FLAT, 0
    .equ RM_TEX, 1
    .equ RM_ALPHA, 2
    .equ RM_ADD, 3
    .equ RM_DARKEN, 4
    .equ RM_TINT, 5

    .equ MIP1_STEP, 1536

    .section .iwram.engine, "ax", %progbits

.macro RECIP v, e, t
    mov     \e, #0
    cmp     \v, #256
    blo     91f
    cmp     \v, #0x1000000
    movhs   \v, \v, lsr #16
    addhs   \e, \e, #16
    cmp     \v, #0x10000
    movhs   \v, \v, lsr #8
    addhs   \e, \e, #8
    cmp     \v, #0x1000
    movhs   \v, \v, lsr #4
    addhs   \e, \e, #4
    cmp     \v, #0x400
    movhs   \v, \v, lsr #2
    addhs   \e, \e, #2
    cmp     \v, #0x200
    movhs   \v, \v, lsr #1
    addhs   \e, \e, #1
    b       92f
91: cmp     \v, #16
    movlo   \v, \v, lsl #4
    sublo   \e, \e, #4
    cmp     \v, #64
    movlo   \v, \v, lsl #2
    sublo   \e, \e, #2
    cmp     \v, #128
    movlo   \v, \v, lsl #1
    sublo   \e, \e, #1
    mov     \v, \v, lsl #1
    sub     \e, \e, #1
92: ldr     \t, =engine_recip_table - 512
    add     \t, \t, \v, lsl #1
    ldrh    \v, [\t]
.endm

    .equ RF_FILL, 0
    .equ RF_ROWB, 4
    .equ RF_PDY, 8
    .equ RF_END, 12
    .equ RF_PDX, 16
    .equ RF_LOOP, 20
    .equ RF_BOT, 24
    .equ RF_LONGL, 28
    .equ RF_RET, 32
    .equ RF_MASK, 36
    .equ RF_TEXELS, 40
    .equ RF_J0, 44
    .equ RF_A, 48
    .equ RF_B, 52
    .equ RF_C, 56
    .equ RF_UVA, 60
    .equ RF_UVB, 64
    .equ RF_UVC, 68
    .equ RF_TEX, 72
    .equ RF_MODE, 76
    .equ RF_JM, 80
    .equ RF_SECTION, 84
    .equ RF_KEEP, 88
    .equ RF_FB, 108
    .equ RF_D0, 112
    .equ RF_D1, 116
    .equ RF_D2, 120
    .equ RF_D3, 124
    .equ RF_SIZE, 128

.macro EDGE2 x, dx, vi, vj, row
    mov     r11, \vi, asr #16
    rsb     r12, r11, \vj, asr #16
    mov     \x, \vi, lsl #16
    mov     \x, \x, asr #16
    mov     \dx, \vj, lsl #16
    rsb     \dx, \x, \dx, asr #16
    sub     r11, r12, #16
    cmp     r11, #2032
    bhs     80f
    ldr     r12, [r8, r12, lsl #2]   @ compact LUT: same values, every 16th original entry
    mul     r11, \dx, r12
    mov     \dx, r11, asr #3
    b       81f
80: mov     r11, \dx
    bl      edge_slope_slow2
    mov     \dx, r11
81: mov     r11, \vi, asr #16
    rsb     lr, r11, \row, lsl #4
    add     lr, lr, #8
    smull   r11, r12, \dx, lr
    mov     r11, r11, lsr #4
    orr     r11, r11, r12, lsl #28
    add     \x, r11, \x, lsl #12
    add     \x, \x, #0x7F00
    add     \x, \x, #0xFF
.endm

.macro TEXEL rd, mask=r11
    and     \rd, r1, \mask
    orr     \rd, \rd, r1, lsr #24
    ldrb    \rd, [r12, \rd, lsr #3]
    add     r1, r1, r2
.endm
.macro SPAN_TEX mask
    tst     r0, #1
    beq     61f
    TEXEL   r10, \mask
    ldrb    r9, [r0, #-1]
    orr     r9, r9, r10, lsl #8
    strh    r9, [r0, #-1]
    add     r0, r0, #1
    subs    r3, r3, #1
    beq     69f
61: tst     r0, #2
    beq     62f
    cmp     r3, #2
    blt     65f
    TEXEL   r10, \mask
    TEXEL   r9, \mask
    orr     r10, r10, r9, lsl #8
    strh    r10, [r0], #2
    subs    r3, r3, #2
    beq     69f
62: subs    r3, r3, #4
    blt     64f
63: TEXEL   r10, \mask
    TEXEL   r9, \mask
    orr     r10, r10, r9, lsl #8
    TEXEL   r9, \mask
    orr     r10, r10, r9, lsl #16
    TEXEL   r9, \mask
    orr     r10, r10, r9, lsl #24
    str     r10, [r0], #4
    subs    r3, r3, #4
    bge     63b
64: adds    r3, r3, #4
    beq     69f
    cmp     r3, #2
    blt     65f
    TEXEL   r10, \mask
    TEXEL   r9, \mask
    orr     r10, r10, r9, lsl #8
    strh    r10, [r0], #2
    subs    r3, r3, #2
    beq     69f
65: TEXEL   r10, \mask
    ldrb    r9, [r0, #1]
    orr     r10, r10, r9, lsl #8
    strh    r10, [r0]
.endm

    .global engine_raster
    .type engine_raster, %function
engine_raster:
    push    {r4-r11, lr}
    sub     sp, sp, #RF_SIZE
    ldr     r1, =g_engine_fb
    ldr     r1, [r1]
    str     r1, [sp, #RF_FB]
    ldmia   r0, {r1-r8}
    mov     r1, r1, lsr #16
    str     r1, [sp, #RF_MODE]
    add     r0, sp, #RF_A
    stmia   r0, {r2-r8}
    bl      raster_face
    add     sp, sp, #RF_SIZE
    pop     {r4-r11, lr}
    bx      lr
    .size engine_raster, . - engine_raster

raster_face:
    str     lr, [sp, #RF_RET]
    add     r0, sp, #RF_A
    ldmia   r0, {r1-r3}
    mov     r7, r1, asr #16
    mov     r8, r2, asr #16
    mov     r9, r3, asr #16
    mov     r10, #0

    cmp     r8, r7
    bge     1f
    cmp     r8, r9
    bgt     2f
    mov     r12, r1
    mov     r1, r2
    mov     r2, r3
    mov     r3, r12
    mov     r12, r7
    mov     r7, r8
    mov     r8, r9
    mov     r9, r12
    mov     r10, #1
    b       3f
1:  cmp     r9, r7
    bge     3f
2:  mov     r12, r3
    mov     r3, r2
    mov     r2, r1
    mov     r1, r12
    mov     r12, r9
    mov     r9, r8
    mov     r8, r7
    mov     r7, r12
    mov     r10, #2
3:  stmia   r0, {r1-r3}

    cmp     r9, r8
    movgt   r11, r9
    movgt   r12, r8
    movgt   lr, #1
    movle   r11, r8
    movle   r12, r9
    movle   lr, #0
    str     lr, [sp, #RF_LONGL]
    add     r4, r7, #7
    mov     r4, r4, asr #4
    add     r11, r11, #7
    mov     r11, r11, asr #4
    add     r12, r12, #7
    mov     r12, r12, asr #4
    cmp     r4, #0
    movlt   r4, #0
    cmp     r11, #FRAME_HEIGHT
    movgt   r11, #FRAME_HEIGHT
    cmp     r4, r11
    bge     rf_done
    cmp     r12, r4
    movlt   r12, r4
    cmp     r12, r11
    movgt   r12, r11
    str     r4, [sp, #RF_J0]
    str     r12, [sp, #RF_JM]
    ldr     r0, [sp, #RF_FB]
    rsb     r5, r12, r12, lsl #4
    add     r5, r0, r5, lsl #4
    str     r5, [sp, #RF_END]
    rsb     r5, r11, r11, lsl #4
    add     r5, r0, r5, lsl #4
    str     r5, [sp, #RF_BOT]
    ldrb    r0, [sp, #RF_MODE]
    cmp     r0, #RM_FLAT
    cmpne   r0, #RM_TINT
    beq     rf_edges

    add     r0, sp, #RF_UVA
    ldmia   r0, {r4-r6}
    cmp     r10, #1
    moveq   r12, r4
    moveq   r4, r5
    moveq   r5, r6
    moveq   r6, r12
    cmp     r10, #2
    moveq   r12, r6
    moveq   r6, r5
    moveq   r5, r4
    moveq   r4, r12
    mov     r0, r1, lsl #16
    mov     r0, r0, asr #16
    mov     r8, r2, lsl #16
    rsb     r8, r0, r8, asr #16
    mov     r9, r3, lsl #16
    rsb     r9, r0, r9, asr #16
    rsb     r11, r7, r2, asr #16
    rsb     r12, r7, r3, asr #16
    mul     r10, r8, r12
    mul     r1, r11, r9
    subs    r10, r10, r1
    ble     tx_zero
    mov     r1, r4, lsl #16
    mov     r1, r1, asr #16
    mov     r2, r5, lsl #16
    rsb     r2, r1, r2, asr #16
    mov     r3, r6, lsl #16
    rsb     r3, r1, r3, asr #16
    mul     r1, r2, r12
    mul     lr, r3, r11
    sub     r1, r1, lr
    mul     lr, r8, r3
    mul     r3, r9, r2
    sub     lr, lr, r3
    mov     r3, r4, asr #16
    rsb     r2, r3, r5, asr #16
    rsb     r3, r3, r6, asr #16
    mul     r5, r2, r12
    mul     r6, r3, r11
    sub     r5, r5, r6
    mul     r6, r8, r3
    mul     r12, r9, r2
    sub     r6, r6, r12

    RECIP   r10, r11, r12
    add     r11, r11, #16
    cmp     r11, #32
    bge     tx_huge
tx_scaled:
    rsb     r12, r11, #32
    smull   r2, r3, r1, r10
    mov     r1, r2, lsr r11
    orr     r1, r1, r3, lsl r12
    smull   r2, r3, lr, r10
    mov     lr, r2, lsr r11
    orr     lr, lr, r3, lsl r12
    smull   r2, r3, r5, r10
    mov     r5, r2, lsr r11
    orr     r5, r5, r3, lsl r12
    smull   r2, r3, r6, r10
    mov     r6, r2, lsr r11
    orr     r6, r6, r3, lsl r12
    b       tx_have
tx_huge:
    sub     r12, r11, #31
    mov     r1, r1, asr r12
    mov     lr, lr, asr r12
    mov     r5, r5, asr r12
    mov     r6, r6, asr r12
    mov     r11, #31
    b       tx_scaled
tx_zero:
    mov     r1, #0
    mov     lr, #0
    mov     r5, #0
    mov     r6, #0
tx_have:

    cmp     r1, #0
    rsblt   r2, r1, #0
    movge   r2, r1
    cmp     r5, #0
    rsblt   r3, r5, #0
    movge   r3, r5
    cmp     r3, r2
    movgt   r2, r3
    ldr     r3, [sp, #RF_TEX]
    cmp     r2, #MIP1_STEP
    ldrlt   r2, [r3]
    ldrge   r2, [r3, #4]
    movlt   r3, #0x1F00
    movge   r3, #0x1E00
    str     r2, [sp, #RF_TEXELS]
    str     r3, [sp, #RF_MASK]

    rsb     r0, r0, #8
    ldr     r2, [sp, #RF_J0]
    mov     r2, r2, lsl #4
    add     r2, r2, #8
    sub     r7, r2, r7
    mov     r2, r4, lsl #16
    mov     r2, r2, asr #12
    mul     r3, r1, r0
    add     r2, r2, r3, asr #4
    mul     r3, lr, r7
    add     r2, r2, r3, asr #4
    mov     r3, r4, asr #16
    mov     r3, r3, lsl #4
    mul     r8, r5, r0
    add     r3, r3, r8, asr #4
    mul     r8, r6, r7
    add     r3, r3, r8, asr #4

    mov     r3, r3, lsl #19
    mov     r3, r3, lsr #19
    add     r3, r3, r2, lsl #19
    add     r3, r3, #0x40000
    str     r3, [sp, #RF_ROWB]
    add     r6, r6, lr, lsl #19
    str     r6, [sp, #RF_PDY]
    add     r5, r5, r1, lsl #19
    str     r5, [sp, #RF_PDX]

rf_edges:
    add     r0, sp, #RF_A
    ldmia   r0, {r1-r3}
    ldr     r10, [sp, #RF_LONGL]
    ldr     r9, [sp, #RF_J0]
    ldr     r8, =lut_delta
    cmp     r10, #0
    movne   r0, r3
    moveq   r0, r2
    EDGE2   r4, r5, r1, r0, r9
    ldr     r6, [sp, #RF_JM]
    cmp     r6, r9
    beq     1f
    mov     r6, #1
    str     r6, [sp, #RF_SECTION]
    cmp     r10, #0
    movne   r0, r2
    moveq   r0, r3
    EDGE2   r6, r7, r1, r0, r9
    b       2f
1:  mov     r0, #0
    str     r0, [sp, #RF_SECTION]
    ldr     r0, [sp, #RF_BOT]
    str     r0, [sp, #RF_END]
    cmp     r10, #0
    movne   r1, r2
    movne   r0, r3
    moveq   r1, r3
    moveq   r0, r2
    EDGE2   r6, r7, r1, r0, r9
2:
    cmp     r10, #0
    bne     3f
    mov     r0, r4
    mov     r4, r6
    mov     r6, r0
    mov     r0, r5
    mov     r5, r7
    mov     r7, r0
3:  ldr     r0, [sp, #RF_FB]
    rsb     r1, r9, r9, lsl #4
    add     r8, r0, r1, lsl #4
    ldrb    r0, [sp, #RF_MODE]
    cmp     r0, #RM_TEX
    beq     rf_tex
    cmp     r0, #RM_TINT
    beq     tn_start
    cmp     r0, #RM_FLAT
    bne     tc_start

    ldrb    r2, [sp, #RF_MODE + 1]
    orr     r2, r2, r2, lsl #8
    orr     r2, r2, r2, lsl #16
    adr     r0, fl_section
    str     r0, [sp, #RF_LOOP]
fl_section:
    ldr     r9, [sp, #RF_END]
    cmp     r8, r9
    bhs     rf_section2
fl_row:
    mov     r0, r4, asr #16
    cmp     r0, #0
    movlt   r0, #0
    mov     r3, r6, asr #16
    cmp     r3, #FRAME_WIDTH
    movgt   r3, #FRAME_WIDTH
    subs    r3, r3, r0
    ble     1f
    add     r0, r8, r0
    bl      FillFlat
1:  add     r4, r4, r5
    add     r6, r6, r7
    add     r8, r8, #FRAME_STRIDE
    cmp     r8, r9
    blo     fl_row
    b       rf_section2

tn_start:
    adr     r0, tn_section
    str     r0, [sp, #RF_LOOP]
tn_section:
    ldr     r9, [sp, #RF_END]
    cmp     r8, r9
    bhs     rf_section2
tn_row:
    mov     r0, r4, asr #16
    cmp     r0, #0
    movlt   r0, #0
    mov     r3, r6, asr #16
    cmp     r3, #FRAME_WIDTH
    movgt   r3, #FRAME_WIDTH
    subs    r3, r3, r0
    ble     1f
    add     r0, r8, r0
    bl      FillTint
1:  add     r4, r4, r5
    add     r6, r6, r7
    add     r8, r8, #FRAME_STRIDE
    ldr     r9, [sp, #RF_END]
    cmp     r8, r9
    blo     tn_row
    b       rf_section2

rf_section2:
    ldr     r0, [sp, #RF_SECTION]
    cmp     r0, #0
    beq     rf_done
    mov     r0, #0
    str     r0, [sp, #RF_SECTION]
    ldr     r0, [sp, #RF_BOT]
    cmp     r8, r0
    bhs     rf_done
    str     r0, [sp, #RF_END]
    add     r0, sp, #RF_KEEP
    stmia   r0, {r2, r8, r11, r12, lr}
    ldr     r10, [sp, #RF_LONGL]
    ldr     r9, [sp, #RF_JM]
    ldr     r8, =lut_delta
    cmp     r10, #0
    ldrne   r1, [sp, #RF_B]
    ldrne   r0, [sp, #RF_C]
    ldreq   r1, [sp, #RF_C]
    ldreq   r0, [sp, #RF_B]
    cmp     r10, #0
    bne     1f
    EDGE2   r4, r5, r1, r0, r9
    b       2f
1:  EDGE2   r6, r7, r1, r0, r9
2:  add     r0, sp, #RF_KEEP
    ldmia   r0, {r2, r8, r11, r12, lr}
    ldr     pc, [sp, #RF_LOOP]
rf_done:
    ldr     pc, [sp, #RF_RET]

rf_tex:
    ldr     r2, [sp, #RF_PDX]
    ldr     r11, [sp, #RF_PDY]
    ldr     r12, [sp, #RF_TEXELS]
    ldr     lr, [sp, #RF_ROWB]
    add     r0, sp, #RF_A
    ldmia   r0, {r0, r1, r3}
    mov     r0, r0, lsl #16
    mov     r1, r1, lsl #16
    mov     r3, r3, lsl #16
    cmp     r0, r1
    movgt   r9, r1
    movle   r9, r0
    movlt   r0, r1
    cmp     r3, r9
    movlt   r9, r3
    cmp     r3, r0
    movgt   r0, r3
    ldr     r1, [sp, #RF_MASK]
    cmp     r9, #16 << 16
    blt     1f
    cmp     r0, #(FRAME_WIDTH * 16 - 16) << 16
    bge     1f
    cmp     r1, #0x1F00
    beq     t0u_start
    b       t1u_start
1:  cmp     r1, #0x1F00
    bne     t1_start
t0_start:
    adr     r0, t0_section
    str     r0, [sp, #RF_LOOP]
t0_section:
    ldr     r9, [sp, #RF_END]
    cmp     r8, r9
    bhs     rf_section2
t0_row:
    mov     r0, r4, asr #16
    cmp     r0, #0
    movlt   r0, #0
    mov     r3, r6, asr #16
    cmp     r3, #FRAME_WIDTH
    movgt   r3, #FRAME_WIDTH
    subs    r3, r3, r0
    ble     69f
    mla     r1, r0, r2, lr
    add     r0, r8, r0
    SPAN_TEX #0x1F00
69: add     lr, lr, r11
    add     r4, r4, r5
    add     r6, r6, r7
    add     r8, r8, #FRAME_STRIDE
    ldr     r9, [sp, #RF_END]
    cmp     r8, r9
    blo     t0_row
    b       rf_section2
t1_start:
    adr     r0, t1_section
    str     r0, [sp, #RF_LOOP]
t1_section:
    ldr     r9, [sp, #RF_END]
    cmp     r8, r9
    bhs     rf_section2
t1_row:
    mov     r0, r4, asr #16
    cmp     r0, #0
    movlt   r0, #0
    mov     r3, r6, asr #16
    cmp     r3, #FRAME_WIDTH
    movgt   r3, #FRAME_WIDTH
    subs    r3, r3, r0
    ble     69f
    mla     r1, r0, r2, lr
    add     r0, r8, r0
    SPAN_TEX #0x1E00
69: add     lr, lr, r11
    add     r4, r4, r5
    add     r6, r6, r7
    add     r8, r8, #FRAME_STRIDE
    ldr     r9, [sp, #RF_END]
    cmp     r8, r9
    blo     t1_row
    b       rf_section2
t0u_start:
    adr     r0, t0u_section
    str     r0, [sp, #RF_LOOP]
t0u_section:
    ldr     r9, [sp, #RF_END]
    cmp     r8, r9
    bhs     rf_section2
t0u_row:
    mov     r0, r4, asr #16
    rsbs    r3, r0, r6, asr #16
    ble     69f
    mla     r1, r0, r2, lr
    add     r0, r8, r0
    SPAN_TEX #0x1F00
69: add     lr, lr, r11
    add     r4, r4, r5
    add     r6, r6, r7
    add     r8, r8, #FRAME_STRIDE
    ldr     r9, [sp, #RF_END]
    cmp     r8, r9
    blo     t0u_row
    b       rf_section2
t1u_start:
    adr     r0, t1u_section
    str     r0, [sp, #RF_LOOP]
t1u_section:
    ldr     r9, [sp, #RF_END]
    cmp     r8, r9
    bhs     rf_section2
t1u_row:
    mov     r0, r4, asr #16
    rsbs    r3, r0, r6, asr #16
    ble     69f
    mla     r1, r0, r2, lr
    add     r0, r8, r0
    SPAN_TEX #0x1E00
69: add     lr, lr, r11
    add     r4, r4, r5
    add     r6, r6, r7
    add     r8, r8, #FRAME_STRIDE
    ldr     r9, [sp, #RF_END]
    cmp     r8, r9
    blo     t1u_row
    b       rf_section2

tc_start:
    ldr     r1, =engine_fill_table
    ldr     r1, [r1, r0, lsl #2]
    str     r1, [sp, #RF_FILL]
    ldr     r2, [sp, #RF_PDX]
    ldr     r11, [sp, #RF_MASK]
    ldr     r12, [sp, #RF_TEXELS]
    adr     r0, tc_section
    str     r0, [sp, #RF_LOOP]
tc_section:
    ldr     r9, [sp, #RF_END]
    cmp     r8, r9
    bhs     rf_section2
tc_row:
    mov     r0, r4, asr #16
    cmp     r0, #0
    movlt   r0, #0
    mov     r3, r6, asr #16
    cmp     r3, #FRAME_WIDTH
    movgt   r3, #FRAME_WIDTH
    subs    r3, r3, r0
    ble     1f
    ldr     r1, [sp, #RF_ROWB]
    mla     r1, r0, r2, r1
    add     r0, r8, r0
    mov     lr, pc
    ldr     pc, [sp, #RF_FILL]
1:  ldr     r0, [sp, #RF_ROWB]
    ldr     r1, [sp, #RF_PDY]
    add     r0, r0, r1
    str     r0, [sp, #RF_ROWB]
    add     r4, r4, r5
    add     r6, r6, r7
    add     r8, r8, #FRAME_STRIDE
    ldr     r9, [sp, #RF_END]
    cmp     r8, r9
    blo     tc_row
    b       rf_section2
    .pool

edge_slope_slow2:
    cmp     r12, #0
    movle   r11, #0
    bxle    lr
    stmfd   sp!, {r4, r5, lr}
    RECIP   r12, r4, r5
    add     r4, r4, #8
    mul     r5, r12, r11
    mov     r11, r5, asr r4
    ldmfd   sp!, {r4, r5, lr}
    bx      lr
    .pool

    .global FillTexAlpha
FillTexAlpha:
    tst     r0, #1
    beq     1f
    TEXEL   r10
    cmp     r10, #0
    beq     0f
    ldrb    r9, [r0, #-1]
    orr     r9, r9, r10, lsl #8
    strh    r9, [r0, #-1]
0:  add     r0, r0, #1
    subs    r3, r3, #1
    bxeq    lr
1:  subs    r3, r3, #2
    blt     5f
2:  TEXEL   r10
    TEXEL   r9
    cmp     r10, #0
    beq     3f
    cmp     r9, #0
    orrne   r10, r10, r9, lsl #8
    strhne  r10, [r0]
    bne     4f
    ldrb    r9, [r0, #1]
    orr     r10, r10, r9, lsl #8
    strh    r10, [r0]
    b       4f
3:  cmp     r9, #0
    beq     4f
    ldrb    r10, [r0]
    orr     r10, r10, r9, lsl #8
    strh    r10, [r0]
4:  add     r0, r0, #2
    subs    r3, r3, #2
    bge     2b
5:  adds    r3, r3, #2
    bxeq    lr
    TEXEL   r10
    cmp     r10, #0
    bxeq    lr
    ldrb    r9, [r0, #1]
    orr     r10, r10, r9, lsl #8
    strh    r10, [r0]
    bx      lr

    .global FillTint
FillTint:
    ldr     r12, =g_shade_water
    tst     r0, #1
    beq     1f
    ldrh    r1, [r0, #-1]
    and     r2, r1, #0xFF
    ldrb    r1, [r12, r1, lsr #8]
    orr     r1, r2, r1, lsl #8
    strh    r1, [r0, #-1]
    add     r0, r0, #1
    subs    r3, r3, #1
    bxeq    lr
1:  tst     r0, #2
    beq     2f
    cmp     r3, #2
    blt     5f
    ldrh    r1, [r0]
    and     r2, r1, #0xFF
    ldrb    r2, [r12, r2]
    ldrb    r1, [r12, r1, lsr #8]
    orr     r1, r2, r1, lsl #8
    strh    r1, [r0], #2
    subs    r3, r3, #2
    bxeq    lr
2:  subs    r3, r3, #4
    blt     4f
3:  ldr     r1, [r0]
    and     r2, r1, #0xFF
    ldrb    r2, [r12, r2]
    and     r10, r1, #0xFF00
    ldrb    r10, [r12, r10, lsr #8]
    orr     r2, r2, r10, lsl #8
    and     r10, r1, #0xFF0000
    ldrb    r10, [r12, r10, lsr #16]
    orr     r2, r2, r10, lsl #16
    ldrb    r10, [r12, r1, lsr #24]
    orr     r2, r2, r10, lsl #24
    str     r2, [r0], #4
    subs    r3, r3, #4
    bge     3b
4:  adds    r3, r3, #4
    bxeq    lr
    cmp     r3, #2
    blt     5f
    ldrh    r1, [r0]
    and     r2, r1, #0xFF
    ldrb    r2, [r12, r2]
    ldrb    r1, [r12, r1, lsr #8]
    orr     r1, r2, r1, lsl #8
    strh    r1, [r0], #2
    subs    r3, r3, #2
    bxeq    lr
5:  ldrh    r1, [r0]
    and     r2, r1, #0xFF
    ldrb    r2, [r12, r2]
    bic     r1, r1, #0xFF
    orr     r1, r1, r2
    strh    r1, [r0]
    bx      lr

    .global FillDarken
FillDarken:
    stmfd   sp!, {r4, lr}
    ldr     r4, =shade_darken
1:  TEXEL   r10
    cmp     r10, #0
    beq     3f
    ldrb    r10, [r0]
    ldrb    r10, [r4, r10]
    tst     r0, #1
    beq     2f
    ldrb    r9, [r0, #-1]
    orr     r9, r9, r10, lsl #8
    strh    r9, [r0, #-1]
    b       3f
2:  ldrb    r9, [r0, #1]
    orr     r9, r10, r9, lsl #8
    strh    r9, [r0]
3:  add     r0, r0, #1
    subs    r3, r3, #1
    bne     1b
    ldmfd   sp!, {r4, lr}
    bx      lr
    .pool

    .global FillFlat
FillFlat:
    tst     r0, #1
    beq     1f
    ldrb    r1, [r0, #-1]
    orr     r1, r1, r2, lsl #8
    strh    r1, [r0, #-1]
    add     r0, r0, #1
    subs    r3, r3, #1
    bxeq    lr
1:  cmp     r3, #2
    blt     6f
    tst     r0, #2
    beq     2f
    strh    r2, [r0], #2
    sub     r3, r3, #2
2:  subs    r3, r3, #16
    blt     3f
20: str     r2, [r0], #4
    str     r2, [r0], #4
    str     r2, [r0], #4
    str     r2, [r0], #4
    subs    r3, r3, #16
    bge     20b
3:  adds    r3, r3, #16
    bxeq    lr
4:  subs    r3, r3, #4
    blt     5f
    str     r2, [r0], #4
    b       4b
5:  adds    r3, r3, #4
    bxeq    lr
    cmp     r3, #2
    blt     6f
    strh    r2, [r0], #2
    subs    r3, r3, #2
    bxeq    lr
6:  ldrb    r1, [r0, #1]
    and     r3, r2, #0xFF
    orr     r1, r3, r1, lsl #8
    strh    r1, [r0]
    bx      lr

    .section .text.engine_additive, "ax", %progbits
    .global FillAdditive
FillAdditive:
    stmfd   sp!, {r4, r5, lr}
    ldr     r4, =g_additive_rows
    ldr     r4, [r4]
    ldr     r5, =g_additive_table
    ldr     r5, [r5]
1:  TEXEL   r10
    add     r10, r4, r10, lsl #1
    ldrh    r10, [r10]
    ldrb    r9, [r0]
    add     r10, r9, r10, lsl #8
    ldrb    r10, [r5, r10]
    tst     r0, #1
    beq     2f
    ldrb    r9, [r0, #-1]
    orr     r9, r9, r10, lsl #8
    strh    r9, [r0, #-1]
    b       3f
2:  ldrb    r9, [r0, #1]
    orr     r9, r10, r9, lsl #8
    strh    r9, [r0]
3:  add     r0, r0, #1
    subs    r3, r3, #1
    bne     1b
    ldmfd   sp!, {r4, r5, lr}
    bx      lr
    .pool

    .section .rodata.engine, "a", %progbits
    .align 2
    .global engine_fill_table
engine_fill_table:
    .word   FillFlat, 0, FillTexAlpha, FillAdditive, FillDarken, 0
    .global engine_recip_table
engine_recip_table:
    .set m, 256
    .rept 256
    .if m == 256
    .hword 65535
    .else
    .hword (16777216 + m / 2) / m
    .endif
    .set m, m + 1
    .endr
