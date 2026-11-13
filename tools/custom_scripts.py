"""Opt-in custom C components for SG3D. No genre-specific behaviors in the runtime.

Each asset <name>.c must export <name>_Start, <name>_Update,
<name>_Collision with signatures in sg3d_script.h. Files are compiled as
separate ARM translation units and linked with the normal node graph.
"""
from __future__ import annotations
import re
import shutil
from pathlib import Path
import math
from project_export import resolve

IDENT=re.compile(r'^[A-Za-z_][A-Za-z_0-9]*$')

def source_name(path):
    name=Path(path).stem
    if not IDENT.fullmatch(name):
        raise ValueError(f'C script filename must be a C identifier: {path}')
    return name

def validate_components(objects,base):
    files={}
    for i,obj in enumerate(objects):
        paths=obj.get('c_scripts',[])
        if not isinstance(paths,list) or len(paths)>8:
            raise ValueError(f'Object {i}: c_scripts must be a list of at most 8 files')
        if len(paths)!=len(set(paths)):
            raise ValueError(f'Object {i}: duplicate C script attachment')
        props=obj.get('properties',{})
        if not isinstance(props,dict) or len(props)>16:
            raise ValueError(f'Object {i}: properties must be an object with at most 16 entries')
        for k,v in props.items():
            if not IDENT.fullmatch(k):raise ValueError(f'Object {i}: invalid property name: {k!r}')
            try:fx=round(float(v)*256)
            except (ValueError,TypeError,OverflowError):raise ValueError(f'Object {i}: invalid property {k}')
            if not math.isfinite(float(v)) or not -(2**31)<=fx<2**31:raise ValueError(f'Object {i}: property {k} exceeds signed fixed-point range')
        for rel in paths:
            path=resolve(base,rel)
            if path.suffix.lower()!='.c' or not path.is_file():
                raise ValueError(f'Object {i}: missing .c script: {path}')
            name=source_name(path)
            if name in files and files[name]!=path:
                raise ValueError(f'C script collision: two scripts are named {name}.c')
            code=path.read_text(encoding='utf-8-sig')
            for callback in ('Start','Update','Collision'):
                if not re.search(r'\b'+re.escape(name)+'_'+callback+r'\s*\(',code):
                    raise ValueError(f'{path.name}: missing {name}_{callback}(...) callback')
            files[name]=path
    return files

def copy_sources(files,outdir):
    outdir=Path(outdir)
    results=[]
    for name,path in sorted(files.items()):
        dest=outdir/f'user_{name}.c'
        # Only C files, no arbitrary external compiler options or special flags.
        shutil.copyfile(path,dest)
        results.append(dest.name)
    return results

def generate_bindings(objects):
    """Return global declarations and callbacks, ready for the generated main.c.

    Context points to the existing contiguous physics_bodies array, and each
    component has a per-object fixed-point property map, shared by node/C code.
    """
    lines=[]
    scripts=[[] for _ in objects]
    if not any(obj.get("c_scripts") or obj.get("properties") for obj in objects):return [],[],[],[],[]
    for i,obj in enumerate(objects):
        props=obj.get('properties',{})
        if props:
            entries=','.join(f'{{"{k}",{round(float(v)*256)}}}' for k,v in props.items())
            lines.append(f'static SG3DProperty script_properties_{i}[]={{ {entries} }};')
        scripts[i]=[source_name(s) for s in obj.get('c_scripts',[])]
    lines.append('static SG3DScriptActor script_actors[SCENE_COUNT];')
    lines.append('static SG3DScriptContext script_context;')
    for script in sorted({s for group in scripts for s in group}):
        for suffix,args in [('Start','SG3DScriptContext *,unsigned'),('Update','SG3DScriptContext *,unsigned'),('Collision','SG3DScriptContext *,unsigned,unsigned')]:
            lines.append(f'void {script}_{suffix}({args});')
    initialize=['script_context=(SG3DScriptContext){script_actors,SCENE_COUNT,&cam,0,0,0};']
    for i,obj in enumerate(objects):
        n=len(obj.get('properties',{}))
        ptr=f'script_properties_{i}' if n else '0'
        initialize.append(f'script_actors[{i}]=(SG3DScriptActor){{&scene_objects[{i}].transform,&physics_bodies[{i}],{ptr},{n}}};')
        for j,(name,value) in enumerate(obj.get('properties',{}).items()):
            initialize.append(f'script_properties_{i}[{j}].value={round(float(value)*256)};')
    start=[f'{s}_Start(&script_context,{i});' for i,group in enumerate(scripts) for s in group]
    update=[f'{s}_Update(&script_context,{i});' for i,group in enumerate(scripts) for s in group]
    collisions=[]
    for i,group in enumerate(scripts):
        if group:
            collisions.append(f'for(unsigned other=0;other<SCENE_COUNT;other++) if(other!={i} && !collision_previous[{i}][other] && sg3d_physics_touching(physics_bodies,SCENE_COUNT,{i},other)){{')
            collisions += [f'  {s}_Collision(&script_context,{i},other);' for s in group]
            collisions.append('}')
    return lines,initialize,start,update,collisions


def starter(name):
    if not IDENT.fullmatch(name):raise ValueError('Script name must be a C identifier')
    return f'''#include "sg3d_script.h"
/* Attached to any scene object, not tied to a particular game genre.
   256 fixed units = 1 world unit; 256 angle units = 360 degrees.
   Add numeric properties to the object in the editor. */
void {name}_Start(SG3DScriptContext *ctx,unsigned self){{
    (void)ctx;(void)self;
}}
void {name}_Update(SG3DScriptContext *ctx,unsigned self){{
    /* Example: move with arrow keys in camera space, collision-aware.
    int32_t dx=(sg3d_key_held(ctx,SG3D_KEY_RIGHT)?12:0)-(sg3d_key_held(ctx,SG3D_KEY_LEFT)?12:0);
    int32_t dz=(sg3d_key_held(ctx,SG3D_KEY_UP)?12:0)-(sg3d_key_held(ctx,SG3D_KEY_DOWN)?12:0);
    sg3d_move_camera_space(ctx,self,dx,dz); */
    (void)ctx;(void)self;
}}
void {name}_Collision(SG3DScriptContext *ctx,unsigned self,unsigned other){{
    (void)ctx;(void)self;(void)other;
}}
'''
