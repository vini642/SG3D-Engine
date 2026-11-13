#include "sg3d_physics.h"
#include <assert.h>
#include <stdio.h>
int main(void){
    SG3DTransform player={0,3*256,0,0,0,256};
    SG3DTransform floor={0,-256,0,0,0,256};
    SG3DTransform wall={3*256,0,0,0,0,256};
    SG3DPhysicsBody b[]={
       {&player,128,128,128,0,0,0,1,1,0},
       {&floor,10*256,128,10*256,0,0,0,0,1,0},
       {&wall,128,10*256,10*256,0,0,0,0,1,0},
    };
    for(int i=0;i<150;i++)sg3d_physics_step(b,3,-7,-179);
    assert(player.y==0 && b[0].grounded);
    sg3d_physics_jump(b,3,0,90);
    assert(b[0].vy==90 && !b[0].grounded);
    sg3d_physics_step(b,3,-7,-179);
    assert(player.y>0);
    for(int i=0;i<150;i++)sg3d_physics_step(b,3,-7,-179);
    assert(player.y==0 && b[0].grounded);
    sg3d_physics_move(b,3,0,20*256,0,0);
    assert(player.x==2*256);
    assert(sg3d_physics_touching(b,3,0,2));
    puts("Physics: fall, ground, jump, land, wall, contact PASS");
    return 0;
}
