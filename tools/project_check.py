#!/usr/bin/env python3
"""Basic SG3D project preflight: validation and actionable warnings, without building."""
import argparse
from pathlib import Path
import math
from project_export import load_project, resolve, parse_obj


def check_project(file=None, *, document=None, base=None):
    if document is None:
        document, base=load_project(file)
    base=Path(base).resolve()
    issues=[]
    def issue(level,location,message):issues.append((level,location,message))
    scenes=document.get('scenes',[document]);names=[]
    if not scenes:
        issue('ERROR','project','No scenes')
        return issues
    for index,scene in enumerate(scenes):
        label=f'Scene {index+1}: {scene.get("name", "untitled")}'
        names.append(scene.get('name',''))
        objects=scene.get('objects',[])
        if not objects:issue('ERROR',label,'No objects; the exporter requires at least one mesh')
        num_tri=0
        for i,obj in enumerate(objects):
            where=f'{label} / Object {i+1} ({obj.get("name", "unnamed")})'
            src=obj.get('mesh')
            if not src:
                # Invisible logic objects are valid and have no mesh asset.
                continue
            path=resolve(base,src)
            if not path.is_file():
                issue('ERROR',where,f'OBJ not found: {path}');continue
            try:
                mesh=parse_obj(path)
                num_tri+=len(mesh['faces'])
                for material in mesh['mtl'].values():
                    tex=material.get('texture')
                    if tex and not Path(tex).is_file():issue('WARN',where,f'Material texture missing: {tex}')
            except (ValueError,OSError) as e:
                issue('ERROR',where,f'Invalid OBJ: {e}')
            if obj.get('texture') and not resolve(base,obj['texture']).is_file():
                issue('WARN',where,'Override texture missing; exporter will use a flat color')
            try:
                values=list(obj.get('position',[0,0,0]))+list(obj.get('rotation',[0,0]))+[obj.get('scale',1)]
                if not all(math.isfinite(float(v)) for v in values):issue('ERROR',where,'Transform contains NaN or Infinity')
            except (ValueError,TypeError):issue('ERROR',where,'Invalid numeric transform')
        from custom_scripts import validate_components
        try:validate_components(objects,base)
        except (ValueError,OSError) as e:issue('ERROR',label,'Custom scripts: '+str(e))
        sky=(scene.get('skybox') or {}).get('file')
        if sky and not resolve(base,sky).is_file():issue('ERROR',label,f'Skybox PNG missing: {sky}')
        orbit=(scene.get('camera') or {}).get('orbit') or {}
        if orbit.get('enabled',False):
            try:
                target=int(orbit.get('target',0))
                if target<0 or target>=len(objects):issue('ERROR',label,'Orbit target is not a valid object index')
                if not .5<=float(orbit.get('distance',6))<=64:issue('ERROR',label,'Orbit distance must be 0.5 to 64')
            except (TypeError,ValueError):issue('ERROR',label,'Orbit camera has invalid settings')
        if num_tri>384:
            issue('WARN',label,f'{num_tri} source triangles; GBA draw queue is limited to 384 visible triangles per frame. Cull/split meshes if needed')
        for i,item in enumerate(scene.get('hud',[])):
            if item.get('file') and not resolve(base,item['file']).is_file():
                issue('ERROR',f'{label} / HUD {i}',f'Sprite missing: {item["file"]}')
    if len(set(names))!=len(names):issue('ERROR','project','Scene names must be unique')
    for index,sfx in enumerate(document.get('sounds',[])):
        if sfx.get('file') and not resolve(base,sfx['file']).is_file():
            issue('ERROR',f'Sound {index+1}',f'WAV not found: {sfx["file"]}')
    return issues


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('project');args=ap.parse_args()
    issues=check_project(args.project)
    if not issues:print('Project check: OK')
    for level,location,msg in issues:print(f'{level}: {location}: {msg}')
    raise SystemExit(1 if any(level=='ERROR' for level,_,_ in issues) else 0)

if __name__=='__main__':main()
