/* Native tests of the C mesh projection/clip and queue, no GBA IO occurs. */
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include "../engine/sg3d.c"
void sg3d_internal_framebuffer(uint8_t *b) {(void)b;}
void sg3d_internal_triangle(const uint32_t s[3],const uint32_t uv[3],
                            uint8_t c,const SG3DTexture *t,uint8_t mode){
    (void)s;(void)uv;(void)c;(void)t;(void)mode;
}
static void reset_stats(void){ count=0; stats=(SG3DStats){0}; camera=(SG3DCamera){0}; }
int main(void){
    const SG3DVertex v[]={{-256,-256,0},{256,-256,0},{0,256,0}};
    const SG3DFace face[]={ {0,1,2,0,0,{0,0,0}} };
    const SG3DMesh mesh={v,3,face,1};
    const SG3DMaterial mat[]={{0,15,SG3D_FLAT}};
    reset_stats();
    sg3d_draw_mesh(&mesh,mat,1,(SG3DTransform){0,0,1200,0,0,256});
    assert(stats.submitted==1 && stats.drawn==0 && count==1 && stats.dropped==0);
    int x=(int16_t)(queue[0].screen[0]&0xffff)/16;
    assert(x>=-100 && x<120);
    /* Fully behind camera = rejected, no memory writes beyond queue. */
    reset_stats();
    sg3d_draw_mesh(&mesh,mat,1,(SG3DTransform){0,0,-512,0,0,256});
    assert(count==0 && stats.rejected==1);
    /* One vertex behind near plane = split into two triangles. */
    const SG3DVertex crossv[]={{-64,-64,-512},{256,-64,0},{0,256,0}};
    const SG3DMesh cross={crossv,3,face,1};
    reset_stats();
    sg3d_draw_mesh(&cross,mat,1,(SG3DTransform){0,0,450,0,0,256});
    assert(stats.submitted==1 && stats.clipped==1 && count>=1 && count<=5);
    /* Several vertices well outside screen = rejected. */
    reset_stats();
    sg3d_draw_mesh(&mesh,mat,1,(SG3DTransform){10000,0,1200,0,0,256});
    assert(count==0 && stats.rejected==1);
    /* Repeated submission bounded by SG3D_MAX_TRIANGLES. */
    reset_stats();
    for(int i=0;i<500;i++)sg3d_draw_mesh(&mesh,mat,1,(SG3DTransform){0,0,1200,0,0,256});
    assert(count==384 && stats.dropped==116);
    puts("Native geometry tests PASSED (projection, near clipping, culling, queue overflow)");
    return 0;
}
