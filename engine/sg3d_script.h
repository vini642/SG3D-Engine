#ifndef SG3D_SCRIPT_H
#define SG3D_SCRIPT_H
/* Public, genre-neutral SG3D user scripting API.
 * Coordinates and velocities are signed 24.8 fixed point (256 = 1.0).
 * Angles use unsigned 8-bit turns (256 units = 360 degrees).
 * No runtime interpreter: the build compiles your .c files into the ROM.
 */
#include <stdint.h>
#include "sg3d.h"
#include "sg3d_physics.h"

enum {
    SG3D_KEY_A=1u, SG3D_KEY_B=2u, SG3D_KEY_SELECT=4u, SG3D_KEY_START=8u,
    SG3D_KEY_RIGHT=16u, SG3D_KEY_LEFT=32u, SG3D_KEY_UP=64u,
    SG3D_KEY_DOWN=128u, SG3D_KEY_R=256u, SG3D_KEY_L=512u
};
#define SG3D_UNIT(n) ((int32_t)(n)*256)
#define SG3D_ANGLE(degrees) ((uint8_t)((degrees)*256/360))

typedef struct { const char *name; int32_t value; } SG3DProperty;
typedef struct {
    SG3DTransform *transform;
    SG3DPhysicsBody *body;
    SG3DProperty *properties;
    unsigned property_count;
} SG3DScriptActor;
typedef struct {
    SG3DScriptActor *actors;
    unsigned actor_count;
    SG3DCamera *camera;
    uint16_t held, pressed;
    volatile int *requested_scene; /* null in single-scene projects */
} SG3DScriptContext;

int sg3d_key_held(const SG3DScriptContext *ctx,uint16_t key);
int sg3d_key_pressed(const SG3DScriptContext *ctx,uint16_t key);
SG3DTransform *sg3d_object(SG3DScriptContext *ctx,unsigned id);
SG3DPhysicsBody *sg3d_body(SG3DScriptContext *ctx,unsigned id);
int32_t sg3d_get_property(SG3DScriptContext *ctx,unsigned id,const char *name);
int sg3d_set_property(SG3DScriptContext *ctx,unsigned id,const char *name,int32_t value);
void sg3d_move_object(SG3DScriptContext *ctx,unsigned id,int32_t dx,int32_t dy,int32_t dz);
/* side is +X, forward is +Z; rotated using camera or object's yaw. */
void sg3d_move_camera_space(SG3DScriptContext *ctx,unsigned id,int32_t side,int32_t forward);
void sg3d_move_local(SG3DScriptContext *ctx,unsigned id,int32_t side,int32_t forward);
void sg3d_rotate_object(SG3DScriptContext *ctx,unsigned id,int yaw_delta,int pitch_delta);
void sg3d_set_velocity(SG3DScriptContext *ctx,unsigned id,int32_t vx,int32_t vy,int32_t vz);
void sg3d_jump_object(SG3DScriptContext *ctx,unsigned id,int32_t impulse);
int sg3d_is_grounded(SG3DScriptContext *ctx,unsigned id);
int sg3d_is_touching(SG3DScriptContext *ctx,unsigned a,unsigned b);
void sg3d_load_scene(SG3DScriptContext *ctx,unsigned scene_id);

/* Attach scripts to any object using its c_scripts list in .sg3d.json.
 * File "my_logic.c" supplies the following callbacks; all three are required:
 * void my_logic_Start(SG3DScriptContext *ctx, unsigned self);
 * void my_logic_Update(SG3DScriptContext *ctx, unsigned self);
 * void my_logic_Collision(SG3DScriptContext *ctx, unsigned self, unsigned other);
 */
#endif
