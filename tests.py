#!/usr/bin/env python3
"""Host-side checks: run `python tests.py`; `python build.py` checks ARM linking."""
from pathlib import Path
import importlib.util
import struct
import unittest

ROOT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('obj_converter',ROOT/'tools/obj_to_sg3d.py')
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class Tests(unittest.TestCase):
    def test_obj_is_convertible(self):
        original=(ROOT/'examples/pyramid.obj').read_text()
        code=module.convert(original,'pyramid',256)
        self.assertEqual(code,(ROOT/'demo/pyramid_mesh.h').read_text())
        self.assertIn('pyramid_vertices, 5, pyramid_faces, 6',code)
        self.assertIn('SG3D_UV(256,0)',code)
    def test_quad_and_negative_indices(self):
        obj='''v 0 0 0\nv 1 0 0\nv 1 1 0\nv 0 1 0\nf -4 -3 -2 -1\n'''
        code=module.convert(obj,'quad',256)
        self.assertIn('quad_vertices, 4, quad_faces, 2',code)
    def test_invalid_indices(self):
        with self.assertRaisesRegex(ValueError,'vertex index'):
            module.convert('v 0 0 0\nf 1 2 3','bad',256)
    def test_vertex_limit(self):
        huge='\n'.join(f'v {i} 0 0' for i in range(257))+'\nf '+' '.join(str(i+1) for i in range(257))
        with self.assertRaisesRegex(ValueError,'256'):
            module.convert(huge,'large',1)
    def test_compact_raster_lut(self):
        table=(ROOT/'engine/lut_delta.bin').read_bytes()
        self.assertEqual(len(table),8192)
        self.assertEqual(struct.unpack_from('<i',table,10*4)[0],32768)
        self.assertIn('lsl #2', (ROOT/'engine/raster_core.s').read_text())
        self.assertNotIn('engine_emit_stage:',(ROOT/'engine/raster_core.s').read_text())
    def test_gba_header_if_built(self):
        rom=ROOT/'build/SG3D_STANDALONE_v07.gba'
        if not rom.is_file():self.skipTest('Run python build.py to generate the ROM')
        raw=rom.read_bytes()
        self.assertEqual(raw[4:8],bytes.fromhex('24ffae51'))
        self.assertEqual(raw[0xA0:0xAC],b'SG3D NOVA V7')
        self.assertEqual((sum(raw[0xA0:0xBE])+0x19)&255,0)
        self.assertEqual(len(raw)%4,0)

if __name__=='__main__':unittest.main()
