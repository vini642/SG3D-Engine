#ifndef SG3D_PHYSICS_H
#define SG3D_PHYSICS_H
#include "sg3d.h"
/* Small, axis-aligned 8.8 fixed-point physics for GBA. Y axis points UP.
 * Static solids block dynamic objects. Rotation does NOT rotate colliders.
 * Half extents must be positive; dynamic bodies have gravity and jump velocity.
 * No broadphase, slopes, rigid-body dynamics, or continuous rotation collisions.
 */
typedef struct {
    SG3DTransform *transform;
    int32_t hx,hy,hz;
    int32_t vx,vy,vz;
    uint8_t dynamic, solid, grounded;
} SG3DPhysicsBody;
void sg3d_physics_move(SG3DPhysicsBody *b, unsigned n, unsigned who,
                       int32_t dx,int32_t dy,int32_t dz);
void sg3d_physics_step(SG3DPhysicsBody *b,unsigned n,
                       int32_t gravity,int32_t terminal_velocity);
int sg3d_physics_touching(const SG3DPhysicsBody *b,unsigned n,unsigned a,unsigned c);
void sg3d_physics_jump(SG3DPhysicsBody *b,unsigned n,unsigned i,int32_t impulse);
#endif
