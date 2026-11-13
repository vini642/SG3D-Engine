"""Convert mono/stereo PCM WAV to small, signed 8-bit, 8192 Hz GBA SFX.

Pure Python converter, supports 8/16-bit PCM. Deliberately rejects compressed
sound files. A 1-KiB zero guard prevents DMA reading past the last sample while
it is stopped at the next frame boundary.
"""
import math, wave
from pathlib import Path
RATE=8192
MAX_SECONDS=2.0

def convert_wav(path):
    with wave.open(str(path),'rb') as f:
        channels,sw,rate,frames=f.getnchannels(),f.getsampwidth(),f.getframerate(),f.getnframes()
        if f.getcomptype()!='NONE' or channels not in (1,2) or sw not in (1,2) or rate<=0:
            raise ValueError('Audio must be PCM WAV, mono/stereo, 8/16-bit')
        if frames==0:raise ValueError('Empty WAV file')
        if frames/rate>MAX_SECONDS:raise ValueError('WAV too long; maximum 2 seconds per effect')
        raw=f.readframes(frames)
    samples=[]
    for n in range(frames):
        v=0
        for c in range(channels):
            i=(n*channels+c)*sw
            if sw==1:v+=(raw[i]-128)*256
            else:v+=int.from_bytes(raw[i:i+2],'little',signed=True)
        samples.append(v/channels)
    n_out=max(1,round(frames*RATE/rate))
    result=[]
    for i in range(n_out):
        at=i*rate/RATE
        j=min(int(at),max(0,frames-1));k=min(j+1,max(0,frames-1))
        t=min(1,at-j)
        amp=samples[j]*(1-t)+samples[k]*t
        result.append(max(-128,min(127,round(amp/256))))
    return result

def sound_manifest(doc,base):
    sounds=doc.get('sounds',[])
    if not isinstance(sounds,list) or len(sounds)>32:raise ValueError('sounds must be a list of 0..32 files')
    names=set();out=[]
    for index,s in enumerate(sounds):
        name=str(s.get('name','')).strip()
        if not name or name in names:raise ValueError('Sound names must be unique and nonempty')
        names.add(name)
        path=Path(s.get('file',''))
        path=(path if path.is_absolute() else Path(base)/path).resolve()
        if not path.is_file():raise ValueError(f'Sound {name} does not exist: {path}')
        samples=convert_wav(path)
        out.append((name,samples))
    return out

def emit_c_header(sounds):
    lines=['/* SG3D Studio audio: signed PCM + 1024 zero guard samples for DMA. */',
           '#ifndef SG3D_AUDIO_ASSETS_H','#define SG3D_AUDIO_ASSETS_H',
           '#include <stdint.h>']
    for i,(_,samples) in enumerate(sounds):
        full=samples+[0]*1024
        full += [0]*((-len(full))%4)
        lines.append(f'static const int8_t sg3d_sound_{i}[{len(full)}] __attribute__((aligned(4))) = {{')
        for j in range(0,len(full),24):lines.append('  '+','.join(str(v) for v in full[j:j+24])+',')
        lines.append('};')
        lines.append(f'#define SG3D_SOUND_{i}_LENGTH {len(samples)}u')
    lines.append('#endif')
    return '\n'.join(lines)+'\n'
