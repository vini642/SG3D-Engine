#include "sg3d_script.h"
/* Generic walkable character: 100% user-authored, no MovePlayer preset. */
void explore_Start(SG3DScriptContext *ctx,unsigned self){(void)ctx;(void)self;}
void explore_Update(SG3DScriptContext *ctx,unsigned self){
    if(sg3d_key_pressed(ctx,SG3D_KEY_SELECT))sg3d_load_scene(ctx,1);
    int32_t speed=sg3d_get_property(ctx,self,"speed");
    int32_t dx=0,dz=0;
    if(sg3d_key_held(ctx,SG3D_KEY_LEFT))dx-=speed;
    if(sg3d_key_held(ctx,SG3D_KEY_RIGHT))dx+=speed;
    if(sg3d_key_held(ctx,SG3D_KEY_UP))dz+=speed;
    if(sg3d_key_held(ctx,SG3D_KEY_DOWN))dz-=speed;
    sg3d_move_camera_space(ctx,self,dx,dz);
    if(sg3d_key_pressed(ctx,SG3D_KEY_A))sg3d_jump_object(ctx,self,SG3D_UNIT(1)/3);
    SG3DTransform *body=sg3d_object(ctx,self);
    if(body){ctx->camera->x=body->x;ctx->camera->y=body->y+SG3D_UNIT(2);ctx->camera->z=body->z-SG3D_UNIT(6);}
}
void explore_Collision(SG3DScriptContext *ctx,unsigned self,unsigned other){(void)ctx;(void)self;(void)other;}
