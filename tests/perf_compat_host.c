/* Deterministic geometry-equivalence regression: compare with
   -DSG3D_PERF_FAST_CLIP=0 and 1; the digest and counters must match. */
#include <stdio.h>
#include <stdint.h>
#include "../engine/sg3d.c"
void sg3d_internal_framebuffer(uint8_t *b){(void)b;}
void sg3d_internal_triangle(const uint32_t *a, const uint32_t *b, uint8_t c, const SG3DTexture *t, uint8_t m){(void)a;(void)b;(void)c;(void)t;(void)m;}
static uint32_t rng=0x87654321;
static uint32_t next(void){rng = rng*1664525u+1013904223u;return rng;}
static uint32_t hash=2166136261u;
static void feed(uint32_t x){ hash=(hash^x)*16777619u; }
int main(void){
    SG3DFace f={0,1,2,0,0,{0,0,0}};
    SG3DMaterial mat={0,7,SG3D_FLAT};
    SG3DVertex vertices[3];
    SG3DMesh mesh={vertices,3,&f,1};
    for(int k=0;k<2000;k++){
        count=0; stats=(SG3DStats){0};camera=(SG3DCamera){0};
        for(int i=0;i<3;i++){
            vertices[i].x=(int16_t)((int)(next()%16000)-8000);
            vertices[i].y=(int16_t)((int)(next()%16000)-8000);
            vertices[i].z=(int16_t)((int)(next()%12000)-4000);
        }
        SG3DTransform t={0,0,500+(int)(next()%2500),0,0,256};
        sg3d_draw_mesh(&mesh,&mat,1,t);
        feed(stats.submitted);feed(stats.clipped);feed(stats.rejected);feed(stats.dropped);feed(count);
        for(unsigned i=0;i<count;i++){
            const QueuedTri *q=&queue[i];
            feed(q->depth);feed(q->mode);feed(q->color);
            for(int j=0;j<3;j++){ feed(q->screen[j]);feed(q->uv[j]); }
        }
    }
    printf("geometry-hash=%08x\n",hash);
    return 0;
}
