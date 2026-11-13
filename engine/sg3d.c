#include "sg3d.h"
#include "sg3d_hud.h"
#include "sin_table.h"
#include <stddef.h>
#include <stdint.h>

#define REG16(a) (*(volatile uint16_t *)(a))
#define REG32(a) (*(volatile uint32_t *)(a))
#define VRAM ((volatile uint16_t *)0x06000000)
#define PAL ((volatile uint16_t *)0x05000000)
#define EWRAM __attribute__((section(".ewram_bss")))
#define NEAR_Z 256
#define FAR_Z 16384

/* Controlled A/B flags: set to 0 to compare against the v0.12.1 pipeline. */
#ifndef SG3D_PERF_FAST_CLIP
#define SG3D_PERF_FAST_CLIP 1
#endif
#ifndef SG3D_PERF_BUCKET_SORT
#define SG3D_PERF_BUCKET_SORT 1
#endif
#define SG3D_DEPTH_BUCKETS 128
/* These optimizations are independent, useful for isolating regressions. */
#ifndef SG3D_PERF_OBJECT_CULL
#define SG3D_PERF_OBJECT_CULL 1
#endif
#ifndef SG3D_PERF_FUSED_TRANSFORM
#define SG3D_PERF_FUSED_TRANSFORM 1
#endif
#ifndef SG3D_PERF_VERTEX_CACHE
#define SG3D_PERF_VERTEX_CACHE 1
#endif
#ifndef SG3D_PERF_SOLID_TEXTURE
#define SG3D_PERF_SOLID_TEXTURE 1
#endif
#ifndef SG3D_PERF_TINY_FLAT
#define SG3D_PERF_TINY_FLAT 1
#endif

extern void sg3d_internal_framebuffer(uint8_t *framebuffer);
extern void sg3d_internal_triangle(const uint32_t s[3],const uint32_t uv[3],
                                   uint8_t color,const SG3DTexture *tex,uint8_t mode);
/* 368640/z, clipped to 16 bits, matching the v0.5 projection */
static const uint16_t invz[2048] = {
#include "invz.inc"
};

typedef struct { int32_t x,y,z,u,v; } ClipPoint;
typedef struct {
    uint32_t screen[3], uv[3];
    const SG3DTexture *texture;
    int32_t depth;
    uint8_t color, mode;
} QueuedTri;
static QueuedTri queue[SG3D_MAX_TRIANGLES] EWRAM;
static ClipPoint transformed[SG3D_MAX_VERTICES] EWRAM;
#if SG3D_PERF_VERTEX_CACHE
static uint32_t screen_cache[SG3D_MAX_VERTICES] EWRAM;
static uint16_t screen_generation[SG3D_MAX_VERTICES] EWRAM;
static uint16_t mesh_generation;
#endif
#if SG3D_PERF_FAST_CLIP
static uint8_t clip_codes[SG3D_MAX_VERTICES] EWRAM;
#endif
#if SG3D_PERF_BUCKET_SORT
static uint16_t bin_head[SG3D_DEPTH_BUCKETS] EWRAM;
static uint16_t bin_next[SG3D_MAX_TRIANGLES] EWRAM;
#endif
static SG3DCamera camera;
static const uint8_t *skybox_pixels;
static SG3DStats stats;
extern void sg3d_effects_rgb332_init(void);
static unsigned count, page, objects_drawn;

static inline int32_t mul8(int32_t a,int32_t b){return (a*b)>>8;}
static inline void yaw_rotate(int32_t *x,int32_t *z,int sy,int cy){
    int32_t xx=*x,zz=*z;
    *x=mul8(xx,cy)+mul8(zz,sy);
    *z=mul8(zz,cy)-mul8(xx,sy);
}
static inline void pitch_rotate(int32_t *y,int32_t *z,int sp,int cp){
    int32_t yy=*y,zz=*z;
    *y=mul8(yy,cp)-mul8(zz,sp);
    *z=mul8(yy,sp)+mul8(zz,cp);
}
/* Fused model/view basis for each object. All math is fixed-point, no floats,
   division or trigonometry at per-vertex time. Q12 basis preserves precision.
   Composing rotations once replaces four rotation stages per vertex. */
#if SG3D_PERF_FUSED_TRANSFORM
static int32_t view_basis[3][3], view_origin[3];
static void prepare_view_transform(SG3DTransform t,int sy,int cy,int sp,int cp,
                                  int csy,int ccy,int csp,int ccp){
    int32_t ox=t.x-camera.x,oy=t.y-camera.y,oz=t.z-camera.z;
    yaw_rotate(&ox,&oz,csy,ccy);pitch_rotate(&oy,&oz,csp,ccp);
    view_origin[0]=ox;view_origin[1]=oy;view_origin[2]=oz;
    for(int k=0;k<3;k++){
        int32_t x=k==0?4096:0,y=k==1?4096:0,z=k==2?4096:0;
        yaw_rotate(&x,&z,sy,cy);pitch_rotate(&y,&z,sp,cp);
        yaw_rotate(&x,&z,csy,ccy);pitch_rotate(&y,&z,csp,ccp);
        view_basis[0][k]=x;view_basis[1][k]=y;view_basis[2][k]=z;
    }
}
static void fused_vertex(int32_t *x,int32_t *y,int32_t *z){
    int32_t vx=*x,vy=*y,vz=*z;
    *x=view_origin[0]+((vx*view_basis[0][0])>>12)+((vy*view_basis[0][1])>>12)+((vz*view_basis[0][2])>>12);
    *y=view_origin[1]+((vx*view_basis[1][0])>>12)+((vy*view_basis[1][1])>>12)+((vz*view_basis[1][2])>>12);
    *z=view_origin[2]+((vx*view_basis[2][0])>>12)+((vy*view_basis[2][1])>>12)+((vz*view_basis[2][2])>>12);
}
#endif
/* View-space origin, independent of object-space orientation. */
static void view_position(int32_t *x,int32_t *y,int32_t *z,int csy,int ccy,int csp,int ccp){
    *x-=camera.x;*y-=camera.y;*z-=camera.z;
    yaw_rotate(x,z,csy,ccy);pitch_rotate(y,z,csp,ccp);
}
/* Bounding sphere culling is deliberately conservative: near/far and 120x80
   screen planes, expanded by sphere radius and 1/8 unit for rounding. It
   must NEVER reject a mesh with any visible pixel. */
#if SG3D_PERF_OBJECT_CULL
static int sphere_is_offscreen(const SG3DMesh *mesh,SG3DTransform t,
                              int sy,int cy,int sp,int cp,int csy,int ccy,int csp,int ccp){
    if(!mesh->bound_radius||t.scale>8192)return 0; /* legacy or extreme-scale mesh */
    int32_t x=((int32_t)mesh->bound_x*t.scale)>>8;
    int32_t y=((int32_t)mesh->bound_y*t.scale)>>8;
    int32_t z=((int32_t)mesh->bound_z*t.scale)>>8;
    yaw_rotate(&x,&z,sy,cy);pitch_rotate(&y,&z,sp,cp);
    x+=t.x;y+=t.y;z+=t.z;
    view_position(&x,&y,&z,csy,ccy,csp,ccp);
    /* ceil(scale*radius/256), plus guard for Q8 rotation roundoff */
    int32_t radius=(((int32_t)mesh->bound_radius*t.scale)+255)>>8;
    radius+=32;
    if(z+radius<NEAR_Z || z-radius>FAR_Z)return 1;
    /* Focal length 90 at 120x80: horizontal +/-2z/3, vertical +/-4z/9. */
    if(3*(x-radius)>2*(z+radius)||3*(-x-radius)>2*(z+radius))return 1;
    if(9*(y-radius)>4*(z+radius)||9*(-y-radius)>4*(z+radius))return 1;
    return 0;
}
#endif
static uint32_t pack_pos(int x,int y){
    return (uint16_t)(int16_t)(x*16) | ((uint32_t)(uint16_t)(int16_t)(y*16)<<16);
}
static int project_recip(int32_t z){
    unsigned shift=0;
    if(z<NEAR_Z) z=NEAR_Z;
    while(z>2047){z>>=1;shift++;}
    return invz[z] >> shift;
}
/* A vertex is normally referenced by multiple triangles. Computing five
   frustum distances once per vertex avoids Sutherland-Hodgman on the common
   completely-inside triangles. The original clipper handles actual edges. */
#if SG3D_PERF_FAST_CLIP
static uint8_t vertex_clip_mask(const ClipPoint *p){
    uint8_t mask=0;
    if(p->z<NEAR_Z) mask|=1;
    if(p->z*4<p->x) mask|=2;
    if(p->z*4<-p->x) mask|=4;
    if(p->z*4<p->y) mask|=8;
    if(p->z*4<-p->y) mask|=16;
    return mask;
}
#endif
static int clip_dist(const ClipPoint *p,int plane){
    switch(plane){
        case 0: return p->z-NEAR_Z;
        case 1: return p->z*4-p->x;
        case 2: return p->z*4+p->x;
        case 3: return p->z*4-p->y;
        default:return p->z*4+p->y;
    }
}
/* Avoid libgcc (__aeabi_idiv) in this freestanding GBA build. Used only for
   the relatively rare near/frustum clipped edges. Returns 8-bit fraction. */
static uint32_t fraction256(uint32_t num,uint32_t den){
    uint32_t q=0;
    if(!den) return 0;
    if(num>=den)return 256;
    for(int i=0;i<8;i++){
        num <<= 1;
        q <<= 1;
        if(num>=den){num-=den;q|=1;}
    }
    return q;
}
static ClipPoint interpolate(ClipPoint a,ClipPoint b,uint32_t n,uint32_t d){
    uint32_t t=fraction256(n,d);
    ClipPoint p;
    p.x=a.x+(((b.x-a.x)*(int32_t)t)>>8);
    p.y=a.y+(((b.y-a.y)*(int32_t)t)>>8);
    p.z=a.z+(((b.z-a.z)*(int32_t)t)>>8);
    p.u=a.u+(((b.u-a.u)*(int32_t)t)>>8);
    p.v=a.v+(((b.v-a.v)*(int32_t)t)>>8);
    return p;
}
static void push_triangle(ClipPoint a,ClipPoint b,ClipPoint c,const SG3DMaterial *mat,uint8_t flags,
                          const uint32_t *cached,uint8_t solid_color,uint8_t tiny_color){
    ClipPoint p[3]={a,b,c};
    int sx[3],sy[3];
    uint32_t scr[3],uv[3];
    for(int k=0;k<3;k++){
        if(cached){
            scr[k]=cached[k];
            sx[k]=((int16_t)(uint16_t)scr[k])>>4;
            sy[k]=((int16_t)(scr[k]>>16))>>4;
        } else {
            int inv=project_recip(p[k].z);
            sx[k]=60+((p[k].x*inv)>>12);
            sy[k]=40-((p[k].y*inv)>>12);
            /* Guard clipping bounds these to ±420 pixels before packing. */
            scr[k]=pack_pos(sx[k],sy[k]);
        }
        uv[k]=SG3D_UV(p[k].u,p[k].v);
    }
    int32_t area=(sy[0]-sy[2])*(sx[0]-sx[1])-(sx[0]-sx[2])*(sy[0]-sy[1]);
    if(!area || (area<0 && (flags&SG3D_CULL_BACK))){stats.rejected++;return;}
    int32_t minx=sx[0],maxx=sx[0],miny=sy[0],maxy=sy[0];
    for(int k=1;k<3;k++){
        if(sx[k]<minx)minx=sx[k];if(sx[k]>maxx)maxx=sx[k];
        if(sy[k]<miny)miny=sy[k];if(sy[k]>maxy)maxy=sy[k];
    }
    if(maxx<0 || minx>=SG3D_WIDTH || maxy<0 || miny>=SG3D_HEIGHT){stats.rejected++;return;}
    if(count==SG3D_MAX_TRIANGLES){stats.dropped++;return;}
    QueuedTri *e=&queue[count++];
    if(area<0){uint32_t t=scr[1];scr[1]=scr[2];scr[2]=t;t=uv[1];uv[1]=uv[2];uv[2]=t;}
    for(int k=0;k<3;k++){e->screen[k]=scr[k];e->uv[k]=uv[k];}
    e->depth=a.z+b.z+c.z;
    e->color=mat->color;
    e->mode=mat->mode;
    if(e->mode>SG3D_TINT) e->mode=SG3D_FLAT;
    if((e->mode==SG3D_TEXTURED || e->mode==SG3D_ALPHA ||
        e->mode==SG3D_ADDITIVE || e->mode==SG3D_DARKEN) && !mat->texture)
        e->mode=SG3D_FLAT;
    e->texture=mat->texture;
#if SG3D_PERF_SOLID_TEXTURE
    if((flags&SG3D_FACE_SOLID_TEX) && e->mode==SG3D_TEXTURED){
        e->mode=SG3D_FLAT;e->color=solid_color;stats.solid_triangles++;
    }
#else
    (void)solid_color;
#endif
#if SG3D_PERF_TINY_FLAT
    /* <= 8 pixels of projected area, and beyond eight world units.
       Character faces close to the camera keep their actual texels. */
    if((flags&SG3D_FACE_TINY_TEX) && e->mode==SG3D_TEXTURED &&
       (area<0?-area:area)<=16 && e->depth>3*2048){
        e->mode=SG3D_FLAT;e->color=tiny_color;stats.tiny_triangles++;
    }
#else
    (void)tiny_color;
#endif
}
static void clip_and_enqueue(const ClipPoint points[3],const SG3DMaterial *mat,uint8_t flags,uint8_t solid_color,uint8_t tiny_color){
    ClipPoint buf[2][10];
    for(int i=0;i<3;i++)buf[0][i]=points[i];
    int cur=0,n=3,clipped=0;
    for(int plane=0;plane<5 && n>=3;plane++){
        ClipPoint *in=buf[cur],*out=buf[cur^1];
        int newn=0;
        ClipPoint a=in[n-1];int da=clip_dist(&a,plane);
        for(int i=0;i<n;i++){
            ClipPoint b=in[i];int db=clip_dist(&b,plane);
            if((da<0)!=(db<0)){
                unsigned an=(unsigned)(da<0?-da:da);
                unsigned bn=(unsigned)(db<0?-db:db);
                if(newn>=9)break;
                out[newn++]=interpolate(a,b,an,an+bn);
                clipped=1;
            }
            if(db>=0){if(newn>=9)break;out[newn++]=b;}
            a=b;da=db;
        }
        n=newn;cur^=1;
    }
    if(n<3){stats.rejected++;return;}
    if(clipped)stats.clipped++;
    for(int i=1;i<n-1;i++)push_triangle(buf[cur][0],buf[cur][i],buf[cur][i+1],mat,flags,0,solid_color,tiny_color);
}

uint16_t sg3d_rgb(unsigned r,unsigned g,unsigned b){return (r&31)|((g&31)<<5)|((b&31)<<10);}
void sg3d_texture_init(SG3DTexture *t,const uint8_t *mip0,const uint8_t *mip1){
    t->mip[0]=(uint32_t)(uintptr_t)mip0;
    t->mip[1]=(uint32_t)(uintptr_t)(mip1?mip1:mip0);
}
void sg3d_set_palette(unsigned index,uint16_t color){if(index<256)PAL[index]=color;}
void sg3d_palette_rgb332(void){
    for(unsigned i=0;i<256;i++){
        unsigned r=((i>>5)&7)*31/7;
        unsigned g=((i>>2)&7)*31/7;
        unsigned b=(i&3)*31/3;
        sg3d_set_palette(i,sg3d_rgb(r,g,b));
    }
}
void sg3d_set_camera(SG3DCamera c){camera=c;}
void sg3d_set_skybox(const uint8_t *pixels){skybox_pixels=pixels;}
void sg3d_init(void){
    REG16(0x04000000)=4|0x0400;
    REG16(0x04000020)=128;REG16(0x04000022)=0;
    REG16(0x04000024)=0;REG16(0x04000026)=128;
    REG32(0x04000028)=0;REG32(0x0400002C)=0;
    camera=(SG3DCamera){0,0,0,0,0};
    skybox_pixels=0;
    sg3d_hud_init();
    page=0;count=0;
    for(unsigned i=0;i<256;i++)PAL[i]=0;
    /* Initialize both side-by-side virtual buffers. */
    for(unsigned y=0;y<80;y++)for(unsigned x=0;x<120;x++)VRAM[y*120+x]=0;
}
void sg3d_begin(uint8_t sky,uint8_t ground){
    count=0;objects_drawn=0;stats=(SG3DStats){0};
    sg3d_hud_begin_frame();
    page ^= 1;
    volatile uint16_t *fb=VRAM+page*60;
    if(skybox_pixels){
        /* Palette-indexed panorama; 256-column wrap and clamped vertical pan.
           Use 16-bit writes, two pixels per store on Mode 4. */
        int xoff=(int)(uint8_t)camera.yaw;
        int yoff=24+(int)(int8_t)camera.pitch;
        for(int y=0;y<80;y++){
            int sy=y+yoff;
            if(sy<0)sy=0;
            if(sy>127)sy=127;
            const uint8_t *src=skybox_pixels+(sy<<8);
            for(int x=0;x<60;x++){
                int sx=(xoff+(x<<1))&255;
                fb[y*120+x]=(uint16_t)src[sx]|((uint16_t)src[(sx+1)&255]<<8);
            }
        }
    }else{
        for(int y=0;y<SG3D_HEIGHT;y++){
            uint8_t col=y<40?sky:ground;
            uint16_t word=col | (uint16_t)(col<<8);
            for(int x=0;x<60;x++)fb[y*120+x]=word;
        }
    }
    sg3d_internal_framebuffer((uint8_t*)0x06000000+page*120);
}
#if SG3D_PERF_VERTEX_CACHE
static uint32_t cached_screen(unsigned index){
    if(screen_generation[index]!=mesh_generation){
        ClipPoint *p=&transformed[index];
        int inv=project_recip(p->z);
        int x=60+((p->x*inv)>>12),y=40-((p->y*inv)>>12);
        screen_cache[index]=pack_pos(x,y);
        screen_generation[index]=mesh_generation;
        stats.cached_vertices++;
    }
    return screen_cache[index];
}
#endif
void sg3d_draw_mesh(const SG3DMesh *mesh,const SG3DMaterial *materials,
                    unsigned material_count,SG3DTransform t){
    if(!mesh||!materials||!mesh->vertices||!mesh->faces||
       mesh->vertex_count>SG3D_MAX_VERTICES||!material_count)return;
    uint32_t scale=t.scale?t.scale:256;
    t.scale=(uint16_t)scale;
    int sy=sin_table[t.yaw],cy=sin_table[(uint8_t)(t.yaw+64)];
    int sp=sin_table[t.pitch],cp=sin_table[(uint8_t)(t.pitch+64)];
    int csy=sin_table[(uint8_t)(-camera.yaw)],ccy=sin_table[(uint8_t)(64-camera.yaw)];
    int csp=sin_table[(uint8_t)(-camera.pitch)],ccp=sin_table[(uint8_t)(64-camera.pitch)];
#if SG3D_PERF_OBJECT_CULL
    if(sphere_is_offscreen(mesh,t,sy,cy,sp,cp,csy,ccy,csp,ccp)){
        stats.culled_objects++;return;
    }
#endif
    objects_drawn++;
#if SG3D_PERF_FUSED_TRANSFORM
    prepare_view_transform(t,sy,cy,sp,cp,csy,ccy,csp,ccp);
#endif
#if SG3D_PERF_VERTEX_CACHE
    mesh_generation++;
    if(!mesh_generation){for(unsigned i=0;i<SG3D_MAX_VERTICES;i++)screen_generation[i]=0;mesh_generation=1;}
#endif
    for(unsigned i=0;i<mesh->vertex_count;i++){
        const SG3DVertex *v=&mesh->vertices[i];
        int32_t x=(v->x*(int32_t)scale)>>8;
        int32_t y=(v->y*(int32_t)scale)>>8;
        int32_t z=(v->z*(int32_t)scale)>>8;
#if SG3D_PERF_FUSED_TRANSFORM
        fused_vertex(&x,&y,&z);
#else
        yaw_rotate(&x,&z,sy,cy);pitch_rotate(&y,&z,sp,cp);
        x+=t.x-camera.x;y+=t.y-camera.y;z+=t.z-camera.z;
        yaw_rotate(&x,&z,csy,ccy);pitch_rotate(&y,&z,csp,ccp);
#endif
        transformed[i]=(ClipPoint){x,y,z,0,0};
#if SG3D_PERF_FAST_CLIP
        clip_codes[i]=vertex_clip_mask(&transformed[i]);
#endif
    }
    for(unsigned f=0;f<mesh->face_count;f++){
        const SG3DFace *face=&mesh->faces[f];
        stats.submitted++;
        if(face->a>=mesh->vertex_count||face->b>=mesh->vertex_count||
           face->c>=mesh->vertex_count||face->material>=material_count){stats.rejected++;continue;}
        ClipPoint tri[3]={transformed[face->a],transformed[face->b],transformed[face->c]};
        for(unsigned i=0;i<3;i++){
            tri[i].u=(int16_t)face->uv[i];
            tri[i].v=(int16_t)(face->uv[i]>>16);
        }
        if(tri[0].z>FAR_Z&&tri[1].z>FAR_Z&&tri[2].z>FAR_Z){stats.rejected++;continue;}
#if SG3D_PERF_FAST_CLIP
        uint8_t m0=clip_codes[face->a],m1=clip_codes[face->b],m2=clip_codes[face->c];
        if((m0&m1&m2)!=0){stats.rejected++;continue;}
        if((m0|m1|m2)==0){
            /* All three vertices already satisfy every clip plane. */
#if SG3D_PERF_VERTEX_CACHE
            uint32_t packed[3]={cached_screen(face->a),cached_screen(face->b),cached_screen(face->c)};
            push_triangle(tri[0],tri[1],tri[2],&materials[face->material],face->flags,packed,face->solid_color,face->tiny_color);
#else
            push_triangle(tri[0],tri[1],tri[2],&materials[face->material],face->flags,0,face->solid_color,face->tiny_color);
#endif
        } else
#endif
        clip_and_enqueue(tri,&materials[face->material],face->flags,face->solid_color,face->tiny_color);
    }
}
void sg3d_end(void){
#if SG3D_PERF_BUCKET_SORT
    /* 128-bucket approximate painter order: O(triangles + bins), instead of
       insertion sorting full 36-byte queue records (worst-case O(N^2)).
       Equivalent to the upstream stage's depth-bin strategy in principle,
       but not its exact logarithmic bin thresholds. Expect occasional painter
       ordering differences when triangles overlap at similar depths. */
    for(unsigned b=0;b<SG3D_DEPTH_BUCKETS;b++)bin_head[b]=0xffff;
    for(unsigned i=0;i<count;i++){
        /* 8.8 fixed depth average; bin 0 near, 127 far. */
        int32_t depth=queue[i].depth/3;
        unsigned bin=depth<=0?0:(unsigned)depth>>7;
        if(bin>=SG3D_DEPTH_BUCKETS)bin=SG3D_DEPTH_BUCKETS-1;
        bin_next[i]=bin_head[bin];bin_head[bin]=(uint16_t)i;
    }
    for(int b=SG3D_DEPTH_BUCKETS-1;b>=0;b--){
        for(unsigned i=bin_head[b];i!=0xffff;i=bin_next[i]){
            QueuedTri *t=&queue[i];
            sg3d_internal_triangle(t->screen,t->uv,t->color,t->texture,t->mode);
        }
    }
#else
    /* v0.12.1 exact painter order, used for A/B verification. */
    for(unsigned i=1;i<count;i++){
        QueuedTri e=queue[i];unsigned j=i;
        while(j>0&&queue[j-1].depth<e.depth){queue[j]=queue[j-1];j--;}
        queue[j]=e;
    }
    for(unsigned i=0;i<count;i++){
        QueuedTri *t=&queue[i];
        sg3d_internal_triangle(t->screen,t->uv,t->color,t->texture,t->mode);
    }
#endif
    stats.drawn=(uint16_t)count;
    sg3d_hud_render(page,stats.drawn,objects_drawn);
    /* Flip the BG2 window ONLY during VBlank; the two 120x80 buffers
       are placed side-by-side within a 240x160 Mode 4 page. */
    while(REG16(0x04000006)>=160){}
    while(REG16(0x04000006)<160){}
    sg3d_hud_present_oam();
    REG32(0x04000028)=(page?120u:0u)<<8;
}
SG3DStats sg3d_stats(void){return stats;}
