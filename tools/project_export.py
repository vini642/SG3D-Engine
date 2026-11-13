#!/usr/bin/env python3
"""SG3D scene exporter: JSON scene + OBJ/MTL + PNG -> actual GBA C source.

python tools/project_export.py examples/demo_project.sg3d.json
python build.py --main generated/main.c

Uses Pillow for PNG -> 32x32 & 16x16 RGB332 mipmaps. All expensive PNG,
OBJ and C generation happen on the PC, not on the GBA.
"""
import argparse
import json
import math
import re
import tempfile
from pathlib import Path
from node_scripts import compile_graph
from orbit_controller import orbit_script_controls
from animation_assets import emit_c,validated_clips
from audio_assets import sound_manifest,emit_c_header


MODES={'flat':0,'texture':1,'alpha':2,'additive':3,'darken':4,'tint':5}

def sym(s):
    s=re.sub('[^a-zA-Z0-9_]+','_',s).strip('_')
    if not s or s[0].isdigit():s='asset_'+s
    return s

def resolve(base, path):
    p=Path(path)
    return (p if p.is_absolute() else base/p).resolve()

def read_mtl(path):
    mats={}; current=None
    if not path.is_file():return mats
    for raw in path.read_text(encoding='utf-8-sig', errors='replace').splitlines():
        parts=raw.partition('#')[0].strip().split()
        if not parts:continue
        key=parts[0]
        if key=='newmtl' and len(parts)>1:
            current=' '.join(parts[1:]);mats[current]={'diffuse':(0.9,0.9,0.9),'texture':None}
        elif current and key=='Kd' and len(parts)>=4:
            try:mats[current]['diffuse']=tuple(max(0,min(1,float(x))) for x in parts[1:4])
            except ValueError:pass
        elif current and key=='map_Kd' and len(parts)>1:
            # Relative texture references in ordinary MTL files. Complex option
            # switches (-o, -s etc.) are not currently interpreted.
            candidate=' '.join(parts[1:])
            if not candidate.startswith('-'):mats[current]['texture']=str(resolve(path.parent,candidate))
    return mats

def parse_obj(path):
    """Keep UVs on faces, not vertices; material face indices are stable."""
    path=Path(path)
    vertices=[];uvs=[];faces=[];material_names=['default'];names={'default':0};mtl={};current='default'
    for no,raw in enumerate(path.read_text(encoding='utf-8-sig',errors='replace').splitlines(),1):
        bits=raw.partition('#')[0].strip().split()
        if not bits:continue
        op=bits[0]
        try:
            if op=='v' and len(bits)>=4:vertices.append(tuple(float(v) for v in bits[1:4]))
            elif op=='vt' and len(bits)>=3:uvs.append((float(bits[1]),float(bits[2])))
            elif op=='mtllib' and len(bits)>1:
                mtl.update(read_mtl(resolve(path.parent,' '.join(bits[1:]))))
            elif op=='usemtl':
                current=' '.join(bits[1:])
                if current not in names:
                    names[current]=len(material_names);material_names.append(current)
            elif op=='f':
                corners=[]
                for item in bits[1:]:
                    pair=item.split('/')
                    vi=int(pair[0]);vi=vi-1 if vi>0 else len(vertices)+vi
                    if vi<0 or vi>=len(vertices):raise ValueError('vertex index out of range')
                    uv=(0.,0.)
                    if len(pair)>1 and pair[1]:
                        ti=int(pair[1]);ti=ti-1 if ti>0 else len(uvs)+ti
                        if ti<0 or ti>=len(uvs):raise ValueError('UV index out of range')
                        uv=uvs[ti]
                    corners.append((vi,uv))
                if len(corners)<3:raise ValueError('face needs at least 3 corners')
                for k in range(1,len(corners)-1):faces.append((corners[0],corners[k],corners[k+1],names[current]))
        except (ValueError,IndexError) as exc:
            raise ValueError(f'{path.name}:{no}: {exc}') from exc
    if not vertices or not faces:raise ValueError(f'{path.name}: no mesh data')
    # Keep only referenced vertices so even OBJs with unused vertices can work.
    used={};ordered=[];triangles=[]
    for a,b,c,m in faces:
        idx=[]
        for old,uv in (a,b,c):
            if old not in used:used[old]=len(ordered);ordered.append(vertices[old])
            idx.append((used[old],uv))
        triangles.append((idx,m))
    if len(ordered)>256:raise ValueError(f'{path.name}: {len(ordered)} vertices; split your mesh into <=256-vertex chunks')
    if len(triangles)>65535:raise ValueError(f'{path.name}: too many faces')
    if len(material_names)>256:raise ValueError(f'{path.name}: too many materials; limit 256')
    return {'vertices':ordered,'faces':triangles,'materials':material_names,'mtl':mtl,'path':path}

def rgb332(r,g,b):
    return (int(r*7/255+0.5)<<5)|(int(g*7/255+0.5)<<2)|int(b*3/255+0.5)

def material_rgb(diffuse):
    return max(1,rgb332(*(int(x*255) for x in diffuse)))

def make_texture(path):
    try:from PIL import Image
    except ImportError as e:raise RuntimeError('Pillow is required to export PNG textures. Run: python -m pip install Pillow') from e
    img=Image.open(path).convert('RGBA')
    result=[]
    for dim in (32,16):
        mip=img.resize((dim,dim),Image.Resampling.BOX)
        tex=[]
        for r,g,b,a in (mip.get_flattened_data() if hasattr(mip,"get_flattened_data") else mip.getdata()):
            val=rgb332(r,g,b)
            tex.append(0 if a<128 else max(1,val))
        result.append(tex)
    return result

def conservative_bounds(vertices):
    """Baked 8.8 mesh-space sphere; 0 radius means never cull this mesh.

    Calculate using already-rounded source coordinates, so the bound contains
    exactly the coordinates the GBA actually transforms.
    """
    import math
    coords=[tuple(int(round(c*256)) for c in v) for v in vertices]
    mid=tuple((min(v[i] for v in coords)+max(v[i] for v in coords))//2 for i in range(3))
    radius=math.isqrt(max(sum((v[i]-mid[i])**2 for i in range(3)) for v in coords))+3
    if radius>65535:return (0,0,0,0)  # too big, must avoid unsafe bound
    return (*mid,radius)


def solid_texture_triangle(corners, mip):
    """Conservatively bake a single RGB332 texel when BOTH LODs are uniform
    across the full UV rectangle (including wrap and a 1-texel margin).
    No interpolation guesswork: if uncertain, retain textured rasterization.
    """
    import math
    color=None
    for dim,texels in ((32,mip[0]),(16,mip[1])):
        uv=[point[1] for point in corners]
        us=[pt[0]*dim for pt in uv];vs=[(1-pt[1])*dim for pt in uv]
        # Include neighboring texels to cover fixed-point interpolation edge cases.
        x0=math.floor(min(us))-1;x1=math.ceil(max(us))+1
        y0=math.floor(min(vs))-1;y1=math.ceil(max(vs))+1
        xs=range(dim) if x1-x0>=dim else [(u%dim) for u in range(x0,x1+1)]
        ys=range(dim) if y1-y0>=dim else [(v%dim) for v in range(y0,y1+1)]
        for y in ys:
            for x in xs:
                v=texels[y*dim+x]
                if v==0:return None  # transparent/clear texel cannot become opaque
                if color is not None and v!=color:return None
                color=v
    return color


def tiny_triangle_color(corners,mips):
    """Approximate texture color for tiny distant triangles. This is an
    explicitly lossy LOD shortcut, never used on alpha/blend materials.
    Four barycentric samples from 16x16 mip level help avoid picking one
    arbitrary corner on colorful atlases. Color zero disallows replacement.
    """
    import math
    uv=[point[1] for point in corners]
    samples=((1/3,1/3,1/3),(.6,.2,.2),(.2,.6,.2),(.2,.2,.6))
    colors=[]
    for w in samples:
        u=sum(w[i]*uv[i][0] for i in range(3))
        v=sum(w[i]*(1-uv[i][1]) for i in range(3))
        tx=math.floor(u*16)%16;ty=math.floor(v*16)%16
        c=mips[1][ty*16+tx]
        if c==0:return None
        colors.append(c)
    # Average the actual RGB332 channels, not the packed index integers.
    rr=round(sum(c>>5 for c in colors)/len(colors))
    gg=round(sum((c>>2)&7 for c in colors)/len(colors))
    bb=round(sum(c&3 for c in colors)/len(colors))
    return max(1,(rr<<5)|(gg<<2)|bb)


def array_decl(type_,name,values,per=16):
    rows=[f'static const {type_} {name}[] = {{']
    for i in range(0,len(values),per):
        rows.append('    '+', '.join(str(v) for v in values[i:i+per])+',')
    rows.append('};')
    return '\n'.join(rows)

def vec_float(item,key,default):
    v=item.get(key,default)
    if not isinstance(v,(list,tuple)) or len(v)!=len(default):raise ValueError(f'bad {key}')
    return [float(n) for n in v]

def load_project(project_file):
    file=Path(project_file).resolve()
    doc=json.loads(file.read_text(encoding='utf8'))
    asset_base=file.parent
    if doc.get('embedded_assets'):
        import base64,zlib,hashlib,tempfile
        root=Path(tempfile.gettempdir())/'sg3d_embedded_assets'/hashlib.sha256(file.read_bytes()).hexdigest()[:32]
        root.mkdir(parents=True,exist_ok=True)
        total=0
        for name,blob in doc['embedded_assets'].items():
            rel=Path(name)
            if rel.is_absolute() or '..' in rel.parts or not rel.parts or rel.parts[0]!='assets':
                raise ValueError('Unsafe embedded asset path')
            packed=base64.b64decode(blob,validate=True)
            inflater=zlib.decompressobj()
            decoded=inflater.decompress(packed,min(32*1024*1024-total,16*1024*1024)+1)
            if not inflater.eof or inflater.unconsumed_tail or len(decoded)+total>32*1024*1024:
                raise ValueError('Embedded asset exceeds size limit or is incomplete')
            total+=len(decoded)
            dst=root/rel;dst.parent.mkdir(parents=True,exist_ok=True)
            dst.write_bytes(decoded)
        asset_base=root
    if 'scenes' in doc:
        if not isinstance(doc['scenes'],list) or not doc['scenes']:
            raise ValueError('scenes must contain at least one scene')
        i=int(doc.get('active_scene',0))
        if not 0<=i<len(doc['scenes']):raise ValueError('active_scene is out of range')
        doc.update({k:doc['scenes'][i].get(k,default) for k,default in
                    [('objects',[]),('camera',{'position':[0,0,0],'rotation':[0,0]}),
                     ('scripts',{'nodes':[],'links':[]}),('physics',{}),('animations',[]),('skybox',{})]})
    if not isinstance(doc.get('objects'),list):raise ValueError('project must have an objects array')
    return doc,asset_base

def export_project(project_file,outdir=None):
    project_file=Path(project_file).resolve();scene,base=load_project(project_file)
    if 'scenes' in scene:
        return export_multiscene(project_file,outdir,scene,base)
    # Don't accidentally compile stale scene_N files when exporting a legacy project.
    stale=Path(outdir).resolve() if outdir else Path(__file__).resolve().parents[1]/'generated'
    (stale/'sg3d_manifest.json').unlink(missing_ok=True)
    root=Path(__file__).resolve().parents[1]
    outdir=Path(outdir).resolve() if outdir else root/'generated'
    outdir.mkdir(parents=True,exist_ok=True)
    from custom_scripts import validate_components, copy_sources, generate_bindings
    custom_files=validate_components(scene['objects'],base)
    custom_source_files=copy_sources(custom_files,outdir)
    object_data=[];unique_meshes={};textures={};warnings=[]
    for n,obj in enumerate(scene['objects']):
        mesh_name=obj.get('mesh')
        mesh_path=resolve(base,mesh_name) if mesh_name else None
        if mesh_path and mesh_path not in unique_meshes:unique_meshes[mesh_path]=parse_obj(mesh_path)
        mesh=unique_meshes[mesh_path] if mesh_path else {'materials':[],'mtl':{},'vertices':[],'faces':[]}
        mode=str(obj.get('mode','texture')).lower()
        if mode not in MODES:raise ValueError(f'object {n}: unknown mode {mode}')
        override=obj.get('texture','')
        override=resolve(base,override) if override else None
        matdefs=[]
        for matname in mesh['materials']:
            info=mesh['mtl'].get(matname,{})
            texpath=override or (Path(info['texture']) if info.get('texture') else None)
            if texpath and not texpath.is_file():
                warnings.append(f'Missing PNG {texpath}; using flat color');texpath=None
            if texpath and texpath not in textures:textures[texpath]=make_texture(texpath)
            effective=MODES[mode]
            if not texpath and effective in (1,2,3,4):effective=0
            matdefs.append((texpath,material_rgb(info.get('diffuse',(.85,.85,.85))),effective))
        object_data.append({'mesh':mesh_path,'mats':matdefs,'obj':obj,'name':sym(obj.get('name',f'object_{n}'))})
    if not object_data:raise ValueError('Add at least one object before exporting')
    asset=[]
    asset+=['/* Generated by tools/project_export.py. Do not edit manually. */',
            '#ifndef SG3D_GENERATED_ASSETS_H','#define SG3D_GENERATED_ASSETS_H',
            '#include "sg3d.h"']
    mesh_syms={p:f'world_mesh_{n}' for n,p in enumerate(unique_meshes)}
    # A shared mesh can have per-object material/texture overrides. Bake a flat
    # texture only if all users of that mesh agree on the texture and mode.
    solid_by_mesh={}
    for path,mesh in unique_meshes.items():
        users=[obj['mats'] for obj in object_data if obj['mesh']==path]
        flat_faces={};tiny_faces={}
        for fi,(corners,material_index) in enumerate(mesh['faces']):
            variants={(u[material_index][0],u[material_index][2]) for u in users}
            if len(variants)!=1:continue
            texpath,mode=next(iter(variants))
            if mode!=1 or texpath not in textures:continue
            flat=solid_texture_triangle(corners,textures[texpath])
            if flat is not None:flat_faces[fi]=flat
            else:
                color=tiny_triangle_color(corners,textures[texpath])
                if color is not None:tiny_faces[fi]=color
        solid_by_mesh[path]=(flat_faces,tiny_faces)
    for path,mesh in unique_meshes.items():
        ident=mesh_syms[path]
        vs=[]
        for vert in mesh['vertices']:
            scaled=[round(c*256) for c in vert]
            if any(v<-32768 or v>32767 for v in scaled):raise ValueError(f'{path}: coordinates exceed 8.8 short range; scale OBJ before export')
            vs.append('{'+','.join(map(str,scaled))+'}')
        asset.append(array_decl('SG3DVertex',ident+'_v',vs,2))
        fs=[]
        for face_i,(corners,mi) in enumerate(mesh['faces']):
            ids=[v for v,uv in corners]
            uvs=[]
            for v,uv in corners:
                u=int(round(uv[0]*512));vv=int(round((1-uv[1])*512))
                if not (-32768<=u<=32767 and -32768<=vv<=32767):
                    raise ValueError(f'{path}: UV values too large')
                uvs.append(f'SG3D_UV({u},{vv})')
            baked=solid_by_mesh[path][0].get(face_i)
            tiny=solid_by_mesh[path][1].get(face_i)
            flag=('SG3D_FACE_SOLID_TEX' if baked is not None else
                  'SG3D_FACE_TINY_TEX' if tiny is not None else '0')
            fs.append('{'+','.join(map(str,ids))+f',{mi},{flag},{{'+','.join(uvs)+
                      f'}},{baked if baked is not None else 0},{tiny if tiny is not None else 0}'+'}')
        asset.append(array_decl('SG3DFace',ident+'_f',fs,1))
        bx,by,bz,br=conservative_bounds(mesh['vertices'])
        asset.append(f'static const SG3DMesh {ident} = {{ {ident}_v,{len(vs)},{ident}_f,{len(fs)}, {bx},{by},{bz},{br} }};')
    tex_syms={p:f'scene_texture_{i}' for i,p in enumerate(textures)}
    for path,mip in textures.items():
        ident=tex_syms[path]
        asset.append(array_decl('uint8_t',ident+'_0',mip[0]))
        asset.append(array_decl('uint8_t',ident+'_1',mip[1]))
        asset.append(f'static SG3DTexture {ident};')
    for i,info in enumerate(object_data):
        if info['mats']:asset.append(f'static SG3DMaterial scene_materials_{i}[{len(info["mats"])}];')
    asset.append('static void scene_assets_init(void){')
    asset.append('    sg3d_palette_rgb332();')
    asset.append('    sg3d_effects_rgb332_init();')
    for path in textures:
        ident=tex_syms[path]
        asset.append(f'    sg3d_texture_init(&{ident},{ident}_0,{ident}_1);')
    for i,info in enumerate(object_data):
        for mi,(path,color,mode) in enumerate(info['mats']):
            asset.append(f'    scene_materials_{i}[{mi}] = (SG3DMaterial){{'+(f'&{tex_syms[path]}' if path else '0')+f',{color},{mode}'+'};')
    asset.append('}')
    asset.append('#endif')
    sky=scene.get('skybox') or {}
    if sky.get('file'):
        from PIL import Image
        img=Image.open(resolve(base,sky['file'])).convert('RGB').resize((256,128),Image.Resampling.NEAREST)
        pixels=[rgb332(*c) for c in (img.get_flattened_data() if hasattr(img,'get_flattened_data') else img.getdata())]
        asset.append(array_decl('uint8_t','sg3d_skybox_pixels',pixels,per=32))
    (outdir/'scene_assets.h').write_text('\n'.join(asset)+'\n',encoding='utf8')
    sounds=sound_manifest(scene,base)
    (outdir/'audio_assets.h').write_text(emit_c_header(sounds),encoding='utf8')
    from hud_assets import hud_emit
    hud_code,hud_count=hud_emit(scene,base)
    animation_c,clips=emit_c(scene)
    declarations, start_commands, update_commands, collision_commands = compile_graph(scene,with_physics=True)
    custom_decls,custom_init,custom_start,custom_update,custom_collisions=generate_bindings(scene['objects'])
    has_custom_scripts=bool(custom_files)
    has_script_context=bool(custom_decls)
    has_scripts=bool((scene.get('scripts') or {}).get('nodes')) or has_custom_scripts
    main=['/* SG3D Studio v0.11 animation + PCM + visual scripting */',
          '#include <stdint.h>', '#include "sg3d_script.h"', '#include "sg3d.h"', '#include "sg3d_physics.h"', '#include "sg3d_audio.h"', '#include "sg3d_hud.h"', '#include "sg3d_facing.h"', '#include "sg3d_controls.h"', '#include "sin_table.h"', '#include "audio_assets.h"', '#include "scene_assets.h"',
          '/* Signed 8.8 operations; avoid libgcc division routines on bare GBA. */',
          'static inline int32_t sg3d_clamp_fx(int32_t v,int32_t lo,int32_t hi){return v<lo?lo:v>hi?hi:v;}',
          'static inline int sg3d_near_objects(const SG3DTransform *a,const SG3DTransform *b,int32_t radius){',
          '  if(radius<0)return 0;',
          '  int32_t rr=radius>>4;if(rr>2048)rr=2048;',
          '  int32_t dx=(a->x-b->x)>>4,dy=(a->y-b->y)>>4,dz=(a->z-b->z)>>4;',
          '  if(dx>rr||dx< -rr||dy>rr||dy< -rr||dz>rr||dz< -rr)return 0;',
          '  return dx*dx+dy*dy+dz*dz<=rr*rr;}',
          'static inline int32_t sg3d_fxmul(int32_t a,int32_t b){return (int32_t)(((int64_t)a*b)>>8);}',
          'static int32_t sg3d_fxdiv(int32_t a,int32_t b){',
          '  if(!b)return 0;',
          '  uint32_t u=a<0?(~(uint32_t)a+1):(uint32_t)a;',
          '  uint32_t v=b<0?(~(uint32_t)b+1):(uint32_t)b;',
          '  uint32_t q=0,r=0;',
          '  for(int i=31;i>=0;i--){',
          '    uint32_t carry=r>>31;r=(r<<1)|((u>>i)&1);',
          '    if(carry||r>=v){r-=v;q|=1u<<i;}',
          '  }',
          '  uint32_t frac=0;',
          '  for(int i=7;i>=0;i--){',
          '    uint32_t carry=r>>31;r<<=1;',
          '    if(carry||r>=v){r-=v;frac|=1u<<i;}',
          '  }',
          '  if(q>8388607u)return (a<0)!=(b<0)?(-2147483647-1):2147483647;',
          '  uint32_t result=(q<<8)|frac;',
          '  if(result>2147483647u)return (a<0)!=(b<0)?(-2147483647-1):2147483647;',
          '  return (a<0)!=(b<0)?-(int32_t)result:(int32_t)result;',
          '}',
          '#define REG_KEYS (*(volatile uint16_t *)0x04000130)',
          '#define A 1u', '#define B 2u', '#define SEL 4u', '#define START 8u',
          '#define RIGHT 16u', '#define LEFT 32u', '#define UP 64u', '#define DOWN 128u',
          '#define R 256u', '#define L 512u',
          'typedef struct {const SG3DMesh *mesh; SG3DMaterial *mats; unsigned nmat; SG3DTransform transform;} SceneObject;',
          'static SceneObject scene_objects[] = {']
    for i,info in enumerate(object_data):
        obj=info['obj'];pos=vec_float(obj,'position',[0,0,6]);rot=vec_float(obj,'rotation',[0,0]);scale=float(obj.get('scale',1.))
        if scale<=0 or scale>255:raise ValueError('scale must be between 0 and 255')
        x,y,z=[round(v*256) for v in pos];yaw,pitch=[round(v*256/360)&255 for v in rot]
        scal=int(max(1,min(65535,round(scale*256))))
        mesh_ref='&'+mesh_syms[info['mesh']] if info['mesh'] else '0'
        mats_ref=f'scene_materials_{i}' if info['mats'] else '0'
        main.append(f'  {{{mesh_ref},{mats_ref},{len(info["mats"])},'+f'{{{x},{y},{z},{yaw},{pitch},{scal}}}'+'},')
    main+=['};','enum { SCENE_COUNT = sizeof(scene_objects)/sizeof(scene_objects[0]) };',
           'static SG3DFacing facing_states[] = {']
    for info in object_data:
        obj=info['obj']
        smooth=float(obj.get('facing_smooth',0.25))
        offset=float(obj.get('facing_offset',0))
        if not (0 < smooth <= 1) or not math.isfinite(smooth):
            raise ValueError('facing_smooth must be in (0,1]')
        if not math.isfinite(offset):raise ValueError('facing_offset must be finite')
        main.append(f'  {{0,0,{1 if obj.get("face_movement",False) else 0},'
                    f'{min(255,max(1,round(smooth*255)))},{round(offset*256/360)&255},0,0}},')
    main+=['};','static SG3DPhysicsBody physics_bodies[] = {']
    for i,info in enumerate(object_data):
        obj=info['obj'];settings=obj.get('physics') or {}
        dynamic=1 if settings.get('dynamic',False) else 0
        solid=1 if settings.get('solid',False) else 0
        mesh=unique_meshes[info['mesh']] if info['mesh'] else {'vertices':[]}
        scale=float(obj.get('scale',1))
        if 'half_extents' in settings:
            extents=vec_float(settings,'half_extents',[1,1,1])
        else:
            # Axis-aligned bounds: local mesh extents multiplied by object scale.
            vs=mesh['vertices']
            extents=[max(0.125,(max(v[j] for v in vs)-min(v[j] for v in vs))*0.5*scale) for j in range(3)] if vs else [0.5,0.5,0.5]
        if any(v<=0 or v>256 for v in extents):raise ValueError('physics half_extents must be between 0 and 256')
        half=[max(1,round(v*256)) for v in extents]
        main.append(f'  {{&scene_objects[{i}].transform,{half[0]},{half[1]},{half[2]},0,0,0,{dynamic},{solid},0}},')
    main+=['};','static SG3DVehicle vehicle_states[SCENE_COUNT];','static uint8_t collision_previous[SCENE_COUNT][SCENE_COUNT];',hud_code,animation_c]+declarations+custom_decls
    main+=['int main(void){','    sg3d_init(); sg3d_audio_init(); scene_assets_init(); sg3d_anim_reset();',
           '    sg3d_set_skybox('+('sg3d_skybox_pixels' if (scene.get('skybox') or {}).get('file') else '0')+');', 
           f'    sg3d_hud_load(scene_hud,{hud_count});',
           f'    sg3d_hud_profiler({1 if scene.get("settings",{}).get("profiler",False) else 0});']
    cam=scene.get('camera',{})
    cp=vec_float(cam,'position',[0,0,0]);cr=vec_float(cam,'rotation',[0,0])
    main.append('    SG3DCamera cam={'+','.join(str(round(a*256)) for a in cp)+','+','.join(str(round(a*256/360)&255) for a in cr)+'};')
    orbit=cam.get('orbit') or {}
    if orbit.get('enabled',False):
        target=int(orbit.get('target',cam.get('follow',0)))
        if not 0<=target<len(object_data):raise ValueError('camera.orbit.target outside scene')
        radius=float(orbit.get('distance',6));height=float(orbit.get('height',1.5))
        turn=float(orbit.get('turn_speed',2))
        if not .5<=radius<=64 or not -32<=height<=32 or not 0<turn<=20:
            raise ValueError('Orbit distance/height/turn_speed out of range')
        yaw=round(float(cam.get('rotation',[0,0])[0])*256/360)&255
        pitch=round(float(orbit.get('pitch',-10))*256/360)
        if not -52<=pitch<=52:raise ValueError('Orbit pitch must be within about +/-73 degrees')
        main.append(f'    uint8_t orbit_yaw={yaw};int8_t orbit_pitch={pitch};')
    main+=['    unsigned keys=0,prev=0; unsigned spin=0; int auto_spin=0;']
    if has_script_context:
        main += ['    '+x for x in custom_init]
        main += ['    '+x for x in custom_start]
    if start_commands:
        main+=['    /* OnStart graph */']+['    '+line for line in start_commands]
    main+=['    for(;;){','        keys=(~REG_KEYS)&1023;',
           '        for(unsigned i=0;i<SCENE_COUNT;i++) sg3d_facing_capture(&facing_states[i], &scene_objects[i].transform);']
    if orbit.get('enabled',False):
        # Camera rotation must be current BEFORE OnUpdate/OnKeyHeld movement.
        # Follow target placement still happens after physics later in frame.
        if orbit.get('sync_yaw',False):
            main.append(f'        orbit_yaw=scene_objects[{target}].transform.yaw;')
            main.append(f'        sg3d_orbit_input(keys,&orbit_yaw,&orbit_pitch,0);')
        else:
            main.append(f'        sg3d_orbit_input(keys,&orbit_yaw,&orbit_pitch,{max(1,round(turn*256/360))});')
        # GBA view pitch uses the opposite sign to orbit elevation.
        main.append('        cam.yaw=orbit_yaw;cam.pitch=(uint8_t)(-orbit_pitch);')
    if has_script_context:
        main+=['        script_context.held=(uint16_t)keys;',
               '        script_context.pressed=(uint16_t)(keys & ~prev);']
        main+=['        '+x for x in custom_update]
    if has_scripts:
        main+=['        /* Compiled visual-script OnUpdate and button events */']
        main+=['        '+line for line in update_commands]
    elif not orbit.get('enabled',False):
        # v0.7 projects remain interactive without adding scripts.
        main+=['        if((keys&START)&&!(prev&START))auto_spin=!auto_spin;',
               '        if((keys&SEL)&&!(prev&SEL)){cam.x=cam.y=cam.z=0;cam.yaw=cam.pitch=0;}',
               '        if(keys&LEFT)cam.x-=16; if(keys&RIGHT)cam.x+=16;',
               '        if(keys&UP)cam.z+=16; if(keys&DOWN)cam.z-=16;',
               '        if(keys&L)cam.yaw-=2; if(keys&R)cam.yaw+=2;',
               '        if(keys&A)cam.y+=12; if(keys&B)cam.y-=12;']
    physics=scene.get('physics',{})
    grav=round(float(physics.get('gravity',-0.025))*256)
    terminal=round(float(physics.get('terminal_velocity',-0.7))*256)
    main += [f'        sg3d_physics_step(physics_bodies,SCENE_COUNT,{grav},{terminal});']
    if collision_commands:
        main += ['        /* Collision-begin events run AFTER physics. */']+['        '+line for line in collision_commands]
    if has_custom_scripts:
        main += ['        /* Native C collision callbacks (begin-contact only). */']
        main += ['        '+line for line in custom_collisions]
    main += ['        for(unsigned a=0;a<SCENE_COUNT;a++)',
             '            for(unsigned b=0;b<SCENE_COUNT;b++)',
             '                collision_previous[a][b]=(uint8_t)sg3d_physics_touching(physics_bodies,SCENE_COUNT,a,b);']
    follow=scene.get('camera',{}).get('follow')
    if follow is not None and not orbit.get('enabled',False):
        idx=int(follow)
        if idx<0 or idx>=len(object_data):raise ValueError('camera.follow refers to missing object')
        offset=vec_float(scene['camera'],'follow_offset',[0,2,-7])
        for axis,value in zip(('x','y','z'),offset):
            main.append(f'        cam.{axis} = scene_objects[{idx}].transform.{axis} + {round(value*256)};')
    if orbit.get('enabled',False):
        speed=round(float(orbit.get('move_speed',.09))*256)
        if not 1<=speed<=1024:raise ValueError('Orbit move_speed must be between 0.004 and 4')
        if orbit.get('auto_move',True) and not orbit_script_controls(scene) and not scene['objects'][target].get('c_scripts'):
            main+=['        int32_t input_x=0,input_z=0;',
                   '        if(!(keys&SEL)){',
                   f'            if(keys&LEFT)input_x-={speed};if(keys&RIGHT)input_x+={speed};',
                   f'            if(keys&UP)input_z+={speed};if(keys&DOWN)input_z-={speed};',
                   '        }',
                   f'        sg3d_move_relative(physics_bodies,SCENE_COUNT,{target},orbit_yaw,input_x,input_z);']
        if orbit.get('sync_yaw',False):main.append(f'        orbit_yaw=scene_objects[{target}].transform.yaw;')
        main.append(f'        sg3d_orbit_place(&cam,&scene_objects[{target}].transform,orbit_yaw,orbit_pitch,{round(radius*256)},{round(height*256)});')
    main+=['        sg3d_anim_step();',
           '        for(unsigned i=0;i<SCENE_COUNT;i++) sg3d_facing_update(&facing_states[i], &scene_objects[i].transform);', '        prev=keys;',
           '        if(auto_spin)spin++;',
           '        sg3d_set_camera(cam);sg3d_begin(1,5);',
           '        for(unsigned i=0;i<sizeof(scene_objects)/sizeof(scene_objects[0]);i++){',
           '            SceneObject *o=&scene_objects[i];',
           '            SG3DTransform t=o->transform;',
           '            if(auto_spin)t.yaw+=spin;',
           '            if(o->mesh)sg3d_draw_mesh(o->mesh,o->mats,o->nmat,t);',
           '        }',
           '        sg3d_end();sg3d_audio_tick();',
           '    }','}']
    (outdir/'main.c').write_text('\n'.join(main)+'\n',encoding='utf8')
    report={'objects':len(object_data),'mesh_assets':len(unique_meshes),
            'triangles':sum(len(m['faces']) for m in unique_meshes.values()),
            'textures':len(textures),'animations':len(clips),'sounds':len(sounds),'hud':hud_count,'script_nodes':len((scene.get('scripts') or {}).get('nodes',[])),
            'dynamic_bodies':sum(bool((obj.get('physics') or {}).get('dynamic')) for obj in scene['objects']), 'warnings':warnings,'main':str(outdir/'main.c'), 'user_sources':custom_source_files}
    if custom_source_files:
        (outdir/'sg3d_manifest.json').write_text(json.dumps({'scenes':0,'user_sources':custom_source_files},indent=2),encoding='utf8')
    (outdir/'sg3d_build_settings.json').write_text(json.dumps(scene.get('settings',{}),indent=2),encoding='utf8')
    (outdir/'export_report.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    return report

def export_multiscene(project_file,outdir,project,base):
    """Compile every scene into its own translation unit with separate objects.

    Scene functions share numeric globals, but geometry and physics are local to
    the scene. A single GBA ROM dispatches scene changes without a VM.
    """
    root=Path(__file__).resolve().parents[1]
    outdir=Path(outdir).resolve() if outdir else root/'generated'
    outdir.mkdir(parents=True,exist_ok=True)
    scenes=project['scenes']
    if not 1<=len(scenes)<=12:raise ValueError('Projects support 1 to 12 scenes')
    names=[str(s.get('name',f'Scene {i}')) for i,s in enumerate(scenes)]
    if len(set(names))!=len(names):raise ValueError('Scene names must be unique')
    # Ensure data is validated before writing the build manifest.
    result=[]
    user_sources=set()
    for i,scene in enumerate(scenes):
        if not isinstance(scene.get('objects'),list) or not scene['objects']:
            raise ValueError(f'Scene {names[i]} needs at least one object for export')
        # Existing single-scene export operates on relative asset references.
        # Resolve every scene's assets from the original project's directory.
        single={k:project[k] for k in ('variables','arrays','sounds','node_components') if k in project}
        single.update({k:scene.get(k,default) for k,default in (
            ('objects',[]),('camera',{}),('physics',{}),('scripts',{}),('animations',[]),('hud',[]),('skybox',{}))})
        single['settings']=project.get('settings',{})
        single['scene_names']=names
        single['objects']=[dict(obj) for obj in single['objects']]
        if (single.get('skybox') or {}).get('file'):
            single['skybox']={'file':str(resolve(base,single['skybox']['file']))}
        for sfx in single.get('sounds',[]):
            if sfx.get('file'):sfx['file']=str(resolve(base,sfx['file']))
        for item in single.get('hud',[]):
            if item.get('file'):item['file']=str(resolve(base,item['file']))
        for obj in single['objects']:
            for field in ('mesh','texture'):
                if obj.get(field):obj[field]=str(resolve(base,obj[field]))
            obj['c_scripts']=[str(resolve(base,p)) for p in obj.get('c_scripts',[])]
        with tempfile.TemporaryDirectory() as tmp:
            src=Path(tmp)/'scene.json'
            src.write_text(json.dumps(single),encoding='utf8')
            tmpout=Path(tmp)/'out'
            report=export_project(src,tmpout)
            for filename in report.get('user_sources',[]):
                data=(tmpout/filename).read_bytes()
                target=outdir/filename
                if filename in user_sources and target.read_bytes()!=data:
                    raise ValueError('Conflicting custom C script names across scenes: '+filename)
                target.write_bytes(data)
                user_sources.add(filename)
            header=(tmpout/'scene_assets.h').read_text(encoding='utf8')
            c=(tmpout/'main.c').read_text(encoding='utf8')
            audio_header=(tmpout/'audio_assets.h').read_text(encoding='utf8')
        hname=f'scene_assets_{i}.h'
        (outdir/hname).write_text(header,encoding='utf8')
        c=c.replace('#include "scene_assets.h"',f'#include "{hname}"')
        (outdir/'audio_assets.h').write_text(audio_header,encoding='utf8')
        c=c.replace('int main(void){',f'int sg3d_run_scene_{i}(void){{')
        c=c.replace('sg3d_init(); sg3d_audio_init(); scene_assets_init();','scene_assets_init();')
        # The scene switch is requested by visual LoadScene actions.
        c=c.replace('        prev=keys;',
                    '        if(sg3d_requested_scene >= 0) return sg3d_requested_scene;\n        prev=keys;')
        # Share user variables instead of resetting them when loading a level.
        c=re.sub(r'^static int32_t (sga_\w+)\[\] = \{[\d,\-]+\};$', r'extern int32_t \1[];', c, flags=re.MULTILINE)
        c=re.sub(r'^static int32_t (sgv_\w+) = [-\d]+; /\* fixed 8\.8 \*/$',
                 r'extern int32_t \1;',c,flags=re.MULTILINE)
        # Re-entering a scene starts its transforms and physics fresh.
        c=c.replace('static SG3DPhysicsBody physics_bodies[] = {',
                    'static SG3DPhysicsBody physics_bodies[] = {')
        c=c.replace('static uint8_t collision_previous[SCENE_COUNT][SCENE_COUNT];',
                    """static uint8_t collision_previous[SCENE_COUNT][SCENE_COUNT];
static SceneObject initial_objects[SCENE_COUNT];
static SG3DPhysicsBody initial_bodies[SCENE_COUNT];
static int snapshot_ready;""")
        c=c.replace('scene_assets_init();', """scene_assets_init();
    if(!snapshot_ready){
        for(unsigned i=0;i<SCENE_COUNT;i++){
            initial_objects[i]=scene_objects[i];initial_bodies[i]=physics_bodies[i];
        }
        snapshot_ready=1;
    }
    for(unsigned i=0;i<SCENE_COUNT;i++){
        scene_objects[i]=initial_objects[i];physics_bodies[i]=initial_bodies[i];vehicle_states[i].speed=0;
        for(unsigned j=0;j<SCENE_COUNT;j++)collision_previous[i][j]=0;
    }""",1)
        c=c.replace('    sg3d_anim_reset();', '    sg3d_anim_reset();')
        c=c.replace('#define REG_KEYS', 'extern volatile int sg3d_requested_scene;\n#define REG_KEYS')
        c=c.replace('script_context=(SG3DScriptContext){script_actors,SCENE_COUNT,&cam,0,0,0};', 'script_context=(SG3DScriptContext){script_actors,SCENE_COUNT,&cam,0,0,&sg3d_requested_scene};')
        (outdir/f'scene_{i}.c').write_text(c,encoding='utf8')
        result.append(report)
    # Build a tiny dispatcher. Scene functions return after a switch request.
    defs,_,_=compile_graph({'variables':project.get('variables',{}),'arrays':project.get('arrays',{}),'objects':[]})
    main=['#include <stdint.h>','#include "sg3d.h"','#include "sg3d_audio.h"',
          'volatile int sg3d_requested_scene = -1;']
    main.extend(line.replace('static int32_t','int32_t',1) for line in defs)
    main.extend(f'int sg3d_run_scene_{i}(void);' for i in range(len(scenes)))
    entry=int(project.get('initial_scene',0))
    if not 0<=entry<len(scenes):raise ValueError('initial_scene is outside scene list')
    main.extend(['int main(void){','  sg3d_init();sg3d_audio_init();',f'  int scene={entry};','  for(;;){',
                 '    sg3d_requested_scene=-1;','    switch(scene){'])
    main.extend(f'    case {i}: scene=sg3d_run_scene_{i}(); break;' for i in range(len(scenes)))
    main.extend(['    default: scene=0; break;','    }','  }','}'])
    (outdir/'main.c').write_text('\n'.join(main)+'\n',encoding='utf8')
    (outdir/'sg3d_manifest.json').write_text(json.dumps({'scenes':len(scenes),'user_sources':sorted(user_sources)},indent=2),encoding='utf8')
    summary={'scenes':len(scenes),'objects':sum(r['objects'] for r in result),
             'triangles':sum(r['triangles'] for r in result),
             'textures':sum(r['textures'] for r in result),
             'script_nodes':sum(r['script_nodes'] for r in result),
             'animations':sum(r['animations'] for r in result), 'sounds':len(project.get('sounds',[])), 'hud':sum(r['hud'] for r in result),
             'warnings':[x for r in result for x in r['warnings']], 'user_sources':sorted(user_sources)}
    (outdir/'sg3d_build_settings.json').write_text(json.dumps(project.get('settings',{}),indent=2),encoding='utf8')
    (outdir/'export_report.json').write_text(json.dumps(summary,indent=2),encoding='utf8')
    return summary

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('project',type=Path)
    ap.add_argument('--outdir',type=Path)
    a=ap.parse_args()
    print(json.dumps(export_project(a.project,a.outdir),indent=2))

if __name__=='__main__':main()
