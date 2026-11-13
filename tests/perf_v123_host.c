/* Native randomized transform/cull regression (no GBA MMIO calls) */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include "../engine/sg3d.c"
void sg3d_internal_framebuffer(uint8_t *p){(void)p;}
void sg3d_internal_triangle(const uint32_t *a,const uint32_t *b,uint8_t c,const SG3DTexture *t,uint8_t m){(void)a;(void)b;(void)c;(void)t;(void)m;}
static uint32_t seed=0xDEADBEEF;
static uint32_t rand32(void){seed=seed*1664525u+1013904223u;return seed;}
static int rnd(int a,int b){return a+(int)(rand32() % (unsigned)(b-a+1));}
static int32_t abs32(int32_t v){return v<0?-v:v;}
int main(void){
    unsigned max_error=0,culled=0;
    for(unsigned i=0;i<18000;i++){
        camera=(SG3DCamera){rnd(-1200,1200),rnd(-1200,1200),rnd(-1200,1200),rnd(0,255),rnd(0,255)};
        SG3DTransform t={rnd(-4000,4000),rnd(-3000,3000),rnd(-4000,4000),rnd(0,255),rnd(0,255),256};
        int sy=sin_table[t.yaw],cy=sin_table[(uint8_t)(t.yaw+64)];
        int sp=sin_table[t.pitch],cp=sin_table[(uint8_t)(t.pitch+64)];
        int csy=sin_table[(uint8_t)(-camera.yaw)],ccy=sin_table[(uint8_t)(64-camera.yaw)];
        int csp=sin_table[(uint8_t)(-camera.pitch)],ccp=sin_table[(uint8_t)(64-camera.pitch)];
        prepare_view_transform(t,sy,cy,sp,cp,csy,ccy,csp,ccp);
        int32_t x=rnd(-2500,2500),y=rnd(-2500,2500),z=rnd(-2500,2500);
        int32_t xx=x,yy=y,zz=z;
        yaw_rotate(&xx,&zz,sy,cy);pitch_rotate(&yy,&zz,sp,cp);
        xx+=t.x-camera.x;yy+=t.y-camera.y;zz+=t.z-camera.z;
        yaw_rotate(&xx,&zz,csy,ccy);pitch_rotate(&yy,&zz,csp,ccp);
        fused_vertex(&x,&y,&z);
        int d=(int)abs32(x-xx);if((unsigned)d>max_error)max_error=d;
        d=(int)abs32(y-yy);if((unsigned)d>max_error)max_error=d;
        d=(int)abs32(z-zz);if((unsigned)d>max_error)max_error=d;
        /* Radius completely encloses vertices at this camera pose. */
        const SG3DVertex vertices[]={ {-512,-512,-512}, {512,512,512}, {512,-512,512} };
        const SG3DFace face={0,1,2,0,0,{0,0,0},0};
        const SG3DMesh mesh={vertices,3,&face,1,0,0,0,890};
        if(sphere_is_offscreen(&mesh,t,sy,cy,sp,cp,csy,ccy,csp,ccp)){
            culled++;
            for(unsigned v=0;v<3;v++){
                int32_t vx=vertices[v].x,vy=vertices[v].y,vz=vertices[v].z;
                yaw_rotate(&vx,&vz,sy,cy);pitch_rotate(&vy,&vz,sp,cp);
                vx+=t.x-camera.x;vy+=t.y-camera.y;vz+=t.z-camera.z;
                yaw_rotate(&vx,&vz,csy,ccy);pitch_rotate(&vy,&vz,csp,ccp);
                if(vz>=NEAR_Z && vz<=FAR_Z){
                    int sx=60+((vx*project_recip(vz))>>12);
                    int syy=40-((vy*project_recip(vz))>>12);
                    if(sx>=0 && sx<SG3D_WIDTH && syy>=0 && syy<SG3D_HEIGHT){
                        fprintf(stderr,"False cull on visible vertex %u case %u\n",v,i);return 2;
                    }
                }
            }
        }
    }
    printf("transform/cull randomized: max-error=%u (8.8 units), culled=%u/18000, visible verts safely retained\n",max_error,culled);
    return max_error>32 ? 1:0;
}
