#ifndef SG3D_FACING_H
#define SG3D_FACING_H
#include "sg3d.h"
/* Visual-only face-movement helper. Coordinates: x/z in SG3D 8.8 units,
   yaw in 256 steps/revolution. No floats or hardware division on the GBA.
   Capture BEFORE scripts/physics; update AFTER animations, BEFORE render.
   Disabled objects preserve their authored/scripted rotation.
   offset = native model forward-axis correction (angle byte).
   smoothing: 1..255 (255 is instant), ~64 = gentle 25%% turn/frame.
*/
typedef struct {
    int32_t previous_x, previous_z;
    uint8_t enabled, smoothing, offset, target, has_target;
} SG3DFacing;
void sg3d_facing_capture(SG3DFacing *state, const SG3DTransform *transform);
void sg3d_facing_update(SG3DFacing *state, SG3DTransform *transform);
#endif
