#include "sg3d_controls.h"
#include "sin_table.h"
#define KEY_R 256u
#define KEY_L 512u
#define KEY_SEL 4u
#define KEY_UP 64u
#define KEY_DOWN 128u
#define KEY_RIGHT 16u
#define KEY_LEFT 32u
static inline int32_t fxmul(int32_t a,int32_t b){return (a*b)>>8;}
void sg3d_orbit_input(uint16_t keys,uint8_t *yaw,int8_t *pitch,uint8_t turn_speed){
    if((keys&KEY_L) && !(keys&KEY_R))*yaw-=turn_speed;
    if((keys&KEY_R) && !(keys&KEY_L))*yaw+=turn_speed;
    if((keys&(KEY_SEL|KEY_UP))==(KEY_SEL|KEY_UP) && *pitch<52)(*pitch)++;
    if((keys&(KEY_SEL|KEY_DOWN))==(KEY_SEL|KEY_DOWN) && *pitch>-52)(*pitch)--;
}
void sg3d_orbit_place(SG3DCamera *cam,const SG3DTransform *target,
                      uint8_t yaw,int8_t pitch,int32_t radius,int32_t height){
    int32_t sy=sin_table[yaw],cy=sin_table[(uint8_t)(yaw+64)];
    int32_t sp=sin_table[(uint8_t)pitch],cp=sin_table[(uint8_t)(pitch+64)];
    int32_t flat=fxmul(radius,cp);
    cam->x=target->x-fxmul(flat,sy);
    cam->z=target->z-fxmul(flat,cy);
    cam->y=target->y+height-fxmul(radius,sp);
    /* The orbit configuration uses conventional elevation: positive = camera
       below the target / looking upward.  The SG3D view transform uses the
       inverse pitch convention (positive = looking downward).  The position
       above was already correct; only the view pitch needs inversion.
       Without this, negative orbit pitch raises the camera AND looks up,
       pushing the player below the bottom of the screen. */
    cam->yaw=yaw;cam->pitch=(uint8_t)(-pitch);
}
void sg3d_orbit_camera(SG3DCamera *cam,const SG3DTransform *target,
                       uint16_t keys,uint8_t *yaw,int8_t *pitch,
                       int32_t radius,int32_t height,uint8_t turn_speed){
    sg3d_orbit_input(keys,yaw,pitch,turn_speed);
    sg3d_orbit_place(cam,target,*yaw,*pitch,radius,height);
}
void sg3d_move_relative(SG3DPhysicsBody *bodies,unsigned count,unsigned obj,
                        uint8_t yaw,int32_t strafe,int32_t forward){
    int sy=sin_table[yaw],cy=sin_table[(uint8_t)(yaw+64)];
    int32_t dx=fxmul(strafe,cy)+fxmul(forward,sy);
    int32_t dz=fxmul(forward,cy)-fxmul(strafe,sy);
    sg3d_physics_move(bodies,count,obj,dx,0,dz);
}
void sg3d_drive_vehicle(SG3DPhysicsBody *bodies,unsigned count,unsigned obj,
                        SG3DVehicle *state,uint16_t keys,int32_t accel,
                        int32_t maxspeed,int32_t drag,uint8_t turn){
    if(obj>=count||!state)return;
    if(accel<0)accel=0;
    if(drag<0)drag=0;
    if(maxspeed<0)maxspeed=0;
    if(keys&KEY_UP)state->speed+=accel;
    else if(keys&KEY_DOWN)state->speed-=accel;
    else if(state->speed>0){state->speed-=drag;if(state->speed<0)state->speed=0;}
    else if(state->speed<0){state->speed+=drag;if(state->speed>0)state->speed=0;}
    if(state->speed>maxspeed)state->speed=maxspeed;
    if(state->speed<-(maxspeed>>1))state->speed=-(maxspeed>>1);
    if(state->speed){
        uint8_t steering=turn;
        if(state->speed<0)steering=(uint8_t)(-steering);
        if(keys&KEY_LEFT)bodies[obj].transform->yaw-=steering;
        if(keys&KEY_RIGHT)bodies[obj].transform->yaw+=steering;
    }
    sg3d_move_relative(bodies,count,obj,bodies[obj].transform->yaw,0,state->speed);
}
