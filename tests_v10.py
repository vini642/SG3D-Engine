"""Version 0.10 regression tests: typed numeric wires, scene exporting, and GUI save."""
import copy, json, sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'editor')]
from project_export import export_project,load_project,resolve
from game_preview import PreviewGame
from node_scripts import compile_graph,default_node

class ValueWireTests(unittest.TestCase):
    def setUp(self):
        self.doc={'objects':[{'name':'X'}],'variables':{'coins':2},
                  'scripts':{'nodes':[
                    default_node('OnUpdate','ev'),default_node('SetVariable','set'),
                    default_node('GetVariable','get'),default_node('Number','num'),
                    default_node('MathAdd','add')],
                  'links':[{'from':'ev','port':'next','to':'set'}],
                  'data_links':[{'from':'get','port':'value','to':'add','input':'a'},
                                {'from':'num','port':'value','to':'add','input':'b'},
                                {'from':'add','port':'value','to':'set','input':'value'}]}}
        self.doc['scripts']['nodes'][1]['params']['variable']='coins'
        self.doc['scripts']['nodes'][2]['params']['variable']='coins'
        self.doc['scripts']['nodes'][3]['params']['value']='1'
    def test_c_expressions(self):
        _,_,update=compile_graph(self.doc)
        self.assertIn('sgv_coins = ((sgv_coins) + (256));',' '.join(update))
    def test_bad_input(self):
        self.doc['scripts']['data_links'][1]['input']='object'
        with self.assertRaisesRegex(ValueError,'Invalid value input'):compile_graph(self.doc)
    def test_duplicate_input(self):
        self.doc['scripts']['data_links'].append({'from':'get','port':'value','to':'add','input':'a'})
        with self.assertRaisesRegex(ValueError,'Only one data wire'):compile_graph(self.doc)
    def test_value_cycle(self):
        self.doc['scripts']['data_links'].append({'from':'add','port':'value','to':'add','input':'a'})
        with self.assertRaises(ValueError):compile_graph(self.doc)
    def test_multiply_divide(self):
        self.doc['scripts']['nodes'].append(default_node('MathMultiply','mul'))
        self.doc['scripts']['nodes'].append(default_node('MathDivide','div'))
        self.doc['scripts']['data_links'][2]['from']='mul'
        self.doc['scripts']['data_links'].append({'from':'div','to':'mul','input':'a','port':'value'})
        _,_,update=compile_graph(self.doc)
        self.assertIn('sg3d_fxmul',str(update))
        self.assertIn('sg3d_fxdiv',str(update))

class MultiSceneTests(unittest.TestCase):
    def setUp(self):
        self.project=ROOT/'examples/two_worlds_v10.sg3d.json'
        self.doc,self.base=load_project(self.project)
    def test_export_multi_scene(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=export_project(self.project,tmp)
            self.assertEqual(r['scenes'],2)
            out=Path(tmp)
            self.assertTrue((out/'scene_0.c').exists())
            self.assertTrue((out/'scene_1.c').exists())
            self.assertTrue((out/'scene_assets_0.h').exists())
            self.assertTrue((out/'scene_assets_1.h').exists())
            dispatcher=(out/'main.c').read_text()
            self.assertEqual(dispatcher.count('int32_t sgv_collected ='),1)
            self.assertIn('sg3d_run_scene_1()',dispatcher)
            a=(out/'scene_0.c').read_text()
            b=(out/'scene_1.c').read_text()
            self.assertIn('sg3d_requested_scene = 1;',a)
            self.assertIn('sg3d_requested_scene = 0;',b)
            self.assertIn('sgv_collected = ((sgv_collected) + (256));',b)
    def test_preview_switch_and_variable_persistence(self):
        sim=PreviewGame(self.doc,self.base,scene_index=1)
        self.assertEqual(sim.variables['collected'],0)
        sim.tick(['A'])
        self.assertEqual(sim.variables['collected'],1)
        sim.tick([]);sim.tick(['B'])
        self.assertEqual(sim.requested_scene,0)
        other=PreviewGame(self.doc,self.base,scene_index=0,shared_variables=sim.variables)
        self.assertEqual(other.variables['collected'],1)
    def test_old_scenes_open(self):
        old,_=load_project(ROOT/'examples/platformer_v09.sg3d.json')
        self.assertNotIn('scenes',old)

class EditorGuiTests(unittest.TestCase):
    def test_scene_switch_and_rebased_save(self):
        from visual_editor import Studio
        app=Studio();app.withdraw();app.update_idletasks()
        try:
            # Exercise the original two-scene layout, not the new v0.11 demo.
            app.doc,_=load_project(ROOT/'examples/platformer_v09.sg3d.json')
            app.path=ROOT/'examples/platformer_v09.sg3d.json'
            app._prepare_scenes()
            app._bind_scene(0)
            old_name=app.doc['scenes'][0]['name']
            from tkinter import simpledialog
            with patch.object(simpledialog,'askstring',return_value='Another Level'):
                app.add_scene()
            app.add_primitive('cube.obj')
            self.assertEqual(app.doc['active_scene'],1)
            with tempfile.TemporaryDirectory() as d:
                target=Path(d)/'my_game.sg3d.json'
                self.assertTrue(app._write_project(target))
                loaded,base=load_project(target)
                self.assertEqual(len(loaded['scenes']),2)
                self.assertEqual(loaded['scenes'][0]['name'],old_name)
                self.assertEqual(loaded['scenes'][1]['name'],'Another Level')
                for sc in loaded['scenes']:
                    for obj in sc['objects']:
                        self.assertTrue(resolve(base,obj['mesh']).is_file())
                app._bind_scene(0)
                self.assertTrue(len(app.doc['objects'])>0)
                app._bind_scene(1)
                self.assertEqual(len(app.doc['objects']),1)
        finally:app.destroy()

if __name__=='__main__':unittest.main(verbosity=2)
