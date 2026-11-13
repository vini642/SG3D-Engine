/* Standalone demo game: original SMG ARM assembly pixels, new scene/mesh API.
   No Super Mario Galaxy models, textures or ISO are needed. */
#include <stdint.h>
#include "sg3d.h"
#include "pyramid_mesh.h"

#define KEYS (*(volatile uint16_t *)0x04000130)
#define KEY_A 1
#define KEY_B 2
#define KEY_SELECT 4
#define KEY_START 8
#define KEY_RIGHT 16
#define KEY_LEFT 32
#define KEY_UP 64
#define KEY_DOWN 128
#define KEY_R 256
#define KEY_L 512
#define EWRAM __attribute__((section(".ewram_bss")))

#define U(u,v) SG3D_UV(u,v)
static const SG3DVertex cube_v[]={
    {-256,-256,-256},{256,-256,-256},{256,256,-256},{-256,256,-256},
    {-256,-256,256},{256,-256,256},{256,256,256},{-256,256,256}
};
#define C(a,b,c,f,ua,ub,uc) {a,b,c,f,0,{ua,ub,uc}}
static const SG3DFace cube_f[]={
 C(4,5,6,0,U(0,0),U(512,0),U(512,512)), C(4,6,7,0,U(0,0),U(512,512),U(0,512)),
 C(1,0,3,1,U(0,0),U(512,0),U(512,512)), C(1,3,2,1,U(0,0),U(512,512),U(0,512)),
 C(0,4,7,2,U(0,0),U(512,0),U(512,512)), C(0,7,3,2,U(0,0),U(512,512),U(0,512)),
 C(5,1,2,3,U(0,0),U(512,0),U(512,512)), C(5,2,6,3,U(0,0),U(512,512),U(0,512)),
 C(3,7,6,4,U(0,0),U(512,0),U(512,512)), C(3,6,2,4,U(0,0),U(512,512),U(0,512)),
 C(0,1,5,5,U(0,0),U(512,0),U(512,512)), C(0,5,4,5,U(0,0),U(512,512),U(0,512)),
};
static const SG3DMesh cube_mesh={cube_v,8,cube_f,12};
static uint8_t tex[6][2][1024] EWRAM;
static SG3DTexture texref[6];
static SG3DMaterial mats[6];

static void assets_init(void){
    /* The six effects share the exact same RGB332 palette mapping. */
    sg3d_palette_rgb332();
    sg3d_effects_rgb332_init();
    static const uint8_t face_color[6]={224,28,3,252,227,31};
    for(unsigned f=0;f<6;f++){
        uint8_t base=face_color[f];
        uint8_t dim=(uint8_t)(((base>>5)>>1)<<5|((((base>>2)&7)>>1)<<2)|((base&3)>>1));
        for(unsigned mip=0;mip<2;mip++){
            unsigned side=mip?16:32;
            for(unsigned y=0;y<side;y++)for(unsigned x=0;x<side;x++){
                unsigned check=((x>>(mip?2:3))^(y>>(mip?2:3)))&1;
                /* Occasional transparent texels exercise ALPHA/DARKEN modes. */
                tex[f][mip][y*side+x]=(uint8_t)((x+y)%19==0?0:(check?base:dim));
            }
        }
        sg3d_texture_init(&texref[f],tex[f][0],tex[f][1]);
        mats[f]=(SG3DMaterial){&texref[f],base,SG3D_TEXTURED};
    }
}

int main(void){
    sg3d_init();assets_init();
    int turn=0, cam_yaw=0, cam_pitch=0, cam_x=0, cam_z=0;
    int scene=0, mode=SG3D_TEXTURED, paused=0;
    unsigned last=0;
    for(;;){
        unsigned keys=(~KEYS)&1023;
        if((keys&KEY_A)&&!(last&KEY_A))scene=(scene+1)%3;
        if((keys&KEY_B)&&!(last&KEY_B))mode=(mode+1)%6;
        if((keys&KEY_START)&&!(last&KEY_START))paused=!paused;
        if((keys&KEY_SELECT)&&!(last&KEY_SELECT)){
            turn=0;cam_yaw=0;cam_pitch=0;cam_x=0;cam_z=0;
        }
        if(keys&KEY_L)cam_yaw-=2;
        if(keys&KEY_R)cam_yaw+=2;
        if(keys&KEY_UP)cam_z+=12;
        if(keys&KEY_DOWN)cam_z-=12;
        if(keys&KEY_LEFT)cam_x-=12;
        if(keys&KEY_RIGHT)cam_x+=12;
        last=keys;
        if(!paused){turn++;}
        SG3DCamera cam={cam_x,0,cam_z,(uint8_t)cam_yaw,(uint8_t)cam_pitch};
        sg3d_set_camera(cam);
        sg3d_begin(0,1);
        for(unsigned i=0;i<6;i++)mats[i].mode=(uint8_t)mode;
        if(scene==0){
            SG3DTransform transform={0,0,1200,(uint8_t)turn,(uint8_t)(turn/2),256};
            sg3d_draw_mesh(&cube_mesh,mats,6,transform);
        } else if(scene==1){
            SG3DTransform a={-340,0,1500,(uint8_t)turn,0,256};
            SG3DTransform b={340,0,1500,(uint8_t)(-turn),0,256};
            sg3d_draw_mesh(&cube_mesh,mats,6,a);
            sg3d_draw_mesh(&pyramid_mesh,mats,6,b);
        } else {
            for(int z=0;z<3;z++)for(int x=-1;x<=1;x++){
                SG3DTransform t={x*560,0,1300+z*700,(uint8_t)(turn+x*24),0,170};
                sg3d_draw_mesh(((x+z)&1)?&cube_mesh:&pyramid_mesh,mats,6,t);
            }
        }
        sg3d_end();
    }
}
