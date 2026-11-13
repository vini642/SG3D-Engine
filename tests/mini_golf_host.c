/* Host-side test of the user-authored Mini Golf controller with generic SG3D stubs.
   This is NOT a GBA emulator, but exercises aim, charging, motion and reset. */
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include "sg3d_script.h"
#include "sg3d_hud.h"
extern void golf_ball_Start(SG3DScriptContext*,unsigned);
extern void golf_ball_Update(SG3DScriptContext*,unsigned);
extern void golf_ball_Collision(SG3DScriptContext*,unsigned,unsigned);
static SG3DTransform transforms[9];
static SG3DScriptActor actors[9];
static SG3DCamera cam;
static int32_t hudval[5];
static unsigned visible[5];
SG3DTransform *sg3d_object(SG3DScriptContext *ctx,unsigned id){(void)ctx;return id<9?&transforms[id]:0;}
void sg3d_move_object(SG3DScriptContext *ctx,unsigned id,int32_t dx,int32_t dy,int32_t dz){
 (void)ctx;SG3DTransform *t=&transforms[id];t->x+=dx;t->y+=dy;t->z+=dz;
 if(t->x < -970)t->x=-970;if(t->x>970)t->x=970;
 if(t->z<2070)t->z=2070;if(t->z>4600)t->z=4600;
}
int sg3d_key_pressed(const SG3DScriptContext *ctx,uint16_t key){return (ctx->pressed&key)!=0;}
int sg3d_key_held(const SG3DScriptContext *ctx,uint16_t key){return (ctx->held&key)!=0;}
void sg3d_hud_set_value(unsigned i,int32_t value){if(i<5)hudval[i]=value;}
void sg3d_hud_set_visible(unsigned i,unsigned value){if(i<5)visible[i]=value;}
int main(void){
 SG3DScriptContext ctx={actors,9,&cam,0,0,0};
 transforms[3].x=576;transforms[3].z=4416;
 golf_ball_Start(&ctx,0);
 assert(transforms[0].x==-640 && transforms[0].z==2278 && hudval[1]==0);
 /* Hold and release A: charge 80 fixed units and hit down +Z. */
 ctx.held=SG3D_KEY_A;
 for(int i=0;i<20;i++)golf_ball_Update(&ctx,0);
 assert(hudval[2]==80);
 ctx.held=0;
 golf_ball_Update(&ctx,0);
 assert(hudval[1]==1);
 int32_t z=transforms[0].z;
 for(int i=0;i<7;i++)golf_ball_Update(&ctx,0);
 assert(transforms[0].z>z+100); /* not the 16x-too-small sine bug */
 /* B reset and penalize stroke after first shot. */
 ctx.pressed=SG3D_KEY_B;golf_ball_Update(&ctx,0);ctx.pressed=0;
 assert(transforms[0].x==-640 && transforms[0].z==2278 && hudval[1]==2);
 /* Aim right and verify the ball has horizontal motion after the shot. */
 ctx.held=SG3D_KEY_RIGHT;
 for(int i=0;i<12;i++)golf_ball_Update(&ctx,0);
 ctx.held=SG3D_KEY_A;
 for(int i=0;i<15;i++)golf_ball_Update(&ctx,0);
 ctx.held=0;golf_ball_Update(&ctx,0);
 assert(hudval[1]==3);
 int32_t x=transforms[0].x;
 for(int i=0;i<8;i++)golf_ball_Update(&ctx,0);
 assert(transforms[0].x>x+30);
 /* START restarts the hole. */
 ctx.pressed=SG3D_KEY_START;golf_ball_Update(&ctx,0);ctx.pressed=0;
 assert(hudval[1]==0 && transforms[0].x==-640 && transforms[0].z==2278);
 puts("Mini Golf controller host test: passed");return 0;
}
