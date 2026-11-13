/* v0.4 compact table — values copied from every 16th entry of original table.
   Patched EDGE2 in this demo loads [lut_delta + dy*4] instead of [lut_delta + dy*64].
   Original raster.s is also included unmodified under original_engine_sources/. */
.section .rodata.lut, "a", %progbits
.balign 4
.global lut_delta
lut_delta:
.incbin "engine/lut_delta.bin"
