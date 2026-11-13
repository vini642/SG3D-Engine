#!/usr/bin/env python3
"""Package a SG3D project (including referenced OBJ, MTL, PNG, WAV) into a portable ZIP.

Usage: python tools/project_pack.py examples/collectathon_v12.sg3d.json -o build/Collectathon_Project.zip
The archived project is editable: it is NOT a compiled GBA ROM.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
import re
import tempfile
import zipfile

from project_export import load_project, parse_obj, resolve


def package_project(source, destination, *, document=None, source_base=None):
    source = Path(source).resolve() if source is not None else None
    if document is None:
        if source is None:
            raise ValueError('source project path is required when document is omitted')
        document, base = load_project(source)
    else:
        document=copy.deepcopy(document)
        base=Path(source_base).resolve() if source_base else (source.parent if source else Path.cwd())
    destination=Path(destination).resolve()
    project=copy.deepcopy(document)
    project.pop('embedded_assets',None)
    project.pop('embedded_format',None)
    assets={}
    payload={}
    scanned_meshes=set()
    scanned_materials=set()

    def asset(path, label):
        original=resolve(base,path)
        if not original.is_file():
            raise FileNotFoundError(f'{label}: missing asset {original}')
        if original in assets:return assets[original]
        safe=re.sub(r'[^A-Za-z0-9_.-]+','_',original.name)[:76]
        if label=='User C script':
            name=f'assets/scripts/{safe}'
            if name in payload:
                raise ValueError(f'Custom C script name collision: {safe}; use unique script filenames')
        else:
            name=f'assets/{len(assets)+1:04d}_{safe}'
        assets[original]=name
        payload[name]=original.read_bytes()
        return name

    def scan_mtl(file):
        original=resolve(base,file)
        target=asset(str(original),'MTL')
        if original in scanned_materials:return target
        scanned_materials.add(original)
        data=payload[target].decode('utf-8-sig',errors='replace').splitlines(keepends=True)
        out=[]
        for line in data:
            m=re.match(r'^(\s*map_Kd\s+)([^#\r\n]+?)(\s*(?:#.*)?\r?\n?)$',line)
            if m:
                texname=m.group(2).strip()
                if texname.startswith('-'):
                    raise ValueError(f'{original}: advanced map_Kd options are unsupported in portable packaging')
                tex=asset(str(resolve(original.parent,texname)),'MTL texture')
                line=f'{m.group(1)}{Path(tex).name}{m.group(3)}'
            out.append(line)
        payload[target]=''.join(out).encode('utf-8')
        return target

    def scan_obj(file):
        original=resolve(base,file)
        target=asset(str(original),'OBJ mesh')
        if original in scanned_meshes:return target
        scanned_meshes.add(original)
        # Check OBJ constraints before packaging: avoids delivering a broken game project.
        parse_obj(original)
        lines=payload[target].decode('utf-8-sig',errors='replace').splitlines(keepends=True)
        out=[]
        for line in lines:
            m=re.match(r'^(\s*mtllib\s+)([^#\r\n]+?)(\s*(?:#.*)?\r?\n?)$',line)
            if m:
                lib=scan_mtl(resolve(original.parent,m.group(2).strip()))
                line=f'{m.group(1)}{Path(lib).name}{m.group(3)}'
            out.append(line)
        payload[target]=''.join(out).encode('utf-8')
        return target

    def scan_scene(scene):
        if (scene.get('skybox') or {}).get('file'):
            scene['skybox']['file']=asset(scene['skybox']['file'],'Skybox PNG')
        for i,obj in enumerate(scene.get('objects',[])):
            obj['c_scripts']=[asset(script,'User C script') for script in obj.get('c_scripts',[])]
            if obj.get('mesh'):
                obj['mesh']=scan_obj(obj['mesh'])
            # No mesh means a valid logic-only / invisible scene object.
            if obj.get('texture'):
                obj['texture']=asset(obj['texture'],'Override texture')
        for item in scene.get('hud',[]):
            if item.get('file'):
                item['file']=asset(item['file'],'HUD sprite')

    if 'scenes' in project:
        for scene in project['scenes']:
            scan_scene(scene)
        active=int(project.get('active_scene',0))
        for k in ('objects','scripts','camera','physics','animations','hud','skybox'):
            if k in project['scenes'][active]:
                project[k]=copy.deepcopy(project['scenes'][active][k])
    else:
        scan_scene(project)
    for sfx in project.get('sounds',[]):
        if sfx.get('file'):
            sfx['file']=asset(sfx['file'],'Sound WAV')

    name=re.sub(r'[^A-Za-z0-9_-]+','_',project.get('name','SG3D_Project')).strip('_')[:60] or 'SG3D_Project'
    root_name=f'{name}.sg3d.json'
    payload[root_name]=(json.dumps(project,indent=2,ensure_ascii=False,allow_nan=False)+'\n').encode('utf-8')
    payload['HOW_TO_OPEN.txt']=(
        'SG3D Studio portable project\n\n'
        f'Open {root_name} using SG3D Studio 1.0.\n'
        'All referenced model, material, texture, sound and custom C files are in assets/.\n'
        'This is an editable project, not a ROM. Use Export GBA to build a ROM.\n'
    ).encode('utf-8')
    destination.parent.mkdir(parents=True,exist_ok=True)
    # Validate the package before replacing an existing file.
    with tempfile.TemporaryDirectory() as temp:
        work=Path(temp)
        for name,data in payload.items():
            p=work/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
        loaded,package_base=load_project(work/root_name)
        for scene in loaded.get('scenes',[loaded]):
            for obj in scene['objects']:
                if obj.get('mesh'):
                    mesh=parse_obj(resolve(package_base,obj['mesh']))
                    for material in mesh['mtl'].values():
                        if material.get('texture') and not Path(material['texture']).is_file():
                            raise FileNotFoundError(f'Packaged texture is missing: {material["texture"]}')
        for sc in loaded.get('scenes',[loaded]):
            for obj in sc['objects']:
                if obj.get('texture') and not resolve(package_base,obj['texture']).is_file():
                    raise FileNotFoundError('Packaged override texture missing')
        with tempfile.NamedTemporaryFile(dir=destination.parent,suffix='.zip',delete=False) as fp:
            tmp=Path(fp.name)
        try:
            with zipfile.ZipFile(tmp,'w',zipfile.ZIP_DEFLATED) as archive:
                for rel,data in sorted(payload.items()):
                    archive.writestr(rel,data)
            os.replace(tmp,destination)
        finally:
            tmp.unlink(missing_ok=True)
    return {'path':destination,'files':len(payload),'project':root_name,'assets':len(assets)}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('project')
    ap.add_argument('-o','--output',required=True)
    args=ap.parse_args()
    result=package_project(args.project,args.output)
    print(f'Portable project: {result["path"]} ({result["assets"]} assets)')

if __name__=='__main__':main()

def make_embedded_document(document,source_base):
    """Bundle a whole project into one JSON document (zlib compressed base64).

    Reuses portable packaging so OBJ and MTL relative paths get rewritten safely.
    """
    import base64,zlib
    with tempfile.TemporaryDirectory() as tmp:
        archive=Path(tmp)/'packed.zip'
        result=package_project(None,archive,document=document,source_base=source_base)
        with zipfile.ZipFile(archive) as z:
            project=json.loads(z.read(result['project']))
            project['embedded_assets']={
                name:base64.b64encode(zlib.compress(z.read(name),9)).decode('ascii')
                for name in z.namelist() if name.startswith('assets/')
            }
            project['embedded_format']=1
            return project


def save_embedded_document(document,source_base,destination):
    data=make_embedded_document(document,source_base)
    destination=Path(destination).resolve()
    destination.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile('w',encoding='utf-8',dir=destination.parent,
                                     prefix='.sg3d_',suffix='.tmp',delete=False) as out:
        temporary=Path(out.name)
        json.dump(data,out,indent=2,ensure_ascii=False,allow_nan=False)
    try:os.replace(temporary,destination)
    finally:temporary.unlink(missing_ok=True)
    return data
