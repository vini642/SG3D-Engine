"""v0.12 export, UI nodes, ROM metadata, editor round-trip and gameplay tests."""
import json, os, sys, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'editor')]
from project_export import export_project
from node_scripts import compile_graph,default_node
from game_preview import PreviewGame
from PIL import Image

class HUDTests(unittest.TestCase):
    def setUp(self):
        self.sample=ROOT/'examples/collectathon_v12.sg3d.json'
        self.doc=json.loads(self.sample.read_text())
    def test_two_scene_hud_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            result=export_project(self.sample,tmp)
            self.assertEqual(result['hud'],8)
            self.assertEqual(result['scenes'],2)
            src=(Path(tmp)/'scene_0.c').read_text()
            self.assertIn('sg3d_hud_load(scene_hud,4)',src)
            self.assertIn('sg3d_hud_set_value(0,',src)
            self.assertIn('sg3d_hud_set_visible(3,0)',src)
            self.assertIn('static const uint8_t ui_sprite_2',src)
            self.assertIn('sg3d_physics_move(physics_bodies',src)
            self.assertEqual(json.loads((Path(tmp)/'sg3d_build_settings.json').read_text())['code'],'SG12')
    def test_old_project_has_no_hud(self):
        with tempfile.TemporaryDirectory() as tmp:
            report=export_project(ROOT/'examples/two_worlds_v10.sg3d.json',tmp)
            self.assertEqual(report['hud'],0)
    def test_ui_index_validation(self):
        d={'objects':[],'hud':[],'scripts':{'nodes':[default_node('SetUIValue','u')],'links':[],'data_links':[]}}
        with self.assertRaisesRegex(ValueError,'HUD element'):
            # connected UI action required to reach graph compilation
            d['scripts']['nodes'].insert(0,default_node('OnStart','s'))
            d['scripts']['links'].append({'from':'s','port':'next','to':'u'})
            compile_graph(d)
    def test_invalid_png(self):
        from hud_assets import hud_emit
        with self.assertRaisesRegex(ValueError,'missing sprite'):
            hud_emit({'hud':[{'type':'sprite','file':'doesnt_exist.png'}]},ROOT)
    def test_preview_render_with_hud(self):
        from gba_preview import render_scene
        scene=self.doc['scenes'][0]
        image,tris=render_scene(scene,self.sample.parent)
        self.assertEqual(image.size,(240,160))
        self.assertGreater(tris,0)
    def test_pc_node_updates_counter(self):
        p=PreviewGame(self.doc,self.sample.parent)
        p.variables['collected']=3
        p.tick(())
        self.assertEqual(p.doc['hud'][0]['value'],3)
        p.tick(('START',))
        self.assertFalse(p.doc['hud'][3]['visible'])
    def test_gui_hud_settings_and_save(self):
        import tkinter as tk
        from visual_editor import Studio
        from ui_editor import HUDEditor,ProjectSettings
        app=Studio();app.withdraw();app.update_idletasks()
        try:
            hud=HUDEditor(app);hud.update_idletasks();hud.refresh(0)
            self.assertEqual(len(app.doc['hud']),4)
            hud.vars['text'].set('TEST HUD');hud.apply()
            self.assertEqual(app.doc['hud'][0]['text'],'TEST HUD')
            hud.destroy()
            settings=ProjectSettings(app);settings.update_idletasks()
            settings.inputs['title'].set('TEST GAME');settings.inputs['code'].set('TG01');settings.apply()
            self.assertEqual(app.doc['settings']['code'],'TG01')
            with tempfile.TemporaryDirectory() as tmp:
                file=Path(tmp)/'test.sg3d.json'
                app._write_project(file)
                reloaded=json.loads(file.read_text())
                self.assertEqual(reloaded['scenes'][0]['hud'][0]['text'],'TEST HUD')
                self.assertEqual(reloaded['settings']['title'],'TEST GAME')
                self.assertTrue((file.parent/reloaded['scenes'][0]['hud'][2]['file']).is_file())
        finally:app.destroy()

if __name__=='__main__':unittest.main()
