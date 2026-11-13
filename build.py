#!/usr/bin/env python3
"""Build the independent, asset-free SMG-GBA derived 3D engine demo.
Usage: python build.py [--clean]
Searches devkitARM first (DEVKITARM env), falls back to Clang/LLD/llvm-objcopy.
"""
from pathlib import Path
import argparse
import os
import shutil
import struct
import subprocess

ROOT=Path(__file__).resolve().parent

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--clean',action='store_true')
    parser.add_argument('--main', default='demo/main.c', help='C entry point, e.g. generated/main.c')
    parser.add_argument('--output', help='Destination .gba ROM file (default: build/SG3D_v12_3_*.gba)')
    parser.add_argument('--hud-legacy', action='store_true', help='render all HUD content to low-res BG2; still uses correct packed VRAM writes for A/B testing')
    parser.add_argument('--perf-baseline', action='store_true', help='disable experimental fast clip and buckets')
    parser.add_argument('--perf-prev-pipeline', action='store_true', help='v0.12.2 fast clip + buckets, without the v0.12.3 changes')
    parser.add_argument('--perf-disable', choices=['object-cull','fused-transform','vertex-cache','solid-texture','tiny-flat'],
                        action='append', default=[], help='disable one optimization for FPS A/B comparisons; repeatable')
    a=parser.parse_args()
    build=ROOT/'build'
    if a.clean and build.exists():shutil.rmtree(build)
    build.mkdir(exist_ok=True)
    lut=(ROOT/'engine/lut_delta.bin').read_bytes()
    if len(lut)!=8192 or struct.unpack_from('<i',lut,10*4)[0]!=32768 or struct.unpack_from('<i',lut,100*4)[0]!=5242:
        raise SystemExit('Error: compact raster lookup table is missing or unexpected')
    toolchain=Path(os.environ.get('DEVKITARM','/opt/devkitpro/devkitARM'))/'bin'
    gcc=shutil.which(str(toolchain/'arm-none-eabi-gcc')) or shutil.which('arm-none-eabi-gcc')
    if gcc:
        compiler=[gcc]
        objcopy=shutil.which(str(toolchain/'arm-none-eabi-objcopy')) or shutil.which('arm-none-eabi-objcopy')
        arch=['-mcpu=arm7tdmi','-marm','-mthumb-interwork']
        ldextra=[]
    else:
        clang=shutil.which('clang')
        objcopy=shutil.which('llvm-objcopy')
        if not clang or not objcopy:raise SystemExit('Requires devkitARM or clang/lld + llvm-objcopy')
        compiler=[clang]
        arch=['--target=armv4t-none-eabi','-mcpu=arm7tdmi','-marm']
        ldextra=['-fuse-ld=lld']
    if not objcopy:raise SystemExit('Missing arm-none-eabi-objcopy / llvm-objcopy')
    perf_flags={
        'object-cull':'SG3D_PERF_OBJECT_CULL',
        'fused-transform':'SG3D_PERF_FUSED_TRANSFORM',
        'vertex-cache':'SG3D_PERF_VERTEX_CACHE',
        'solid-texture':'SG3D_PERF_SOLID_TEXTURE',
        'tiny-flat':'SG3D_PERF_TINY_FLAT',
    }
    sources=['engine/startup.s' ,'engine/sg3d.c','engine/raster_api.c',
             'engine/raster_core.s','engine/lut.s','engine/effects.c','engine/sg3d_physics.c','engine/sg3d_audio.c','engine/sg3d_hud.c','engine/sg3d_facing.c','engine/sg3d_controls.c','engine/sg3d_script.c',a.main]
    if a.main == 'generated/main.c' and (ROOT/'generated/sg3d_manifest.json').exists():
        import json
        manifest=json.loads((ROOT/'generated/sg3d_manifest.json').read_text())
        sources += [f'generated/scene_{i}.c' for i in range(manifest['scenes'])]
        sources += [f'generated/{file}' for file in manifest.get('user_sources',[])]
    objects=[]
    for src in sources:
        out=build/(str(len(objects))+'_'+Path(src).stem+'.o')
        flags=arch.copy()
        if src.endswith('.c'):
            flags+=['-ffreestanding','-fno-builtin','-ffunction-sections','-fdata-sections',
                    '-std=c11','-O2','-fno-strict-aliasing','-Wall','-Wextra',
                    '-Wno-misleading-indentation',f'-I{ROOT/"engine"}',f'-I{ROOT/"demo"}']
        if a.hud_legacy and src.endswith('.c'):
            flags.append('-DSG3D_HUD_NATIVE_UI=0')
        if a.perf_baseline and src.endswith('.c'):
            flags+=['-DSG3D_PERF_FAST_CLIP=0','-DSG3D_PERF_BUCKET_SORT=0']
        if src.endswith('.c'):
            for option,define in perf_flags.items():
                if a.perf_baseline or a.perf_prev_pipeline or option in a.perf_disable:
                    flags.append(f'-D{define}=0')
        cmd=compiler+flags+['-c',str(ROOT/src),'-o',str(out)]
        print('Compiling',src,flush=True)
        subprocess.run(cmd,check=True,cwd=ROOT)
        objects.append(str(out))
    elf=build/'sg3d.elf'
    suffix='BASELINE' if a.perf_baseline else ('PREVIOUS_12_2' if a.perf_prev_pipeline else ('NO_'+'_'.join(x.replace('-','_').upper() for x in a.perf_disable) if a.perf_disable else 'OPTIMIZED'))
    rom_path=Path(a.output).expanduser().resolve() if a.output else build/f'SG3D_v12_3_{suffix}.gba'
    if rom_path.suffix.lower()!='.gba':raise SystemExit('--output filename must end in .gba')
    rom_path.parent.mkdir(parents=True,exist_ok=True)
    subprocess.run(compiler+arch+ldextra+['-nostdlib','-Wl,-T,linker.ld',
                   '-Wl,--gc-sections',f'-Wl,-Map,{build/"sg3d.map"}']+objects+['-o',str(elf)],
                   check=True,cwd=ROOT)
    subprocess.run([objcopy,'-O','binary',str(elf),str(rom_path)],check=True)
    rom=bytearray(rom_path.read_bytes())
    logo=bytes.fromhex('''
24 FF AE 51 69 9A A2 21 3D 84 82 0A 84 E4 09 AD
11 24 8B 98 C0 81 7F 21 A3 52 BE 19 93 09 CE 20
10 46 4A 4A F8 27 31 EC 58 C7 E8 33 82 E3 CE BF
85 F4 DF 94 CE 4B 09 C1 94 56 8A C0 13 72 A7 FC
9F 84 4D 73 A3 CA 9A 61 58 97 A3 27 FC 03 98 76
23 1D C7 61 03 04 AE 56 BF 38 84 00 40 A7 0E FD
FF 52 FE 03 6F 95 30 F1 97 FB C0 85 60 D6 80 25
A9 63 BE 03 01 4E 38 E2 F9 A2 34 FF BB 3E 03 44
78 00 90 CB 88 11 3A 94 65 C0 7C 63 87 F0 3C AF
D6 25 E4 8B 38 0A AC 72 21 D4 F8 07
''')
    assert len(logo)==156 and len(rom)>=0xC0
    rom[4:0xA0]=logo
    settings={}
    if a.main == 'generated/main.c' and (ROOT/'generated/sg3d_build_settings.json').is_file():
        import json
        settings=json.loads((ROOT/'generated/sg3d_build_settings.json').read_text())
    title=str(settings.get('title','SG3D NOVA 12'))
    code=str(settings.get('code','SG12')).upper()
    maker=str(settings.get('maker','00')).upper()
    if not title.isascii() or len(title)>12 or not title:raise SystemExit('ROM title: 1 to 12 ASCII chars')
    if len(code)!=4 or not code.isascii() or not code.isalnum():raise SystemExit('ROM game code: exactly 4 ASCII letters/digits')
    if len(maker)!=2 or not maker.isascii() or not maker.isalnum():raise SystemExit('ROM maker code: 2 ASCII letters/digits')
    rom[0xA0:0xAC]=title.encode('ascii').ljust(12,b' ')
    rom[0xAC:0xB0]=code.encode('ascii')
    rom[0xB0:0xB2]=maker.encode('ascii')
    rom[0xB2]=0x96
    rom[0xB3:0xBD]=bytes(10)
    rom[0xBD]=(-sum(rom[0xA0:0xBD])-0x19)&255
    rom[0xBE:0xC0]=bytes(2)
    rom+=bytes((-len(rom))%4)
    assert (sum(rom[0xA0:0xBE])+0x19)&255==0
    rom_path.write_bytes(rom)
    print(f'Built {rom_path}: {len(rom):,} bytes (GBA header valid).')
    print('Compile/link validation passed. Runtime behavior still needs verification on a GBA emulator or hardware.')

if __name__=='__main__':main()
