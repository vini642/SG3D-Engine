#!/usr/bin/env python3
"""Convert ordinary triangulated/quad Wavefront OBJ into a standalone SG3D C mesh.
Requires only Python 3. No original game or asset extractor required.

Usage: python tools/obj_to_sg3d.py examples/pyramid.obj demo/pyramid_mesh.h --name pyramid
"""
import argparse
import math
import re
from pathlib import Path


def symbol(s):
    s=re.sub(r'\W+','_',s).strip('_')
    if not s or s[0].isdigit():s='mesh_'+s
    return s


def convert(source, name, scale):
    verts=[]; texcoords=[]; faces=[]; unique={}; output_verts=[]
    for line_no,line in enumerate(source.splitlines(),1):
        parts=line.partition('#')[0].strip().split()
        if not parts:continue
        try:
            if parts[0]=='v':
                verts.append(tuple(float(x) for x in parts[1:4]))
            elif parts[0]=='vt':
                texcoords.append(tuple(float(x) for x in parts[1:3]))
            elif parts[0]=='f':
                poly=[]
                for item in parts[1:]:
                    fields=item.split('/')
                    vi=int(fields[0]);vi=vi-1 if vi>0 else len(verts)+vi
                    if not 0<=vi<len(verts):raise ValueError('vertex index out of bounds')
                    # Build output vertex list by POSITION (UVs live per face, so seams are fine).
                    if vi not in unique:
                        unique[vi]=len(output_verts)
                        output_verts.append(verts[vi])
                    uv=(0.0,0.0)
                    if len(fields)>1 and fields[1]:
                        ti=int(fields[1]);ti=ti-1 if ti>0 else len(texcoords)+ti
                        if not 0<=ti<len(texcoords):raise ValueError('texture index out of bounds')
                        uv=texcoords[ti]
                    poly.append((unique[vi],uv))
                if len(poly)<3:raise ValueError('face with fewer than 3 points')
                for i in range(1,len(poly)-1):
                    faces.append((poly[0],poly[i],poly[i+1]))
        except (IndexError,ValueError) as error:
            raise ValueError(f'OBJ line {line_no}: {error}') from error
    if not output_verts or not faces:raise ValueError('OBJ contains no polygon mesh')
    if len(output_verts)>256:raise ValueError('more than 256 vertices; split mesh into smaller objects')
    if len(faces)>65535:raise ValueError('more than 65535 faces')
    nm=symbol(name)
    h=['/* Generated from OBJ by tools/obj_to_sg3d.py. Edit the OBJ instead. */',
       f'#ifndef SG3D_{nm.upper()}_H',f'#define SG3D_{nm.upper()}_H',
       '#include "sg3d.h"',f'static const SG3DVertex {nm}_vertices[] = {{']
    for x,y,z in output_verts:
        vs=[int(round(n*scale)) for n in (x,y,z)]
        if any(not -32768<=v<=32767 for v in vs):
            raise ValueError('coordinate exceeds signed 16 bit range; use lower --scale')
        h.append('    {'+ ', '.join(map(str,vs))+'},')
    h.extend(['};',f'static const SG3DFace {nm}_faces[] = {{'])
    for poly in faces:
        indices=[v for v,uv in poly]
        uvs=[]
        for _,(u,v) in poly:
            # 16 UV units per texel * 32 texels = 512 per texture repeat.
            U=int(round(u*512));V=int(round((1-v)*512))
            uvs.append(f'SG3D_UV({U},{V})')
        h.append('    {'+', '.join(map(str,indices))+', 0, 0, {'+', '.join(uvs)+'}},')
    h.extend(['};',f'static const SG3DMesh {nm}_mesh = {{',
              f'    {nm}_vertices, {len(output_verts)}, {nm}_faces, {len(faces)}',
              '};', '#endif', ''])
    return '\n'.join(h)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('obj',type=Path)
    ap.add_argument('output',type=Path)
    ap.add_argument('--name',default=None)
    ap.add_argument('--scale',type=float,default=256.0,help='8.8 fixed units per OBJ unit (default 256)')
    a=ap.parse_args()
    code=convert(a.obj.read_text(encoding='utf8'),a.name or a.obj.stem,a.scale)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(code,encoding='utf8')
    print('Converted',a.obj,'->',a.output)
if __name__=='__main__':main()
