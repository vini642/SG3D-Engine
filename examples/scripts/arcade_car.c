#include "sg3d_script.h"
/* Hand-written steering + speed/drag from custom properties; not a preset. */
void arcade_car_Start(SG3DScriptContext *ctx,unsigned self){sg3d_set_property(ctx,self,"speed",0);}
void arcade_car_Update(SG3DScriptContext *ctx,unsigned self){
    if(sg3d_key_pressed(ctx,SG3D_KEY_SELECT))sg3d_load_scene(ctx,2);
    int32_t speed=sg3d_get_property(ctx,self,"speed");
    int32_t accel=sg3d_get_property(ctx,self,"accel");
    int32_t top=sg3d_get_property(ctx,self,"top");
    if(sg3d_key_held(ctx,SG3D_KEY_A))speed+=accel;
    if(sg3d_key_held(ctx,SG3D_KEY_B))speed-=accel;
    if(!sg3d_key_held(ctx,SG3D_KEY_A)&&!sg3d_key_held(ctx,SG3D_KEY_B))speed=(speed*15)>>4;
    if(speed>top)speed=top;
    if(speed< -top/2)speed= -top/2;
    sg3d_set_property(ctx,self,"speed",speed);
    if(sg3d_key_held(ctx,SG3D_KEY_LEFT))sg3d_rotate_object(ctx,self,-2,0);
    if(sg3d_key_held(ctx,SG3D_KEY_RIGHT))sg3d_rotate_object(ctx,self,2,0);
    sg3d_move_local(ctx,self,0,speed);
    SG3DTransform *car=sg3d_object(ctx,self);
    if(car){ctx->camera->x=car->x;ctx->camera->y=car->y+SG3D_UNIT(3);ctx->camera->z=car->z-SG3D_UNIT(8);ctx->camera->yaw=car->yaw;}
}
void arcade_car_Collision(SG3DScriptContext *ctx,unsigned self,unsigned other){(void)other;sg3d_set_property(ctx,self,"speed",0);}
