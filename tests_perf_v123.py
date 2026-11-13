"""v0.12.3 conservative bounds and static texture replacement tests."""
import json,sys,tempfile,unittest,math
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools'))
from project_export import conservative_bounds,solid_texture_triangle,export_project,make_texture

class PerfTests(unittest.TestCase):
    def test_bounds_enclose_vertices(self):
        v=[(-2.4,-1,0.6),(4.1,1.8,3.5),(0,0,-5)]
        x,y,z,r=conservative_bounds(v)
        for vx,vy,vz in v:
            d=sum((int(round(a*256))-b)**2 for a,b in zip((vx,vy,vz),(x,y,z)))
            self.assertLessEqual(d,r*r)
    def test_large_bounds_disable_culling(self):
        self.assertGreater(conservative_bounds([(-128,-128,-128),(127,127,127)])[3],50000)
    def test_uniform_color_baking_and_checker_preservation(self):
        pts=[(0,(0.1,0.1)),(1,(0.3,0.1)),(2,(0.1,0.3))]
        self.assertEqual(solid_texture_triangle(pts,[[88]*1024,[88]*256]),88)
        self.assertIsNone(solid_texture_triangle(pts,[[88]*1024,[90]*256]))
        self.assertIsNone(solid_texture_triangle([(0,(0.2,0.1)),(1,(0.8,0.1)),(2,(0.2,0.8))],[[88 if x<16 else 90 for y in range(32) for x in range(32)],[88]*256]))
    def test_project_export_bounds_and_solid(self):
        with tempfile.TemporaryDirectory() as tmp:
            b=Path(tmp)
            (b/'box.obj').write_text('mtllib box.mtl\nv -1 0 0\nv 1 0 0\nv 0 1 0\nvt 0 0\nvt 1 0\nvt 0 1\nusemtl color\nf 1/1 2/2 3/3\n')
            (b/'box.mtl').write_text('newmtl color\nmap_Kd red.png\n')
            Image.new('RGB',(32,32),(255,0,0)).save(b/'red.png')
            obj={'objects':[{'mesh':'box.obj','name':'red','position':[0,0,6],'rotation':[0,0],'scale':1,'mode':'texture'}],
                 'camera':{'position':[0,0,0],'rotation':[0,0]},'scripts':{'nodes':[],'links':[]}}
            (b/'p.sg3d.json').write_text(json.dumps(obj))
            export_project(b/'p.sg3d.json',b/'export')
            h=(b/'export'/'scene_assets.h').read_text()
            self.assertIn('SG3D_FACE_SOLID_TEX',h)
            self.assertRegex(h,r'world_mesh_0 = \{ world_mesh_0_v,3,world_mesh_0_f,1, .+\};')
            # Shared mesh with per-instance different texture must not bake.
            Image.new('RGB',(32,32),(0,255,0)).save(b/'green.png')
            obj['objects'].append({'mesh':'box.obj','name':'green','position':[4,0,6],'rotation':[0,0],'scale':1,
                                   'mode':'texture','texture':'green.png'})
            (b/'p.sg3d.json').write_text(json.dumps(obj))
            export_project(b/'p.sg3d.json',b/'export')
            self.assertNotIn('SG3D_FACE_SOLID_TEX',(b/'export'/'scene_assets.h').read_text())

if __name__=='__main__':unittest.main()
