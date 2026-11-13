#include "sg3d_physics.h"

static int overlap(int32_t a,int32_t ah,int32_t b,int32_t bh){
    return a-ah < b+bh && b-bh < a+ah;
}
static int near(int32_t a,int32_t b){
    return a >= b-2 && a <= b+2;
}
static int32_t at(const SG3DTransform *t,int axis){
    return axis==0?t->x:axis==1?t->y:t->z;
}
static int32_t ext(const SG3DPhysicsBody *b,int axis){
    return axis==0?b->hx:axis==1?b->hy:b->hz;
}
static void setat(SG3DTransform *t,int axis,int32_t value){
    if(axis==0)t->x=value;else if(axis==1)t->y=value;else t->z=value;
}
static int aligned(const SG3DPhysicsBody *a,const SG3DPhysicsBody *b,int axis){
    for(int k=0;k<3;k++){
        if(k==axis)continue;
        if(!overlap(at(a->transform,k),ext(a,k),at(b->transform,k),ext(b,k)))return 0;
    }
    return 1;
}
static void axis_move(SG3DPhysicsBody *b,unsigned n,unsigned i,int axis,int32_t delta){
    if(!delta || i>=n || !b[i].transform)return;
    SG3DPhysicsBody *a=&b[i];
    int32_t pos=at(a->transform,axis),end=pos+delta;
    int hit=0;
    for(unsigned j=0;j<n;j++){
        const SG3DPhysicsBody *other=&b[j];
        if(j==i || !other->solid || !other->transform || !aligned(a,other,axis))continue;
        int32_t v=at(other->transform,axis),r=ext(a,axis)+ext(other,axis);
        if(delta>0 && pos+r<=v && end+r>v){end=v-r;hit=1;}
        if(delta<0 && pos-r>=v && end-r<v){end=v+r;hit=1;}
    }
    setat(a->transform,axis,end);
    if(hit && axis==1){a->vy=0;if(delta<0)a->grounded=1;}
    if(hit && axis==0)a->vx=0;
    if(hit && axis==2)a->vz=0;
}
void sg3d_physics_move(SG3DPhysicsBody *b,unsigned n,unsigned i,
                       int32_t dx,int32_t dy,int32_t dz){
    if(i>=n || !b[i].transform)return;
    axis_move(b,n,i,0,dx);
    axis_move(b,n,i,2,dz);
    axis_move(b,n,i,1,dy);
}
static int ground_contact(SG3DPhysicsBody *b,unsigned n,unsigned i){
    SG3DPhysicsBody *a=&b[i];
    if(!a->transform)return 0;
    for(unsigned j=0;j<n;j++){
        SG3DPhysicsBody *c=&b[j];
        if(i==j || !c->solid || !c->transform)continue;
        if(!overlap(a->transform->x,a->hx,c->transform->x,c->hx) ||
           !overlap(a->transform->z,a->hz,c->transform->z,c->hz))continue;
        if(near(a->transform->y-a->hy,c->transform->y+c->hy))return 1;
    }
    return 0;
}
/* Correct spawn/interpenetration before sweeping axes. This handles scenes
   where a player starts intersecting a platform. For large/angled terrain
   this is still only an axis-aligned box approximation. */
static void depenetrate(SG3DPhysicsBody *b,unsigned n,unsigned i){
    SG3DPhysicsBody *a=&b[i];
    for(int iteration=0;iteration<4;iteration++){
        int found=0,best_axis=1;int32_t best_push=0,best_abs=0x7fffffff;
        for(unsigned j=0;j<n;j++){
            const SG3DPhysicsBody *c=&b[j];
            if(j==i||!c->solid||!c->transform)continue;
            int collides=1;
            for(int axis=0;axis<3;axis++){
                if(!overlap(at(a->transform,axis),ext(a,axis),at(c->transform,axis),ext(c,axis))){collides=0;break;}
            }
            if(!collides)continue;
            for(int axis=0;axis<3;axis++){
                int32_t pos=at(a->transform,axis),other=at(c->transform,axis);
                int32_t reach=ext(a,axis)+ext(c,axis);
                int32_t delta=pos-other;
                int32_t depth=reach-(delta<0?-delta:delta);
                if(depth<best_abs){
                    best_abs=depth;best_axis=axis;best_push=(delta>=0?depth:-depth);found=1;
                }
            }
        }
        if(!found)break;
        setat(a->transform,best_axis,at(a->transform,best_axis)+best_push);
        if(best_axis==1){a->vy=0;if(best_push>0)a->grounded=1;}
        else if(best_axis==0)a->vx=0;
        else a->vz=0;
    }
}
void sg3d_physics_step(SG3DPhysicsBody *b,unsigned n,int32_t gravity,int32_t terminal){
    for(unsigned i=0;i<n;i++){
        if(!b[i].dynamic || !b[i].transform)continue;
        depenetrate(b,n,i);
        b[i].grounded=(uint8_t)ground_contact(b,n,i);
        if(!b[i].grounded){
            b[i].vy+=gravity;
            if(b[i].vy<terminal)b[i].vy=terminal;
        }else if(b[i].vy<0)b[i].vy=0;
        sg3d_physics_move(b,n,i,b[i].vx,b[i].vy,b[i].vz);
        b[i].grounded=(uint8_t)ground_contact(b,n,i);
        if(b[i].grounded && b[i].vy<0)b[i].vy=0;
    }
}
int sg3d_physics_touching(const SG3DPhysicsBody *b,unsigned n,unsigned a,unsigned c){
    if(a>=n || c>=n || a==c || !b[a].transform || !b[c].transform)return 0;
    const SG3DPhysicsBody *u=&b[a],*v=&b[c];
    return (u->transform->x-u->hx<=v->transform->x+v->hx+2 &&
            v->transform->x-v->hx<=u->transform->x+u->hx+2 &&
            u->transform->y-u->hy<=v->transform->y+v->hy+2 &&
            v->transform->y-v->hy<=u->transform->y+u->hy+2 &&
            u->transform->z-u->hz<=v->transform->z+v->hz+2 &&
            v->transform->z-v->hz<=u->transform->z+u->hz+2);
}
void sg3d_physics_jump(SG3DPhysicsBody *b,unsigned n,unsigned i,int32_t impulse){
    if(i<n && b[i].dynamic && b[i].grounded){
        b[i].vy=impulse;
        b[i].grounded=0;
    }
}
