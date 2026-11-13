"""Feature-completion regression tests: orbit, racing, skybox, packed projects."""
import json
import tempfile
import unittest
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'editor')]
from project_export import load_project,export_project
from project_pack import save_embedded_document,package_project
from project_check import check_project
from node_scripts import compile_graph
from game_preview import PreviewGame
from gba_preview import render_scene

class FeatureTests(unittest.TestCase):
    def test_orbit_walk_and_follow(self):
        source=ROOT/'examples/orbit_sky_demo.sg3d.json';doc,base=load_project(source)
        sim=PreviewGame(doc,base)
        before=sim.doc['objects'][0]['position'][:]
        sim.tick(['UP'])
        after=sim.doc['objects'][0]['position']
        self.assertGreater(after[2],before[2])
        c0=sim.doc['camera']['position'][:]
        sim.tick(['R'])
        self.assertNotEqual(sim.doc['camera']['position'],c0)
    def test_racing_controller_and_checkpoint(self):
        source=ROOT/'examples/racing_controller_demo.sg3d.json';doc,base=load_project(source)
        self.assertEqual([],check_project(source))
        sim=PreviewGame(doc,base)
        sim.tick(['UP','RIGHT'])
        self.assertGreater(sim.vehicle_speeds[0],0)
        self.assertNotEqual(sim.doc['objects'][0]['rotation'][0],0)
    def test_compiled_orbit_and_skybox(self):
        source=ROOT/'examples/orbit_sky_demo.sg3d.json'
        with tempfile.TemporaryDirectory() as tmp:
            export_project(source,Path(tmp))
            main=(Path(tmp)/'main.c').read_text()
            h=(Path(tmp)/'scene_assets.h').read_text()
            self.assertIn('sg3d_orbit_input(',main)
            self.assertIn('sg3d_orbit_place(',main)
            self.assertIn('sg3d_move_relative(',main)
            self.assertIn('sg3d_set_skybox(sg3d_skybox_pixels)',main)
            self.assertIn('static const uint8_t sg3d_skybox_pixels',h)
    def test_compiled_racing_actions(self):
        source=ROOT/'examples/racing_controller_demo.sg3d.json';doc,base=load_project(source)
        _,_,cmds,collisions=compile_graph(doc,with_physics=True)
        joined='\n'.join(cmds)
        self.assertIn('sg3d_drive_vehicle',joined)
        self.assertIn('sg3d_physics_touching', '\n'.join(collisions))
        # Additional proximity branch supports checkpoint distance tests.
        doc['scripts']={'nodes':[
            {'id':'e','type':'OnUpdate','params':{}},
            {'id':'near','type':'IfNearObject','params':{'object':'0','other':'2','radius':'2'}},
            {'id':'a','type':'AddVariable','params':{'variable':'laps','value':'1'}}],
            'links':[{'from':'e','to':'near','port':'next'}, {'from':'near','to':'a','port':'true'}]}
        _,_,conditional,_=compile_graph(doc,with_physics=True)
        self.assertIn('sg3d_near_objects','\n'.join(conditional))
    def test_skybox_preview_moves(self):
        doc,base=load_project(ROOT/'examples/orbit_sky_demo.sg3d.json')
        doc['objects']=[]
        a,_=render_scene(doc,base)
        doc['camera']['rotation'][0]=105
        b,_=render_scene(doc,base)
        self.assertNotEqual(a.tobytes(),b.tobytes())
    def test_self_contained_roundtrip_and_export(self):
        source=ROOT/'examples/orbit_sky_demo.sg3d.json';doc,base=load_project(source)
        with tempfile.TemporaryDirectory() as tmp:
            packed=Path(tmp)/'selfcontained.sg3d.json'
            save_embedded_document(doc,base,packed)
            before=packed.read_bytes()
            loaded,root=load_project(packed)
            self.assertTrue(loaded['embedded_assets'])
            self.assertTrue((root/loaded['skybox']['file']).is_file())
            self.assertEqual([],check_project(packed))
            export_project(packed,Path(tmp)/'out')
            loaded['name']='Changed title'
            edited=Path(tmp)/'edited.sg3d.json'
            save_embedded_document(loaded,root,edited)
            opened,_=load_project(edited)
            self.assertEqual('Changed title',opened['name'])
            self.assertEqual([],check_project(edited))
            archive=Path(tmp)/'traditional.zip'
            self.assertGreater(package_project(edited,archive)['assets'],0)
    def test_missing_skybox_reported(self):
        source=ROOT/'examples/orbit_sky_demo.sg3d.json';doc,base=load_project(source)
        doc['skybox']['file']='this_file_does_not_exist.png'
        self.assertTrue(any('Skybox PNG missing' in message for _,_,message in check_project(document=doc,base=base)))

if __name__=='__main__':unittest.main()

class FeatureGUIFidelityTests(unittest.TestCase):
    def test_packed_file_gui_save_reopen(self):
        from unittest.mock import patch
        from visual_editor import Studio
        app=Studio();app.withdraw();app.update_idletasks()
        try:
            with tempfile.TemporaryDirectory() as td:
                path=Path(td)/'all_in_one.sg3d.json'
                with patch('tkinter.filedialog.asksaveasfilename',return_value=str(path)):
                    self.assertTrue(app.save_self_contained())
                self.assertIn('embedded_assets',app.doc)
                app.doc['name']='GUI saved changes'
                app._write_project(path)
                loaded,base=load_project(path)
                self.assertEqual(loaded['name'],'GUI saved changes')
                self.assertEqual([],check_project(path))
                self.assertTrue(base.is_dir())
        finally:
            app.destroy()
