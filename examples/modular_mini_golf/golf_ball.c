/* MODULAR MINI GOLF – authored entirely as a project C script, not a special
   engine controller. Asset geometry and materials come from the supplied
   Blockbench tile packs. 8.8 fixed-point coordinates: 256 = one tile.

   Object IDs in MiniGolf_Modular.sg3d.json:
   0 ball, 1 arrow, 2 cup, 3..11 tiles.
   Editable example: move/rotate pieces in the editor; collider follows them.
   To add/remove tiles, extend TILE_COUNT and the scene's ordered tile list.
*/
#include "sg3d_script.h"
#include "sg3d_hud.h"
#include "sin_table.h"

#define S 256
#define BALL_RADIUS 27
#define MAX_CHARGE 85
#define FRICTION 246
#define BOUNCE 158
#define STOP 2
#define TILE_FIRST 3u
#define TILE_COUNT 9u

enum { STRAIGHT=0, END_CAP=1, TURN_LEFT=2, TURN_RIGHT=3, RAMP=4 };
/* Every course tile is a normal editable scene object. Its position, rotation,
   and custom numeric properties drive collisions and incline height.
   This means moving/rotating a tile in the editor also moves its playing area. */
static uint8_t tile_kind[TILE_COUNT];
static int32_t tile_rise[TILE_COUNT];
static int32_t vx,vz;
static int charging,charge,strokes,won,overview;
static uint8_t aim;
static int32_t iabs(int32_t v){return v<0?-v:v;}
static int32_t sine(uint8_t a){return sin_table[a];}
static int surface(SG3DScriptContext *ctx,int32_t x,int32_t z,int32_t *surface_y,int *slope){
    int match=-1;
    int32_t near=0x7fffffff,height=0;
    for(unsigned i=0;i<TILE_COUNT;++i){
        SG3DTransform *t=sg3d_object(ctx,TILE_FIRST+i);
        if(!t)continue;
        int32_t dx=x-t->x,dz=z-t->z;
        int32_t c=sine((uint8_t)(t->yaw+64));
        int32_t sn=sine(t->yaw);
        /* Inverse of SG3D's local-to-world yaw rotation. */
        int32_t lx=(c*dx-sn*dz)>>8;
        int32_t lz=(sn*dx+c*dz)>>8;
        int32_t minx=-S/2-9,maxx=S/2+9,minz=-S/2-9,maxz=S/2+9;
        unsigned kind=tile_kind[i];
        if(kind==STRAIGHT||kind==RAMP){minx=-70;maxx=70;}
        else if(kind==END_CAP){minx=-70;maxx=70;minz=-70;}
        else if(kind==TURN_LEFT){minx=-70;maxz=70;}
        else if(kind==TURN_RIGHT){maxx=70;maxz=70;}
        if(lx<minx||lx>maxx||lz<minz||lz>maxz)continue;
        int32_t delta=iabs(lx)+iabs(lz);
        if(delta<near){
            near=delta;match=(int)i;
            height=t->y+S/8;
            if(tile_rise[i])height+=(tile_rise[i]*(lz+S/2))/S;
        }
    }
    if(match<0)return 0;
    *surface_y=height;
    if(slope)*slope=(int)tile_rise[match];
    return 1;
}
static void reset_game(SG3DScriptContext *ctx,unsigned self,int fresh){
    SG3DTransform *b=sg3d_object(ctx,self);
    SG3DTransform *tee=sg3d_object(ctx,TILE_FIRST);
    if(b&&tee){b->x=tee->x;b->z=tee->z;b->y=tee->y+S/8+BALL_RADIUS;}
    vx=vz=0;charging=0;charge=0;won=0;aim=0;
    if(fresh)strokes=0;
}
void golf_ball_Start(SG3DScriptContext *ctx,unsigned self){
    for(unsigned i=0;i<TILE_COUNT;i++){
        tile_kind[i]=(uint8_t)(sg3d_get_property(ctx,TILE_FIRST+i,"tile_kind")/S);
        tile_rise[i]=sg3d_get_property(ctx,TILE_FIRST+i,"rise");
    }
    reset_game(ctx,self,1);overview=0;
    sg3d_hud_set_visible(4,0);
    sg3d_hud_set_value(1,0);
    sg3d_hud_set_value(2,0);
}
void golf_ball_Update(SG3DScriptContext *ctx,unsigned self){
    SG3DTransform *ball=sg3d_object(ctx,self);
    SG3DTransform *arrow=sg3d_object(ctx,1u);
    if(!ball||!arrow)return;
    if(sg3d_key_pressed(ctx,SG3D_KEY_START))reset_game(ctx,self,1);
    if(sg3d_key_pressed(ctx,SG3D_KEY_B)){
        if(strokes>0&&!won)strokes++;
        reset_game(ctx,self,0);
    }
    if(sg3d_key_pressed(ctx,SG3D_KEY_R))overview=!overview;
    if(won){
        arrow->y=-4096;
        if(sg3d_key_pressed(ctx,SG3D_KEY_A))reset_game(ctx,self,1);
    }else if(vx||vz){
        int32_t floor_y=0;
        int slope=0;
        if(surface(ctx,ball->x+vx,ball->z,&floor_y,&slope))ball->x+=vx;
        else vx=-(vx*BOUNCE)/S;
        if(surface(ctx,ball->x,ball->z+vz,&floor_y,&slope))ball->z+=vz;
        else vz=-(vz*BOUNCE)/S;
        if(!surface(ctx,ball->x,ball->z,&floor_y,&slope))floor_y=S/8;
        ball->y=floor_y+BALL_RADIUS;
        /* A bit of slope resistance: ramps are not just decorations. */
        if(slope>0 && vz>0){vz-=slope/45;if(vz<0)vz=0;}
        if(slope>0 && vz<0){vz-=slope/60;}
        vx=(vx*FRICTION)/S;
        vz=(vz*FRICTION)/S;
        if(iabs(vx)<STOP)vx=0;
        if(iabs(vz)<STOP)vz=0;
        SG3DTransform *cup=sg3d_object(ctx,2u);
        int32_t dx=cup?ball->x-cup->x:9999;
        int32_t dz=cup?ball->z-cup->z:9999;
        if(dx*dx+dz*dz < 31*31 && iabs(vx)+iabs(vz)<65){
            won=1;vx=vz=0;ball->y=-4096;
        }
    }else{
        if(sg3d_key_held(ctx,SG3D_KEY_LEFT))aim-=2;
        if(sg3d_key_held(ctx,SG3D_KEY_RIGHT))aim+=2;
        if(sg3d_key_held(ctx,SG3D_KEY_A)){
            charging=1;
            if(charge<MAX_CHARGE)charge+=3;
            if(charge>MAX_CHARGE)charge=MAX_CHARGE;
        }else if(charging){
            int32_t p=charge<19?19:charge;
            vx=(p*sine(aim))>>8;
            vz=(p*sine((uint8_t)(aim+64)))>>8;
            strokes++;charging=charge=0;
        }
    }
    if(!won && !vx&&!vz){
        arrow->x=ball->x;
        arrow->z=ball->z;
        arrow->y=ball->y-BALL_RADIUS+3;
        arrow->yaw=aim;
    }else arrow->y=-4096;
    /* Camera follows the golf ball; R toggles an elevated course view. */
    if(ctx->camera){
        int32_t tx=ball->x+S/2;
        int32_t tz=ball->z-(overview?6*S:3*S);
        int32_t ty=(won?S:ball->y)+(overview?7*S:3*S);
        ctx->camera->x+=(tx-ctx->camera->x)/4;
        ctx->camera->y+=(ty-ctx->camera->y)/4;
        ctx->camera->z+=(tz-ctx->camera->z)/4;
        ctx->camera->yaw=0;
        ctx->camera->pitch=SG3D_ANGLE(overview?42:28);
    }
    sg3d_hud_set_value(1,strokes);
    sg3d_hud_set_value(2,charge);
    sg3d_hud_set_visible(4,won);
}
void golf_ball_Collision(SG3DScriptContext *ctx,unsigned self,unsigned other){
    (void)ctx;(void)self;(void)other;
}
