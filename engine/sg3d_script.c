#include "sg3d_script.h"
#include "sg3d_controls.h"
static int sg3d_str_equal(const char *a,const char *b){
    if(!a||!b)return 0;
    while(*a&&*b&&*a==*b){++a;++b;}
    return *a==*b;
}
static SG3DScriptActor *actor(SG3DScriptContext *ctx,unsigned id){
    return (ctx&&id<ctx->actor_count)?&ctx->actors[id]:0;
}
int sg3d_key_held(const SG3DScriptContext *ctx,uint16_t key){return ctx&&((ctx->held&key)!=0);}
int sg3d_key_pressed(const SG3DScriptContext *ctx,uint16_t key){return ctx&&((ctx->pressed&key)!=0);}
SG3DTransform *sg3d_object(SG3DScriptContext *ctx,unsigned id){SG3DScriptActor *a=actor(ctx,id);return a?a->transform:0;}
SG3DPhysicsBody *sg3d_body(SG3DScriptContext *ctx,unsigned id){SG3DScriptActor *a=actor(ctx,id);return a?a->body:0;}
int32_t sg3d_get_property(SG3DScriptContext *ctx,unsigned id,const char *name){
    SG3DScriptActor *a=actor(ctx,id);if(!a)return 0;
    for(unsigned i=0;i<a->property_count;i++)if(sg3d_str_equal(a->properties[i].name,name))return a->properties[i].value;
    return 0;
}
int sg3d_set_property(SG3DScriptContext *ctx,unsigned id,const char *name,int32_t value){
    SG3DScriptActor *a=actor(ctx,id);if(!a)return 0;
    for(unsigned i=0;i<a->property_count;i++)if(sg3d_str_equal(a->properties[i].name,name)){
        a->properties[i].value=value;return 1;
    }
    return 0;
}
void sg3d_move_object(SG3DScriptContext *ctx,unsigned id,int32_t dx,int32_t dy,int32_t dz){
    SG3DScriptActor *a=actor(ctx,id);if(!a||!a->body)return;
    /* Body array is not contiguous inside actors; context supplies the scene array. */
    if(ctx->actor_count && ctx->actors[0].body){
        SG3DPhysicsBody *first=ctx->actors[0].body;
        sg3d_physics_move(first,ctx->actor_count,id,dx,dy,dz);
    }
}
void sg3d_move_camera_space(SG3DScriptContext *ctx,unsigned id,int32_t side,int32_t forward){
    SG3DScriptActor *a=actor(ctx,id);if(!a||!ctx->camera)return;
    sg3d_move_relative(ctx->actors[0].body,ctx->actor_count,id,ctx->camera->yaw,side,forward);
}
void sg3d_move_local(SG3DScriptContext *ctx,unsigned id,int32_t side,int32_t forward){
    SG3DScriptActor *a=actor(ctx,id);if(!a||!a->transform)return;
    sg3d_move_relative(ctx->actors[0].body,ctx->actor_count,id,a->transform->yaw,side,forward);
}
void sg3d_rotate_object(SG3DScriptContext *ctx,unsigned id,int yaw_delta,int pitch_delta){
    SG3DTransform *t=sg3d_object(ctx,id);if(!t)return;
    t->yaw=(uint8_t)(t->yaw+yaw_delta);t->pitch=(uint8_t)(t->pitch+pitch_delta);
}
void sg3d_set_velocity(SG3DScriptContext *ctx,unsigned id,int32_t vx,int32_t vy,int32_t vz){
    SG3DPhysicsBody *b=sg3d_body(ctx,id);if(b){b->vx=vx;b->vy=vy;b->vz=vz;}
}
void sg3d_jump_object(SG3DScriptContext *ctx,unsigned id,int32_t impulse){
    if(ctx&&id<ctx->actor_count)sg3d_physics_jump(ctx->actors[0].body,ctx->actor_count,id,impulse);
}
int sg3d_is_grounded(SG3DScriptContext *ctx,unsigned id){
    SG3DPhysicsBody *b=sg3d_body(ctx,id);return b?b->grounded:0;
}
int sg3d_is_touching(SG3DScriptContext *ctx,unsigned a,unsigned b){
    if(!ctx||a>=ctx->actor_count||b>=ctx->actor_count)return 0;
    return sg3d_physics_touching(ctx->actors[0].body,ctx->actor_count,a,b);
}
void sg3d_load_scene(SG3DScriptContext *ctx,unsigned scene_id){
    if(ctx&&ctx->requested_scene)*ctx->requested_scene=(int)scene_id;
}
