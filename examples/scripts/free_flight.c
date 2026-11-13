#include "sg3d_script.h"
/* Free-flight controller: vertical movement, pitch and yaw; no genre modes. */
void free_flight_Start(SG3DScriptContext *ctx,unsigned self){(void)ctx;(void)self;}
void free_flight_Update(SG3DScriptContext *ctx,unsigned self){
    if(sg3d_key_pressed(ctx,SG3D_KEY_SELECT))sg3d_load_scene(ctx,0);
    int32_t speed=sg3d_get_property(ctx,self,"speed");
    int32_t vertical=0;
    if(sg3d_key_held(ctx,SG3D_KEY_L))sg3d_rotate_object(ctx,self,-2,0);
    if(sg3d_key_held(ctx,SG3D_KEY_R))sg3d_rotate_object(ctx,self,2,0);
    if(sg3d_key_held(ctx,SG3D_KEY_UP))sg3d_rotate_object(ctx,self,0,-1);
    if(sg3d_key_held(ctx,SG3D_KEY_DOWN))sg3d_rotate_object(ctx,self,0,1);
    if(sg3d_key_held(ctx,SG3D_KEY_A))vertical=speed;
    if(sg3d_key_held(ctx,SG3D_KEY_B))vertical=-speed;
    sg3d_move_local(ctx,self,0,speed);
    sg3d_move_object(ctx,self,0,vertical,0);
    SG3DTransform *ship=sg3d_object(ctx,self);
    if(ship){ctx->camera->x=ship->x;ctx->camera->y=ship->y+SG3D_UNIT(1);ctx->camera->z=ship->z-SG3D_UNIT(7);ctx->camera->yaw=ship->yaw;}
}
void free_flight_Collision(SG3DScriptContext *ctx,unsigned self,unsigned other){(void)ctx;(void)self;(void)other;}
