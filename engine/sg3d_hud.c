#include "sg3d_hud.h"
#define VRAM16 ((volatile uint16_t*)0x06000000)
#define REG16(a) (*(volatile uint16_t*)(a))
#define MAX_HUD 16
#ifndef SG3D_HUD_NATIVE_UI
#define SG3D_HUD_NATIVE_UI 1
#endif
static SG3DHUDItem hud[MAX_HUD];
static unsigned num,show_profiler;
static unsigned frames,fps;
static uint16_t fps_at,render_started;
static volatile uint16_t *canvas;
/* GBA VRAM does NOT support normal 8-bit writes. Byte stores mirror to both
   halfword bytes, turning two adjacent HUD pixels into one doubled pixel!
   Preserve the neighbouring pixel through a 16-bit read-modify-write. */
static void pix(int x,int y,uint8_t c){
    if((unsigned)x<120 && (unsigned)y<80){
        volatile uint16_t *p=canvas+y*120+(x>>1);
        uint16_t old=*p;
        *p=(x&1)?(uint16_t)((old&0x00ff)|((uint16_t)c<<8))
                 :(uint16_t)((old&0xff00)|c);
    }
}
static void rect(int x,int y,int w,int h,uint8_t c){
    if(w<1 || h<1)return;
    int x1=x+w,y1=y+h;
    if(x<0)x=0;if(y<0)y=0;if(x1>120)x1=120;if(y1>80)y1=80;
    for(int yy=y;yy<y1;yy++)for(int xx=x;xx<x1;xx++)pix(xx,yy,c);
}
/* Deliberately tiny 3x5 font for low-resolution hardware HUD. */
static uint16_t glyph(char c){
    switch(c){
    case '0':return 0x7B6F;case '1':return 0x2497;case '2':return 0x73E7;
    case '3':return 0x73CF;case '4':return 0x5BC9;case '5':return 0x79CF;
    case '6':return 0x79EF;case '7':return 0x7249;case '8':return 0x7BEF;
    case '9':return 0x7BCF;case 'A':return 0x7BED;case 'B':return 0x6BAE;
    case 'C':return 0x7927;case 'D':return 0x6B6E;case 'E':return 0x79E7;
    case 'F':return 0x79E4;case 'G':return 0x796F;case 'H':return 0x5BED;
    case 'I':return 0x7247;case 'J':return 0x124F;case 'K':return 0x5BAD;
    case 'L':return 0x4927;case 'M':return 0x5FED;case 'N':return 0x5F6D;
    case 'O':return 0x7B6F;case 'P':return 0x7BE4;case 'Q':return 0x7B7B;
    case 'R':return 0x7BAD;case 'S':return 0x79CF;case 'T':return 0x7249;
    case 'U':return 0x5B6F;case 'V':return 0x5B6A;case 'W':return 0x5BFD;
    case 'X':return 0x5AAD;case 'Y':return 0x5A49;case 'Z':return 0x72A7;
    case ':':return 0x0404;case '.':return 0x0001;case '!':return 0x2492;
    case '-':return 0x01C0;case '/':return 0x1248;case '?':return 0x7282;
    case '+':return 0x05D0;case '_':return 0x0007;
    default:return 0;
    }
}
static void text(int x,int y,const char *s,uint8_t color,unsigned maxchars){
    if(!s)return;
    for(unsigned n=0;*s && n<maxchars;n++,s++,x+=4){
        if(*s=='\n'){y+=7;x-=4;continue;}
        char c=*s;if(c>='a'&&c<='z')c-=32;
        uint16_t bits=glyph(c);
        for(int yy=0;yy<5;yy++)for(int xx=0;xx<3;xx++)
            if(bits & (1u<<(14-yy*3-xx)))pix(x+xx,y+yy,color);
    }
}
/* Freestanding GBA build: avoid implicit __aeabi_uidiv dependencies. */
static unsigned udiv32(unsigned a,unsigned b){
    if(!b)return 0;
    unsigned q=0,r=0;
    for(int bit=31;bit>=0;bit--){
        unsigned overflow=r>>31;
        r=(r<<1)|((a>>bit)&1u);
        if(overflow||r>=b){r-=b;q|=1u<<bit;}
    }
    return q;
}
static void number(int x,int y,int value,uint8_t c){
    char str[15];unsigned n=0;
    unsigned v=(unsigned)(value<0?-(int64_t)value:value);
    do{unsigned q=udiv32(v,10);str[n++]=(char)('0'+v-q*10);v=q;}while(v&&n<12);
    if(value<0)str[n++]='-';
    for(unsigned i=0;i<n/2;i++){char ch=str[i];str[i]=str[n-1-i];str[n-1-i]=ch;}
    str[n]=0;text(x,y,str,c,14);
}

#if SG3D_HUD_NATIVE_UI
/* Native 240x160 OBJ overlay over hardware-scaled BG2. Bitmap modes only
   expose BG2, so using another BG layer for sharp UI is NOT possible.

   Mode 4's OBJ character region is 0x06014000..0x06017fff (16 KiB).
   With 8bpp sprites this is 256 8x8 tiles. Tile indices in OBJ attr2
   count *32* bytes, so 8bpp indices must be even. 1D OBJ mapping is used.
   NO byte stores to VRAM: the GBA mirrors 8-bit VRAM writes across both bytes.
*/
#define HUD_OBJ_CHAR ((volatile uint16_t*)0x06014000)
#define HUD_OBJ_PAL ((volatile uint16_t*)0x05000200)
#define HUD_OAM ((volatile uint16_t*)0x07000000)
#define HUD_MAX_SPRITES 128u
#define HUD_MAX_TILES 256u
#define HUD_EWRAM __attribute__((section(".ewram_bss")))
#include "hud_native_font.inc"
static uint16_t hud_oam_shadow[128*4] HUD_EWRAM;
static unsigned hud_sprite_count,hud_tile_count,hud_dropped;

void sg3d_hud_init(void){
    /* OBJ on; OBJ 1D tiles. Keep affine BG2 unchanged. */
    REG16(0x04000000)|=0x1040;
    for(unsigned i=0;i<256;i++){
        unsigned r=((i>>5)&7)*31/7;
        unsigned g=((i>>2)&7)*31/7;
        unsigned b=(i&3)*31/3;
        HUD_OBJ_PAL[i]=(uint16_t)(r|(g<<5)|(b<<10));
    }
    /* Preserve opaque black while reserving OBJ palette index 0 for alpha. */
    HUD_OBJ_PAL[1]=0;
    hud_sprite_count=0;hud_tile_count=0;hud_dropped=0;
    for(unsigned i=0;i<128;i++){
        HUD_OAM[i*4]=0x0200;HUD_OAM[i*4+1]=0;
        HUD_OAM[i*4+2]=0;HUD_OAM[i*4+3]=0;
    }
}
static void obj_begin(void){
    hud_sprite_count=0;hud_tile_count=0;hud_dropped=0;
}
static int obj_alloc(unsigned tiles,int x,int y,unsigned shape,unsigned size){
    if(hud_sprite_count>=HUD_MAX_SPRITES||hud_tile_count+tiles>HUD_MAX_TILES){
        hud_dropped++;return -1;
    }
    unsigned slot=hud_sprite_count++;
    unsigned tile=512u+hud_tile_count*2u; /* 8bpp tile = 64 bytes */
    unsigned o=slot*4;
    hud_oam_shadow[o]=(uint16_t)((y&255)|0x2000|(shape<<14));
    hud_oam_shadow[o+1]=(uint16_t)((x&511)|(size<<14));
    hud_oam_shadow[o+2]=(uint16_t)(tile|0x0000); /* priority 0, over BG2 */
    hud_oam_shadow[o+3]=0;
    hud_tile_count+=tiles;
    return (int)(tile-512)/2; /* byte-addressed base tile in OBJ character VRAM */
}
static void obj_tile8(unsigned tile,const uint8_t *pixels){
    volatile uint16_t *dest=HUD_OBJ_CHAR+tile*32u;
    for(unsigned i=0;i<32;i++){
        uint8_t lo=pixels[i*2],hi=pixels[i*2+1];
        dest[i]=(uint16_t)lo|((uint16_t)hi<<8);
    }
}
static __attribute__((noinline)) void obj_zero(uint8_t *data,unsigned n){
    volatile uint8_t *p=data;for(unsigned i=0;i<n;i++)p[i]=0;
}
static void obj_glyph(int x,int y,char c,uint8_t color){
    if(x<=-8||x>=240||y<=-8||y>=160)return;
    if(c>='a'&&c<='z')c-=32;
    if(c<32||c>126)c='?';
    if(c==' ')return;
    int tile=obj_alloc(1,x,y,0,0);if(tile<0)return;
    uint8_t pixels[64];obj_zero(pixels,64);
    const uint8_t *rows=hud_font_5x7[(unsigned)c-32u];
    for(unsigned yy=0;yy<7;yy++){
        for(unsigned xx=0;xx<5;xx++){
            if(rows[yy]&(1u<<(4-xx)))pixels[yy*8+xx]=color?color:1;
        }
    }
    obj_tile8((unsigned)tile,pixels);
}
static void obj_text(int x,int y,const char *str,uint8_t color,unsigned maxchars){
    if(!str)return;
    int startx=x;
    for(unsigned n=0;*str && n<maxchars;str++,n++){
        if(*str=='\n'){x=startx;y+=9;continue;}
        obj_glyph(x,y,*str,color);x+=6;
    }
}
static void obj_number(int x,int y,int value,uint8_t color){
    char b[15];unsigned n=0;
    unsigned v=(unsigned)(value<0?-(int64_t)value:value);
    do{unsigned q=udiv32(v,10);b[n++]=(char)('0'+v-q*10);v=q;}while(v&&n<12);
    if(value<0)b[n++]='-';
    for(unsigned i=0;i<n/2;i++){char c=b[i];b[i]=b[n-1-i];b[n-1-i]=c;}
    b[n]=0;obj_text(x,y,b,color,14);
}
static void obj_image(int x,int y,int width,int height,const uint8_t *src){
    if(!src||width<=0||height<=0)return;
    /* 16x16 native-resolution sprites (four 8x8 tiles each). Sparse
       transparent areas are not allocated. Max 64 filled macroblocks. */
    for(int top=0;top<height;top+=16)for(int left=0;left<width;left+=16){
        int sw=width-left;if(sw>16)sw=16;
        int sh=height-top;if(sh>16)sh=16;
        if(x+left>=240||x+left+sw<=0||y+top>=160||y+top+sh<=0)continue;
        unsigned any=0;
        for(int yy=0;yy<sh&&!any;yy++)for(int xx=0;xx<sw;xx++){
            if(src[(top+yy)*width+left+xx]){any=1;break;}
        }
        if(!any)continue;
        int base=obj_alloc(4,x+left,y+top,0,1);
        if(base<0)return;
        for(unsigned tile_y=0;tile_y<2;tile_y++)for(unsigned tile_x=0;tile_x<2;tile_x++){
            uint8_t pixels[64];obj_zero(pixels,64);
            for(unsigned yy=0;yy<8;yy++)for(unsigned xx=0;xx<8;xx++){
                unsigned sx=tile_x*8+xx,sy=tile_y*8+yy;
                if(sx<(unsigned)sw&&sy<(unsigned)sh){
                    uint8_t color=src[(top+(int)sy)*width+left+(int)sx];
                    pixels[yy*8+xx]=color;
                }
            }
            obj_tile8((unsigned)base+tile_y*2+tile_x,pixels);
        }
    }
}
void sg3d_hud_present_oam(void){
    /* Called AFTER entering VBlank; OAM updates during active drawing
       are unreliable on hardware. Invisible entries must be disabled. */
    for(unsigned i=0;i<128;i++){
        unsigned o=i*4;
        if(i<hud_sprite_count){
            HUD_OAM[o]=hud_oam_shadow[o];
            HUD_OAM[o+1]=hud_oam_shadow[o+1];
            HUD_OAM[o+2]=hud_oam_shadow[o+2];
        }else HUD_OAM[o]=0x0200;
    }
}
unsigned sg3d_hud_dropped_sprites(void){return hud_dropped;}
#else
void sg3d_hud_init(void){}
void sg3d_hud_present_oam(void){}
unsigned sg3d_hud_dropped_sprites(void){return 0;}
#endif

void sg3d_hud_load(const SG3DHUDItem *items,unsigned count){
    if(count>MAX_HUD)count=MAX_HUD;
    num=count;
    for(unsigned i=0;i<count;i++)hud[i]=items[i];
}
void sg3d_hud_set_value(unsigned i,int32_t value){
    if(i<num){if(value>32767)value=32767;if(value< -32768)value= -32768;hud[i].value=(int16_t)value;}
}
void sg3d_hud_set_visible(unsigned i,unsigned visible){if(i<num)hud[i].visible=!!visible;}
void sg3d_hud_profiler(unsigned enabled){show_profiler=!!enabled;frames=0;fps=0;fps_at=0;
    if(enabled){
        REG16(0x0400010A)=0;REG16(0x04000108)=0;REG16(0x0400010A)=0x82; /* Timer 2 /256 */
        REG16(0x0400010E)=0;REG16(0x0400010C)=0;REG16(0x0400010E)=0x83; /* Timer 3 /1024 */
    }else {REG16(0x0400010A)=0;REG16(0x0400010E)=0;}
}
static unsigned txtlen(const char *s){unsigned n=0;if(s)while(s[n]&&n<27)n++;return n;}
void sg3d_hud_begin_frame(void){if(show_profiler)render_started=REG16(0x04000108);}
void sg3d_hud_render(unsigned page,unsigned triangles,unsigned objects){
    canvas=VRAM16+(page&1)*60;
#if SG3D_HUD_NATIVE_UI
    obj_begin();
#endif
    for(unsigned i=0;i<num;i++){
        SG3DHUDItem *h=&hud[i];if(!h->visible)continue;
        int x=h->x,y=h->y,w=h->w,hh=h->h;
        if(h->kind==SG3D_HUD_RECT)rect(x,y,w,hh,h->bg);
        else if(h->kind==SG3D_HUD_BAR){
            rect(x,y,w,hh,h->bg);
            int amount=h->value;if(amount<0)amount=0;
            int maximum=h->maximum>0?h->maximum:1;
            if(amount>maximum)amount=maximum;
            rect(x,y,(int)udiv32((unsigned)(w*amount),(unsigned)maximum),hh,h->fg);
        }else if(h->kind==SG3D_HUD_TEXT){
            if(h->bg)rect(x-1,y-1,w?w:70,hh?hh:7,h->bg);
#if SG3D_HUD_NATIVE_UI
            obj_text(x*2,y*2,h->text,h->fg,27);
            if(h->maximum)obj_number(x*2+6*(unsigned)(h->text?txtlen(h->text):0),y*2,h->value,h->fg);
#else
            text(x,y,h->text,h->fg,27);
            if(h->maximum)number(x+4*(unsigned)(h->text?txtlen(h->text):0),y,h->value,h->fg);
#endif
        }else if(h->kind==SG3D_HUD_DIALOGUE){
            rect(x,y,w,hh,h->bg);
#if SG3D_HUD_NATIVE_UI
            obj_text((x+3)*2,(y+3)*2,h->text,h->fg,27);
#else
            text(x+3,y+3,h->text,h->fg,(unsigned)(w>6?(w-6)/4:0));
#endif
        }else if(h->kind==SG3D_HUD_SPRITE && h->sprite){
#if SG3D_HUD_NATIVE_UI
            obj_image(x*2,y*2,w*2,hh*2,h->sprite);
#else
            for(int yy=0;yy<hh;yy++)for(int xx=0;xx<w;xx++){
                uint8_t v=h->sprite[yy*w+xx];if(v)pix(x+xx,y+yy,v);
            }
#endif
        }
    }
    if(show_profiler){
        uint16_t now=REG16(0x0400010C);frames++;
        if((uint16_t)(now-fps_at)>=16384){fps=frames;frames=0;fps_at=now;}
        unsigned elapsed=(uint16_t)(REG16(0x04000108)-render_started);
        unsigned render_ms=udiv32(elapsed,66); /* 16.78 MHz / 256 / 1000 */
        /* Two rows, with meaningful labels: the old 1-letter overlay was
           nearly unreadable on a physical 240x160 LCD or scaled mGBA. */
        rect(0,0,120,15,1);
#if SG3D_HUD_NATIVE_UI
        obj_text(4,3,"FPS",255,3);obj_number(26,3,(int)fps,255);
        obj_text(112,3,"TRI",255,3);obj_number(136,3,(int)triangles,255);
        obj_text(4,16,"OBJ",255,3);obj_number(26,16,(int)objects,255);
        obj_text(112,16,"MS",255,2);obj_number(130,16,(int)render_ms,255);
#else
        text(2,1,"FPS",255,3);number(17,1,(int)fps,255);
        text(56,1,"TRI",255,3);number(72,1,(int)triangles,255);
        text(2,8,"OBJ",255,3);number(17,8,(int)objects,255);
        text(56,8,"MS",255,2);number(68,8,(int)render_ms,255);
#endif
    }
}
