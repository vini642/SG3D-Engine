"""PC-baked rigid transform animation clips. No interpolation/division on GBA.

Each key stores absolute position, rotation (degrees), and scale. Clips are
sampled offline to native SG3DTransform (8.8 position, 8-bit angle, 8.8 scale).
"""
import math

def validated_clips(scene):
    clips=scene.get('animations',[])
    if not isinstance(clips,list) or len(clips)>24:
        raise ValueError('animations must be a list with at most 24 clips')
    used=set();out=[]
    for ci,raw in enumerate(clips):
        name=str(raw.get('name','')).strip()
        if not name or name in used:raise ValueError('Animation names must be unique and nonempty')
        used.add(name)
        idx=int(raw.get('object',-1))
        objects=scene.get('objects',[])
        if not 0<=idx<len(objects):raise ValueError(f'Animation {name}: object index out of range')
        if (objects[idx].get('physics') or {}).get('dynamic'):
            raise ValueError(f'Animation {name}: cannot drive a dynamic physics object (disable Dynamic)')
        duration=int(raw.get('duration',60))
        if not 2<=duration<=240:raise ValueError('Animation duration must be 2..240 frames')
        keys=raw.get('keys',[])
        if not isinstance(keys,list) or len(keys)<2 or len(keys)>32:
            raise ValueError(f'Animation {name}: requires 2..32 keyframes')
        prev=-1;normalized=[]
        for k in keys:
            f=int(k.get('frame',-1))
            if f<=prev or f>=duration:raise ValueError(f'Animation {name}: keys must have increasing frames < duration')
            prev=f
            values={}
            for attr,num in [('position',3),('rotation',2)]:
                v=k.get(attr)
                if not isinstance(v,list) or len(v)!=num or not all(math.isfinite(float(n)) for n in v):
                    raise ValueError(f'Animation {name}: invalid {attr}')
                values[attr]=[float(n) for n in v]
            scale=float(k.get('scale',1))
            if not math.isfinite(scale) or scale<=0 or scale>255:raise ValueError(f'Animation {name}: scale must be positive')
            normalized.append({'frame':f,**values,'scale':scale})
        if normalized[0]['frame']!=0:raise ValueError(f'Animation {name}: first key must be frame 0')
        out.append({'name':name,'object':idx,'duration':duration,'keys':normalized,
                    'loop':bool(raw.get('loop',True)),'autoplay':bool(raw.get('autoplay',False))})
    return out

def pose_at(clip, frame):
    """Keyframe lerp; shorter-path wrap for rotations."""
    keys=clip['keys'];frame=max(0,min(int(frame),clip['duration']-1))
    left=keys[0];right=keys[-1]
    for i in range(len(keys)-1):
        if keys[i]['frame']<=frame<=keys[i+1]['frame']:
            left,right=keys[i],keys[i+1];break
    if frame>=keys[-1]['frame']:left=right=keys[-1]
    t=0.0 if left['frame']==right['frame'] else (frame-left['frame'])/(right['frame']-left['frame'])
    position=[a+(b-a)*t for a,b in zip(left['position'],right['position'])]
    rotation=[]
    for a,b in zip(left['rotation'],right['rotation']):
        delta=(b-a+180)%360-180
        rotation.append((a+delta*t)%360)
    return {'position':position,'rotation':rotation,'scale':left['scale']+(right['scale']-left['scale'])*t}

def bake(clip):
    frames=[]
    for frame in range(clip['duration']):
        p=pose_at(clip,frame)
        coords=[round(x*256) for x in p['position']]
        if any(x<-(1<<31) or x>=(1<<31) for x in coords):raise ValueError('Animation position exceeds signed 32-bit range')
        angles=[round(x*256/360)&255 for x in p['rotation']]
        scale=round(p['scale']*256)
        if scale<1 or scale>65535:raise ValueError('Animation scale exceeds 8.8 transform range')
        frames.append((*coords,*angles,scale))
    return frames

def emit_c(scene):
    clips=validated_clips(scene)
    parts=['/* v0.11 pre-baked rigid animations. Data stays in ROM. */',
           'typedef struct {const SG3DTransform *frames; unsigned count, object, loop, autoplay;} SG3DAnimClip;']
    for idx,clip in enumerate(clips):
        frames=bake(clip)
        parts.append(f'static const SG3DTransform sg3d_anim_frames_{idx}[] = {{')
        parts.extend('    {'+','.join(map(str,frame))+'},' for frame in frames)
        parts.append('};')
    parts.append('static const SG3DAnimClip sg3d_clips[] = {')
    parts.extend(f'  {{sg3d_anim_frames_{i},{c["duration"]},{c["object"]},{int(c["loop"])},{int(c["autoplay"])}}},' for i,c in enumerate(clips))
    # Zero-length array is not portable C11; use a harmless dummy when empty.
    if not clips:parts.append('  {0,0,0,0,0},')
    parts.extend(['};',f'enum {{ SG3D_ANIM_COUNT = {len(clips)} }};',
         f'static unsigned char sg3d_anim_running[{max(1,len(clips))}];',
         f'static unsigned short sg3d_anim_cursor[{max(1,len(clips))}];',
         'static void sg3d_anim_play(unsigned clip){',
         '  if(clip>=SG3D_ANIM_COUNT)return;',
         '  sg3d_anim_cursor[clip]=0;sg3d_anim_running[clip]=1;',
         '}',
         'static void sg3d_anim_stop(unsigned clip){',
         '  if(clip<SG3D_ANIM_COUNT)sg3d_anim_running[clip]=0;',
         '}',
         'static void sg3d_anim_reset(void){',
         '  for(unsigned i=0;i<SG3D_ANIM_COUNT;i++){',
         '    sg3d_anim_cursor[i]=0;sg3d_anim_running[i]=sg3d_clips[i].autoplay;',
         '  }',
         '}',
         'static void sg3d_anim_step(void){',
         '  for(unsigned i=0;i<SG3D_ANIM_COUNT;i++){',
         '    if(!sg3d_anim_running[i])continue;',
         '    const SG3DAnimClip *c=&sg3d_clips[i];',
         '    scene_objects[c->object].transform=c->frames[sg3d_anim_cursor[i]];',
         '    if(++sg3d_anim_cursor[i]>=c->count){',
         '      if(c->loop)sg3d_anim_cursor[i]=0;',
         '      else {sg3d_anim_cursor[i]=c->count-1;sg3d_anim_running[i]=0;}',
         '    }',
         '  }',
         '}',])
    return '\n'.join(parts),clips
