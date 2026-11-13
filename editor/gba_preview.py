"""Approximate SG3D GBA viewport with full-res OBJ text and image HUD.

120x80 Mode 4 8-bit BG2 -> hardware 2x -> 240x160 LCD. Native OBJ UI.
RGB332, affine (not perspective corrected) texture lookup, artist-defined UV,
shared palette, nearest filtering, global far-to-near triangle order.
This is a preview, not an emulator of the ARM rasterizer / fill conventions.
"""
import math
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
from project_export import parse_obj, resolve, make_texture, rgb332
from hud_native_font import draw_native_text

W,H=120,80
PALETTE=[(((i>>5)&7)*255//7,((i>>2)&7)*255//7,(i&3)*255//3) for i in range(256)]


def transform(v,obj):
    sc=float(obj.get('scale',1))
    x,y,z=(a*sc for a in v)
    yaw,pitch=(math.radians(float(a)) for a in obj.get('rotation',[0,0]))
    x,z=x*math.cos(yaw)+z*math.sin(yaw),z*math.cos(yaw)-x*math.sin(yaw)
    y,z=y*math.cos(pitch)-z*math.sin(pitch),y*math.sin(pitch)+z*math.cos(pitch)
    p=obj['position'];return x+p[0],y+p[1],z+p[2]


def view(v,cam):
    p=cam.get('position',[0,0,0]);x,y,z=(v[i]-p[i] for i in range(3))
    yaw,pitch=(math.radians(-float(a)) for a in cam.get('rotation',[0,0]))
    x,z=x*math.cos(yaw)+z*math.sin(yaw),z*math.cos(yaw)-x*math.sin(yaw)
    y,z=y*math.cos(pitch)-z*math.sin(pitch),y*math.sin(pitch)+z*math.cos(pitch)
    return x,y,z


def render_scene(doc,base,mesh_cache=None,texture_cache=None,textures=True):
    """Return (RGB PIL image 240x160, number of accepted triangles)."""
    mesh_cache={} if mesh_cache is None else mesh_cache
    texture_cache={} if texture_cache is None else texture_cache
    indices=bytearray([1 if y<40 else 5 for y in range(H) for x in range(W)])
    tris=[];camera=doc.get('camera',{})
    sky=(doc.get('skybox') or {}).get('file')
    if sky:
        sp=resolve(base,sky)
        if sp.is_file():
            if ('sky',sp) not in texture_cache:
                texture_cache['sky',sp]=Image.open(sp).convert('RGB').resize((256,128),Image.Resampling.NEAREST)
            panorama=texture_cache['sky',sp]
            px=panorama.load();yaw=int(float(camera.get('rotation',[0,0])[0])*256/360)&255
            pit=round(float(camera.get('rotation',[0,0])[1])*256/360)
            for y in range(80):
                yy=max(0,min(127,y+24+pit))
                for x in range(120):indices[y*120+x]=rgb332(*px[(yaw+x)&255,yy])
    for obj in doc.get('objects',[]):
        if not obj.get('mesh'):continue
        path=resolve(base,obj['mesh'])
        if path not in mesh_cache:mesh_cache[path]=parse_obj(path)
        mesh=mesh_cache[path]
        positions=[]
        for vert in mesh['vertices']:
            x,y,z=view(transform(vert,obj),camera)
            # Uses same projected focal length as engine/sg3d.c.
            positions.append((60+90*x/z,40-90*y/z,z) if z>1.0 else None)
        for corners,mi in mesh['faces']:
            pp=[positions[i] for i,uv in corners]
            if any(p is None for p in pp):continue  # Near clip remains approximate.
            ax,ay,_=pp[0];bx,by,_=pp[1];cx,cy,_=pp[2]
            area=(bx-ax)*(cy-ay)-(cx-ax)*(by-ay)
            if abs(area)<0.00001:continue
            uv=[v[1] for v in corners]
            material=mesh['mtl'].get(mesh['materials'][mi],{})
            color=rgb332(*(round(v*255) for v in material.get('diffuse',(.85,.85,.85))))
            color=max(1,color)
            tex_name=obj.get('texture') or material.get('texture')
            mips=None
            if textures and tex_name:
                tex_path=resolve(base,tex_name) if obj.get('texture') else Path(tex_name).resolve()
                if tex_path.is_file():
                    if tex_path not in texture_cache:texture_cache[tex_path]=make_texture(tex_path)
                    mips=texture_cache[tex_path]
            mode=obj.get('mode','texture')
            if not mips and mode in ('texture','alpha','additive','darken'):mode='flat'
            tris.append(((pp[0][2]+pp[1][2]+pp[2][2])/3,pp,uv,mode,color,mips))
    # Same general back-to-front ordering as the GBA queue.
    tris.sort(key=lambda t:t[0],reverse=True)
    for depth,pp,uv,mode,color,mips in tris:
        x0,y0,_=pp[0];x1,y1,_=pp[1];x2,y2,_=pp[2]
        denom=(y1-y2)*(x0-x2)+(x2-x1)*(y0-y2)
        if abs(denom)<0.00001:continue
        minx=max(0,math.floor(min(x0,x1,x2)));maxx=min(W-1,math.ceil(max(x0,x1,x2)))
        miny=max(0,math.floor(min(y0,y1,y2)));maxy=min(H-1,math.ceil(max(y0,y1,y2)))
        if maxx<minx or maxy<miny:continue
        # Smaller faces switch to 16x16 mip like the rasterizer's mip path.
        dim=16 if abs(denom)<240 else 32
        tex=mips[1 if dim==16 else 0] if mips else None
        inv=1.0/denom
        for y in range(miny,maxy+1):
            for x in range(minx,maxx+1):
                xx=x+.5;yy=y+.5
                w0=((y1-y2)*(xx-x2)+(x2-x1)*(yy-y2))*inv
                w1=((y2-y0)*(xx-x2)+(x0-x2)*(yy-y2))*inv
                w2=1.0-w0-w1
                if min(w0,w1,w2)<-0.00001:continue
                pos=y*W+x
                pix=color
                if mode=='tint':
                    old=indices[pos];pix=(old&0x1f)|0x40
                elif mode in ('texture','alpha','additive','darken') and tex:
                    # UV is repeated/wrapped as in the GBA 32x32 texture mapper.
                    u=(uv[0][0]*w0+uv[1][0]*w1+uv[2][0]*w2)
                    v=(uv[0][1]*w0+uv[1][1]*w1+uv[2][1]*w2)
                    ui=int(u*dim)%dim;vi=int((1-v)*dim)%dim
                    pix=tex[vi*dim+ui]
                    if mode in ('alpha','additive','darken') and pix==0:continue
                    if mode=='darken':
                        prev=indices[pos];pix=((prev>>5)>>1<<5)|(((prev>>2)&7)>>1<<2)|((prev&3)>>1)
                    elif mode=='additive':
                        prev=indices[pos]
                        pix=(min(7,(prev>>5)+(pix>>5))<<5)|(min(7,((prev>>2)&7)+((pix>>2)&7))<<2)|min(3,(prev&3)+(pix&3))
                indices[pos]=pix
    img=Image.new('P',(W,H));img.putpalette([v for rgb in PALETTE for v in rgb]);img.frombytes(bytes(indices))
    img=img.convert('RGB')
    pen=ImageDraw.Draw(img)
    for item in doc.get('hud',[]):
        if not item.get('visible',True):continue
        kind=item.get('type','text');x=int(item.get('x',2));y=int(item.get('y',2))
        ww=int(item.get('w',50));hh=int(item.get('h',7))
        fg=PALETTE[int(item.get('fg',255))];bgidx=int(item.get('bg',0));bg=PALETTE[bgidx]
        if kind in ('rect','bar','dialogue') or (kind=='text' and bgidx):
            pen.rectangle((x,y,x+ww-1,y+hh-1),fill=bg)
        if kind=='bar':
            maximum=max(1,int(item.get('maximum',1)))
            value=max(0,min(maximum,int(item.get('value',0))))
            if value:pen.rectangle((x,y,x+(ww*value)//maximum-1,y+hh-1),fill=fg)
    # Native hardware sprite overlay: glyphs and PNG images are drawn only
    # after the low-resolution 3D framebuffer has been scaled 2x.
    img=img.resize((240,160),Image.Resampling.NEAREST)
    native_pen=ImageDraw.Draw(img)
    for item in doc.get('hud',[]):
        if not item.get('visible',True):continue
        kind=item.get('type','text');x=int(item.get('x',2));y=int(item.get('y',2))
        ww=int(item.get('w',50));hh=int(item.get('h',7))
        fg=PALETTE[int(item.get('fg',255))]
        if kind in ('text','dialogue'):
            label=str(item.get('text','')).upper()
            if kind=='text' and item.get('maximum'):label+=str(item.get('value',0))
            x+=(3 if kind=='dialogue' else 0);y+=(3 if kind=='dialogue' else 0)
            draw_native_text(native_pen,x*2,y*2,label,fg,27)
        elif kind=='sprite' and item.get('file'):
            p=resolve(base,item['file'])
            if p.is_file():
                sprite=Image.open(p).convert('RGBA').resize((ww*2,hh*2),Image.Resampling.NEAREST)
                img.paste(sprite,(x*2,y*2),sprite)
    return img,len(tris)
