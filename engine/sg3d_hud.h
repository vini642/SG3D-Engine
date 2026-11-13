#ifndef SG3D_HUD_H
#define SG3D_HUD_H
#include <stdint.h>
/* GBA full-resolution HUD overlay: 3D remains 120x80 scaled to 240x160,
   while glyphs and PNG images use 240x160 native OBJ hardware sprites.
   Existing project element coordinates remain 120x80 logical units (x2 on
   the display) for backward compatibility. Rectangles and bars are low-res.
   RGB332 palette. OBJ palette index 0 is transparent. */
typedef struct {
    uint8_t kind,x,y,w,h,fg,bg,visible;
    int16_t value,maximum;
    const char *text;
    const uint8_t *sprite; /* packed 8-bit RGB332, 0 transparent */
} SG3DHUDItem;
#define SG3D_HUD_TEXT 1
#define SG3D_HUD_BAR 2
#define SG3D_HUD_RECT 3
#define SG3D_HUD_SPRITE 4
#define SG3D_HUD_DIALOGUE 5
void sg3d_hud_init(void);
void sg3d_hud_present_oam(void); /* call during VBlank */
unsigned sg3d_hud_dropped_sprites(void);
void sg3d_hud_load(const SG3DHUDItem *items,unsigned count);
void sg3d_hud_set_value(unsigned item,int32_t value);
void sg3d_hud_set_visible(unsigned item,unsigned visible);
void sg3d_hud_profiler(unsigned enabled);
void sg3d_hud_begin_frame(void);
void sg3d_hud_render(unsigned page,unsigned triangles,unsigned objects);
#endif
