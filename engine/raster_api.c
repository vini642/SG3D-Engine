#include <stdint.h>
#include <stddef.h>
#include "sg3d.h"
/* Exact memory layout expected by the original ARM engine_raster routine. */
typedef struct {
    uint16_t next;
    uint8_t mode, colour;
    uint32_t s[3], uv[3];
    const SG3DTexture *texture;
} DrawEntry;
_Static_assert(sizeof(DrawEntry) == 32, "raster.s DrawEntry ABI changed");
extern void engine_raster(const DrawEntry *entry);
uint8_t *g_engine_fb;
/* The fill-mode lookup tables are initialized by sg3d_effects_rgb332_init. */
uint8_t g_shade_water[256];
uint8_t shade_darken[256];
const uint16_t *g_additive_rows;
const uint8_t *g_additive_table;

void sg3d_internal_framebuffer(uint8_t *fb) { g_engine_fb = fb; }
void sg3d_internal_triangle(const uint32_t s[3], const uint32_t uv[3],
                            uint8_t color, const SG3DTexture *tex, uint8_t mode) {
    DrawEntry e = {0};
    e.next = 0xffff;
    e.mode = mode;
    e.colour = color;
    for(unsigned i=0;i<3;i++){ e.s[i]=s[i]; e.uv[i]=uv[i]; }
    e.texture = tex;
    engine_raster(&e);
}
