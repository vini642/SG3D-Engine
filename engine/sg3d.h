#ifndef SG3D_H
#define SG3D_H
#include <stdint.h>

/* SMG GBA standalone renderer. Coordinates: 8.8 fixed point (256 = 1 unit).
   Camera looks down positive Z. Y points UP. Angles: 0..255 for full turn.
   Internally renders at 120x80 then hardware-scaled to 240x160. */
#define SG3D_WIDTH 120
#define SG3D_HEIGHT 80
#define SG3D_MAX_VERTICES 256
#define SG3D_MAX_TRIANGLES 384
#define SG3D_UV(u,v) ((uint32_t)(uint16_t)(u) | ((uint32_t)(uint16_t)(v)<<16))

typedef struct { int16_t x, y, z; } SG3DVertex;
typedef struct {
    uint16_t a, b, c;
    uint8_t material, flags;
    uint32_t uv[3];
    uint8_t solid_color; /* used only if SG3D_FACE_SOLID_TEX flag is set */
    uint8_t tiny_color; /* used only if SG3D_FACE_TINY_TEX flag is set */
} SG3DFace;
#define SG3D_CULL_BACK 1u
#define SG3D_FACE_SOLID_TEX 2u /* exporter proved this triangle samples one RGB332 color */
#define SG3D_FACE_TINY_TEX 4u /* exporter computed a representative distant-polygon color */

typedef struct {
    const SG3DVertex *vertices;
    uint16_t vertex_count;
    const SG3DFace *faces;
    uint16_t face_count;
    /* Conservative mesh-space bounding sphere, 8.8 units; radius==0 disables culling.
       Legacy four-field initializers remain valid and are NOT culled automatically. */
    int16_t bound_x, bound_y, bound_z;
    uint16_t bound_radius;
} SG3DMesh;

/* Each mip is a pointer to palette indices, with mip[0] 32x32 and mip[1]
   16x16 or 32x32. Transparent mode treats palette index zero as clear. */
typedef struct { uint32_t mip[2]; } SG3DTexture;
typedef enum {
    SG3D_FLAT=0, SG3D_TEXTURED=1, SG3D_ALPHA=2,
    SG3D_ADDITIVE=3, SG3D_DARKEN=4, SG3D_TINT=5
} SG3DMode;
typedef struct {
    const SG3DTexture *texture;
    uint8_t color, mode;
} SG3DMaterial;
typedef struct { int32_t x,y,z; uint8_t yaw,pitch; } SG3DCamera;
typedef struct {
    int32_t x,y,z;
    uint8_t yaw,pitch;
    uint16_t scale; /* 256 = normal size; 0 also means normal size */
} SG3DTransform;
typedef struct {
    uint16_t submitted, drawn, clipped, rejected, dropped;
    uint16_t culled_objects, cached_vertices, solid_triangles, tiny_triangles;
} SG3DStats;

/* Palette colors are 15-bit BGR. Indices 0..255. */
void sg3d_init(void);
void sg3d_set_palette(unsigned index, uint16_t color);
/* Optional RGB332 color palette/effect mappings for blending modes 3-5.
   RGB332 must be used together with the RGB332 effect LUTs.
   Call once after sg3d_init, before rendering. Index 0 is transparent. */
void sg3d_palette_rgb332(void);
void sg3d_effects_rgb332_init(void);
void sg3d_set_camera(SG3DCamera camera);
/* Panorama is RGB332 256x128 in ROM. Horizontal wrap follows camera yaw. */
void sg3d_set_skybox(const uint8_t *pixels);
void sg3d_begin(uint8_t sky_color, uint8_t ground_color);
void sg3d_draw_mesh(const SG3DMesh *mesh, const SG3DMaterial *materials,
                    unsigned material_count, SG3DTransform transform);
void sg3d_end(void); /* global painter sort -> original ARM assembly rasterizer -> VBlank flip */
SG3DStats sg3d_stats(void);

/* Build references from 32x32/16x16 8bpp palette textures in RAM/ROM. */
void sg3d_texture_init(SG3DTexture *out, const uint8_t *mip0, const uint8_t *mip1);
uint16_t sg3d_rgb(unsigned r, unsigned g, unsigned b);

#endif
