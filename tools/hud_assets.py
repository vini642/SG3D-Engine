"""Compile low-res HUD items to ROM-backed GBA pixel overlays."""
from pathlib import Path
from project_export import resolve, rgb332, sym

KINDS={'text':'SG3D_HUD_TEXT','bar':'SG3D_HUD_BAR','rect':'SG3D_HUD_RECT',
       'sprite':'SG3D_HUD_SPRITE','dialogue':'SG3D_HUD_DIALOGUE'}

def hud_emit(scene,base):
    items=scene.get('hud',[])
    if not isinstance(items,list) or len(items)>16:raise ValueError('HUD supports at most 16 elements')
    out=['/* HUD coordinates are legacy 120x80; native GBA OBJ text and PNG are 240x160. */']
    rows=[]
    for i,o in enumerate(items):
        typ=o.get('type','text')
        if typ not in KINDS:raise ValueError(f'HUD {i}: invalid type {typ}')
        x,y=int(o.get('x',2)),int(o.get('y',2));w,h=int(o.get('w',50)),int(o.get('h',7))
        if not (-120<=x<=120 and -80<=y<=80 and 1<=w<=120 and 1<=h<=80):raise ValueError(f'HUD {i}: dimensions out of range')
        fg=int(o.get('fg',255));bg=int(o.get('bg',0));value=int(o.get('value',0));maximum=int(o.get('maximum',0))
        if not 0<=fg<=255 or not 0<=bg<=255 or not -32768<=value<=32767 or not 0<=maximum<=32767:raise ValueError(f'HUD {i}: color/value out of range')
        name=f'ui_sprite_{i}';image='0'
        if typ=='sprite':
            try:from PIL import Image
            except ImportError as exc:raise RuntimeError('Pillow required for HUD PNG import') from exc
            p=resolve(base,o.get('file',''))
            if not p.is_file():raise ValueError(f'HUD {i}: missing sprite PNG {p}')
            img=Image.open(p).convert('RGBA').resize((w*2,h*2),Image.Resampling.NEAREST)
            vals=[]
            for r,g,b,a in (img.get_flattened_data() if hasattr(img,"get_flattened_data") else img.getdata()):
                pix=rgb332(r,g,b)
                vals.append(0 if a<128 else max(1,pix))
            out.append(f'static const uint8_t {name}[{w*h*4}] = {{'+','.join(map(str,vals))+'};')
            image=name
        label=str(o.get('text','')).encode('ascii','replace').decode('ascii')[:27]
        label=label.replace('\\','\\\\').replace('"','\\"').replace('\n',' ')
        rows.append(f'  {{{KINDS[typ]},{x},{y},{w},{h},{fg},{bg},{1 if o.get("visible",True) else 0},{value},{maximum},"{label}",{image}}},')
    out.append('static const SG3DHUDItem scene_hud[] = {')
    if rows:out.extend(rows)
    else:out.append('  {0},')
    out.append('};')
    return '\n'.join(out),len(rows)
