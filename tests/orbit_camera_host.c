#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include "sg3d_controls.h"
#include "sin_table.h"
static int32_t mul8(int32_t a,int32_t b){return (a*b)>>8;}
static void view(SG3DCamera camera,int32_t *x,int32_t *y,int32_t *z){
    int32_t dx=*x-camera.x,dy=*y-camera.y,dz=*z-camera.z;
    int sy=sin_table[(uint8_t)(-camera.yaw)];
    int cy=sin_table[(uint8_t)(64-camera.yaw)];
    int xx=mul8(dx,cy)+mul8(dz,sy);
    int zz=mul8(dz,cy)-mul8(dx,sy);
    int sp=sin_table[(uint8_t)(-camera.pitch)];
    int cp=sin_table[(uint8_t)(64-camera.pitch)];
    *x=xx;*y=mul8(dy,cp)-mul8(zz,sp);*z=mul8(dy,sp)+mul8(zz,cp);
}
int main(void){
    SG3DTransform player={0};player.x=1234;player.y=256;player.z=2345;
    const int32_t height=384;
    for(int yaw=0;yaw<256;yaw+=16){
      for(int pitch=-48;pitch<=48;pitch+=12){
        SG3DCamera cam={0};
        sg3d_orbit_place(&cam,&player,(uint8_t)yaw,(int8_t)pitch,1792,height);
        int32_t x=player.x,y=player.y+height,z=player.z;
        view(cam,&x,&y,&z);
        if(x<-20||x>20||y<-20||y>20||z<512){
            fprintf(stderr,"bad yaw=%d pitch=%d view=%ld,%ld,%ld\\n",yaw,pitch,(long)x,(long)y,(long)z);
            return 1;
        }
        assert(cam.pitch==(uint8_t)(-pitch));
      }
    }
    puts("Camera aim: 16 yaws x 9 elevations passed");
    return 0;
}
