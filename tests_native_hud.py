"""Pre-release HUD fixes: packed Mode 4 VRAM, OBJ layout, exporter and preview."""
import json, os, shutil, subprocess, sys, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'editor')]
from hud_assets import hud_emit
from gba_preview import render_scene

class NativeHUDTests(unittest.TestCase):
    def test_native_png_pixel_count_is_four_times_legacy(self):
        d=json.loads((ROOT/'examples/collectathon_v12.sg3d.json').read_text())
        code,n=hud_emit(d['scenes'][0],ROOT/'examples')
        self.assertEqual(n,4)
        self.assertIn('ui_sprite_2[576]',code)  # 12x12 HUD -> 24x24 OBJ

    def test_preview_text_is_true_native_resolution(self):
        p=ROOT/'examples/collectathon_v12.sg3d.json'
        scene=json.loads(p.read_text())['scenes'][0]
        with_ui,_=render_scene(scene,p.parent)
        scene['hud']=[]
        without_ui,_=render_scene(scene,p.parent)
        self.assertEqual(with_ui.size,(240,160))
        self.assertNotEqual(with_ui.getpixel((7,20)),without_ui.getpixel((7,20)))
        # Some neighboring native pixels must differ: text isn't horizontal-pixel-doubled.
        found=any(with_ui.getpixel((x,y))!=with_ui.getpixel((x+1,y))
                  for y in range(20,34) for x in range(6,45,2))
        self.assertTrue(found)

    def test_native_hud_register_math_and_low_res_rmw(self):
        cc=shutil.which('cc') or shutil.which('gcc') or shutil.which('clang')
        if not cc:self.skipTest('No native compiler')
        code=r'''
#include <stdint.h>
#include "engine/sg3d_hud.c"
int main(void){
    uint16_t fb[121];for(unsigned i=0;i<121;i++)fb[i]=0x1234;
    canvas=fb;
    pix(0,0,0x56);
    if(fb[0]!=0x1256)return 1;  /* only low byte */
    pix(1,0,0x78);
    if(fb[0]!=0x7856)return 2;  /* only high byte */
    pix(2,0,0xab);
    if(fb[1]!=0x12ab)return 3;
    hud_tile_count=0;hud_sprite_count=0;hud_dropped=0;
    int tile=obj_alloc(1,4,9,0,0);
    if(tile!=0 || hud_oam_shadow[2]!=512 || hud_oam_shadow[0]!=(0x2000|9))return 4;
    tile=obj_alloc(4,17,23,0,1);
    if(tile!=1 || hud_oam_shadow[6]!=514 || hud_oam_shadow[5]!=(17|(1<<14)))return 5;
    hud_tile_count=255;
    if(obj_alloc(4,0,0,0,1)!=-1 || hud_dropped!=1)return 6;
    return 0;
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            src=Path(tmp)/'test.c';exe=Path(tmp)/'test'
            src.write_text(code)
            subprocess.run([cc,'-std=c11','-O2','-I'+str(ROOT),str(src),'-o',str(exe)],check=True,capture_output=True)
            subprocess.run([str(exe)],check=True,capture_output=True)

if __name__=='__main__':unittest.main()
