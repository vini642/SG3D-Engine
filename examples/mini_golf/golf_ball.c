#include "sg3d_script.h"
#include "sg3d_hud.h"
#include "sin_table.h"
/* SG3D Mini Golf starter: editable user script, not part of the engine.
   Units are 24.8 fixed point (256 = 1 world unit).
   Scene object 0 = ball, 1 = arrow, 3 = hole.
   Edit ball friction, shot strength, or course layout freely! */
#define ARROW_OBJECT 1u
#define HOLE_OBJECT 3u
#define START_X (-640)  /* -2.5 units */
#define START_Z (2278)  /*  8.9 units */
#define BALL_Y 70
#define AIM_Y 6
#define MAX_CHARGE 184
#define STOP_SPEED 3
#define ROLL_FRICTION 244
#define WALL_BOUNCE 175
static int32_t velocity_x, velocity_z;
static int charge, strokes, won, charging;
static uint8_t shot_yaw;
static int32_t absi(int32_t x){ return x<0?-x:x; }
static int32_t sine(uint8_t a){ return sin_table[a]; }
static void reset_ball(SG3DScriptContext *ctx, unsigned self, int clear_score){
    SG3DTransform *t=sg3d_object(ctx,self);
    if(t){t->x=START_X;t->y=BALL_Y;t->z=START_Z;}
    velocity_x=velocity_z=0;charge=charging=won=0;shot_yaw=0;
    if(clear_score)strokes=0;
}
void golf_ball_Start(SG3DScriptContext *ctx,unsigned self){
    reset_ball(ctx,self,1);
    sg3d_hud_set_visible(4,0);
    sg3d_hud_set_value(1,strokes);
    sg3d_hud_set_value(2,charge);
}
void golf_ball_Update(SG3DScriptContext *ctx,unsigned self){
    SG3DTransform *ball=sg3d_object(ctx,self);
    SG3DTransform *arrow=sg3d_object(ctx,ARROW_OBJECT);
    SG3DTransform *hole=sg3d_object(ctx,HOLE_OBJECT);
    if(!ball || !arrow || !hole)return;
    if(sg3d_key_pressed(ctx,SG3D_KEY_START))reset_ball(ctx,self,1);
    if(sg3d_key_pressed(ctx,SG3D_KEY_B)){
        /* +1 penalty stroke when resetting, unless nothing has happened yet. */
        if(strokes>0 && !won)strokes++;
        reset_ball(ctx,self,0);
    }
    if(won){
        arrow->y=-4096;
        if(sg3d_key_pressed(ctx,SG3D_KEY_A))reset_ball(ctx,self,1);
    }else if(absi(velocity_x)+absi(velocity_z)>0){
        int32_t old_x=ball->x,old_z=ball->z;
        /* Generic collision-aware SG3D movement against all solid objects. */
        sg3d_move_object(ctx,self,velocity_x,0,velocity_z);
        if(ball->x!=old_x+velocity_x)velocity_x=-(velocity_x*WALL_BOUNCE)/256;
        if(ball->z!=old_z+velocity_z)velocity_z=-(velocity_z*WALL_BOUNCE)/256;
        velocity_x=(velocity_x*ROLL_FRICTION)/256;
        velocity_z=(velocity_z*ROLL_FRICTION)/256;
        if(absi(velocity_x)<STOP_SPEED)velocity_x=0;
        if(absi(velocity_z)<STOP_SPEED)velocity_z=0;
        /* Ball must slow down near the hole before it drops in. */
        int32_t dx=ball->x-hole->x,dz=ball->z-hole->z;
        if(dx*dx+dz*dz < 112*112 && absi(velocity_x)+absi(velocity_z)<106){
            won=1;velocity_x=velocity_z=0;ball->y=-4096;
        }
    }else{
        /* Players can aim and charge only while the ball is at rest. */
        if(sg3d_key_held(ctx,SG3D_KEY_LEFT))shot_yaw-=2;
        if(sg3d_key_held(ctx,SG3D_KEY_RIGHT))shot_yaw+=2;
        if(sg3d_key_held(ctx,SG3D_KEY_A)){
            charging=1;
            if(charge<MAX_CHARGE)charge+=4;
            if(charge>MAX_CHARGE)charge=MAX_CHARGE;
        }else if(charging){
            /* Release A = strike, direction uses the engine sine table. */
            int32_t power=charge;
            if(power<25)power=25;
            velocity_x=(power*sine(shot_yaw))>>8;
            velocity_z=(power*sine((uint8_t)(shot_yaw+64)))>>8;
            strokes++;charging=0;charge=0;
        }
    }
    if(!won && velocity_x==0 && velocity_z==0){
        arrow->x=ball->x;arrow->y=AIM_Y;arrow->z=ball->z;
        arrow->yaw=shot_yaw;
    }else arrow->y=-4096;
    sg3d_hud_set_value(1,strokes);
    sg3d_hud_set_value(2,charge);
    sg3d_hud_set_visible(4,won);
}
void golf_ball_Collision(SG3DScriptContext *ctx,unsigned self,unsigned other){
    (void)ctx;(void)self;(void)other;
}
