#include "sg3d_facing.h"
#include <assert.h>
#include <stdio.h>
static void direction(int dx, int dz, int expected) {
    SG3DFacing f={0,0,1,255,0,0,0};
    SG3DTransform t={0,0,0,0,0,256};
    sg3d_facing_capture(&f,&t);
    t.x=dx;t.z=dz;
    sg3d_facing_update(&f,&t);
    assert(t.yaw==(uint8_t)expected);
}
int main(void) {
    direction(0,256,0);direction(256,0,64);
    direction(0,-256,128);direction(-256,0,192);
    direction(256,256,32);direction(-256,256,224);
    direction(256,-256,96);direction(-256,-256,160);
    SG3DFacing f={0,0,1,64,0,0,0};
    SG3DTransform t={0,0,0,0,0,256};
    sg3d_facing_capture(&f,&t);t.x=256;
    sg3d_facing_update(&f,&t);
    assert(t.yaw>0 && t.yaw<64);
    uint8_t saved=t.yaw;
    sg3d_facing_capture(&f,&t);
    sg3d_facing_update(&f,&t);
    assert(t.yaw>saved && t.yaw<64); /* finish turn while standing still */
    f.offset=128;f.smoothing=255;
    sg3d_facing_capture(&f,&t);t.x+=256;
    sg3d_facing_update(&f,&t);
    assert(t.yaw==192); /* backwards-facing model */
    f.enabled=0;sg3d_facing_capture(&f,&t);t.z+=256;
    sg3d_facing_update(&f,&t);
    assert(t.yaw==192); /* disabled means unchanged */
    printf("Facing directions, easing, offset, idle and disabled: PASS\n");
    return 0;
}
