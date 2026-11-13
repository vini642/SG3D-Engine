"""Regression: orbit and racing cameras must point at their follow target."""
import json
import math
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'editor')]
from project_export import export_project
from game_preview import PreviewGame
from visual_editor import view_transform

SAMPLE=ROOT/'examples/orbit_sky_demo.sg3d.json'

class CameraTargetTests(unittest.TestCase):
    def test_orbit_pitch_aims_at_target_pc(self):
        for yaw in (0,90,180,270):
            for pitch in (-45,-10,0,15,45):
                with self.subTest(yaw=yaw,pitch=pitch):
                    doc=json.loads(SAMPLE.read_text())
                    doc['camera']['rotation'][0]=yaw
                    doc['camera']['orbit']['pitch']=pitch
                    sim=PreviewGame(doc,SAMPLE.parent)
                    sim.tick([])
                    obj=sim.doc['objects'][0]
                    h=float(doc['camera']['orbit']['height'])
                    focal=[obj['position'][0],obj['position'][1]+h,obj['position'][2]]
                    x,y,z=view_transform(focal,sim.doc['camera'])
                    self.assertGreater(z,0.1)
                    self.assertAlmostEqual(x,0,delta=0.03)
                    self.assertAlmostEqual(y,0,delta=0.06)

    def test_pitch_buttons_keep_camera_on_target(self):
        doc=json.loads(SAMPLE.read_text())
        sim=PreviewGame(doc,SAMPLE.parent)
        for keys in (['SELECT','UP'],['SELECT','UP'],['SELECT','DOWN'],['L'],['R']):
            sim.tick(keys)
            obj=sim.doc['objects'][0]
            h=doc['camera']['orbit']['height']
            x,y,z=view_transform([obj['position'][0],obj['position'][1]+h,obj['position'][2]],sim.doc['camera'])
            self.assertAlmostEqual(y,0,delta=0.07)
            self.assertAlmostEqual(x,0,delta=0.07)
            self.assertGreater(z,0.1)

    def test_racing_camera_tracks_target(self):
        doc=json.loads((ROOT/'examples/racing_controller_demo.sg3d.json').read_text())
        sim=PreviewGame(doc,ROOT/'examples')
        for keys in (['UP','LEFT'],['UP','LEFT'],['UP','RIGHT'],['UP']):
            sim.tick(keys)
            i=int(doc['camera']['orbit']['target'])
            obj=sim.doc['objects'][i]
            h=doc['camera']['orbit']['height']
            x,y,z=view_transform([obj['position'][0],obj['position'][1]+h,obj['position'][2]],sim.doc['camera'])
            self.assertAlmostEqual(y,0,delta=0.1)
            self.assertAlmostEqual(x,0,delta=0.1)

    def test_export_uses_inverted_view_pitch(self):
        with tempfile.TemporaryDirectory() as tmp:
            export_project(SAMPLE,Path(tmp))
            src=(Path(tmp)/'main.c').read_text()
            self.assertIn('cam.pitch=(uint8_t)(-orbit_pitch)',src)
            self.assertIn('sg3d_orbit_place(',src)

    def test_legacy_non_orbit_camera_unchanged(self):
        doc=json.loads(SAMPLE.read_text())
        doc['camera']['orbit']['enabled']=False
        doc['camera']['rotation'][1]=-10
        sim=PreviewGame(doc,SAMPLE.parent)
        self.assertEqual(sim.doc['camera']['rotation'][1],-10)

if __name__=='__main__':unittest.main()
