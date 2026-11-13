/* RGB332 blending tables for extracted ARM raster modes.
   64 KiB EWRAM, initialized once per game; no floating point and no huge ROM LUT.
   These modes are valid ONLY while using the sg3d_palette_rgb332 palette. */
#include <stdint.h>
#define EWRAM __attribute__((section(".ewram_bss")))
extern uint8_t g_shade_water[256];
extern uint8_t shade_darken[256];
extern const uint16_t *g_additive_rows;
extern const uint8_t *g_additive_table;
static uint8_t additive_lookup[256*256] EWRAM;
static uint16_t rows[256] EWRAM;
static int ready;
void sg3d_effects_rgb332_init(void) {
    if(ready)return;
    ready=1;
    for(unsigned s=0;s<256;s++){
        unsigned sr=(s>>5)&7,sg=(s>>2)&7,sb=s&3;
        rows[s]=(uint16_t)s;
        /* Background tint: a slightly blue, quieter color. */
        unsigned tr=(sr+0)>>1;
        unsigned tg=(sg+2)>>1;
        unsigned tb=(sb+3)>>1;
        if(tg>7)tg=7;if(tb>3)tb=3;
        g_shade_water[s]=(uint8_t)((tr<<5)|(tg<<2)|tb);
        shade_darken[s]=(uint8_t)(((sr>>1)<<5)|((sg>>1)<<2)|(sb>>1));
        for(unsigned d=0;d<256;d++){
            unsigned r=sr+((d>>5)&7),g=sg+((d>>2)&7),b=sb+(d&3);
            if(r>7)r=7;if(g>7)g=7;if(b>3)b=3;
            additive_lookup[s*256+d]=(uint8_t)((r<<5)|(g<<2)|b);
        }
    }
    g_additive_rows=rows;
    g_additive_table=additive_lookup;
}
