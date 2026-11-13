/* Native sanity check for the palette effect lookup tables. */
#include <stdint.h>
#include <stdio.h>
uint8_t g_shade_water[256];
uint8_t shade_darken[256];
const uint16_t *g_additive_rows;
const uint8_t *g_additive_table;
extern void sg3d_effects_rgb332_init(void);
int main(void){
    sg3d_effects_rgb332_init();
    if(!g_additive_rows || !g_additive_table)return 1;
    for(int src=0;src<256;src++){
        if(g_additive_rows[src]!=src)return 2;
        for(int dst=0;dst<256;dst++){
            int r=((src>>5)&7)+((dst>>5)&7);
            int g=((src>>2)&7)+((dst>>2)&7);
            int b=(src&3)+(dst&3);
            if(r>7)r=7;if(g>7)g=7;if(b>3)b=3;
            unsigned expected=(r<<5)|(g<<2)|b;
            if(g_additive_table[src*256+dst]!=expected)return 3;
        }
    }
    if(shade_darken[255]!=((3<<5)|(3<<2)|1))return 4;
    if(g_shade_water[0]==0)return 5;
    puts("PASS: 65,536 additive lookups, darken/tint tables");
    return 0;
}
