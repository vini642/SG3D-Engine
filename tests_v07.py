#!/usr/bin/env python3
"""v0.7 offline regression tests: converter, RGB332, generated ABI, header, GUI imports."""
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools'))
from project_export import parse_obj,export_project,make_texture,rgb332,MODES

class V07Tests(unittest.TestCase):
    def test_all_assembly_render_modes_exposed(self):
        asm=(ROOT/'engine/raster_core.s').read_text()
        header=(ROOT/'engine/sg3d.h').read_text()
        for name,value in MODES.items():
            alias={'texture':'TEXTURED'}.get(name,name.upper())
            self.assertIn('SG3D_'+alias,header)
            self.assertIn('RM_'+{'texture':'TEX','additive':'ADD'}.get(name,name.upper()),asm)
            self.assertEqual(value,list(MODES.values())[value])

    def test_rgb332_extremes(self):
        self.assertEqual(rgb332(0,0,0),0)
        self.assertEqual(rgb332(255,255,255),255)
        self.assertEqual(rgb332(255,0,0),224)
        self.assertEqual(rgb332(0,255,0),28)
        self.assertEqual(rgb332(0,0,255),3)

    def test_materials_and_quads(self):
        mesh=parse_obj(ROOT/'examples/cube.obj')
        self.assertEqual(len(mesh['faces']),12)
        self.assertEqual(len(mesh['vertices']),8)
        self.assertIn('Checker',mesh['materials'])
        self.assertTrue(Path(mesh['mtl']['Checker']['texture']).is_file())

    def test_png_mips(self):
        tex=make_texture(ROOT/'examples/checker.png')
        self.assertEqual(len(tex[0]),1024)
        self.assertEqual(len(tex[1]),256)
        self.assertTrue(all(0<=v<=255 for mip in tex for v in mip))

    def test_scene_export_has_live_textures_modes_camera(self):
        with tempfile.TemporaryDirectory() as td:
            info=export_project(ROOT/'examples/demo_project.sg3d.json',td)
            self.assertEqual(info['objects'],3)
            self.assertEqual(info['triangles'],18)
            self.assertEqual(info['textures'],1)
            self.assertEqual(info['warnings'],[])
            code=(Path(td)/'scene_assets.h').read_text()
            main=(Path(td)/'main.c').read_text()
            self.assertIn('sg3d_effects_rgb332_init();',code)
            self.assertIn('scene_texture_0_0',code)
            self.assertIn('scene_texture_0_1',code)
            self.assertIn('sg3d_draw_mesh',main)
            self.assertIn('scene_materials_2[1]',code)
            self.assertIn('SG3DTransform',main)

    def test_rom_header(self):
        rom=ROOT/'build/SG3D_STANDALONE_v07.gba'
        if not rom.is_file():self.skipTest('build.py not run')
        b=rom.read_bytes()
        self.assertEqual(b[4:8],bytes.fromhex('24ffae51'))
        self.assertEqual(b[0xa0:0xac],b'SG3D NOVA V7')
        self.assertEqual((sum(b[0xa0:0xbe])+0x19)&255,0)

if __name__=='__main__':unittest.main(verbosity=2)
