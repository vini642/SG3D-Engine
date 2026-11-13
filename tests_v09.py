"""v0.9 game behavior and save/load regression tests."""
import json, sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).parent
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'editor')]
from project_export import load_project, resolve, export_project
from node_scripts import compile_graph
from game_preview import PreviewGame

class GameTests(unittest.TestCase):
    def setUp(self):
        self.source=ROOT/'examples/platformer_v09.sg3d.json'
        self.doc,_=load_project(self.source)

    def test_nodes_export(self):
        decl,start,update,post=compile_graph(self.doc,with_physics=True)
        self.assertIn('sg3d_physics_move',str(update))
        self.assertIn('sg3d_physics_jump',str(update))
        self.assertIn('sg3d_physics_touching',str(post))
        with tempfile.TemporaryDirectory() as d:
            report=export_project(self.source,d)
            generated=(Path(d)/'main.c').read_text()
            self.assertIn('sg3d_physics_step(',generated)
            self.assertIn('collision_previous',generated)
            self.assertIn('cam.x = scene_objects[0].transform.x',generated)
            self.assertEqual(report['dynamic_bodies'],1)

    def test_preview_jump_collision_and_collection(self):
        sim=PreviewGame(self.doc,ROOT/'examples')
        sim.tick([])
        self.assertTrue(sim.bodies[0]['grounded'])
        sim.tick(['A'])
        self.assertGreater(sim.doc['objects'][0]['position'][1],-.6)
        for k in range(130):sim.tick([])
        self.assertTrue(sim.bodies[0]['grounded'])
        self.assertAlmostEqual(sim.doc['objects'][0]['position'][1],-.6,delta=.02)
        for k in range(16):sim.tick(['RIGHT'])
        self.assertEqual(sim.variables['collected'],1)
        self.assertGreater(sim.doc['objects'][2]['position'][1],15)
        self.assertEqual(self.doc['objects'][2]['position'][1],-.6) # editor scene untouched
        self.assertAlmostEqual(sim.doc['camera']['position'][0],sim.doc['objects'][0]['position'][0])

    def test_collision_event_invalid_other(self):
        bad=json.loads(json.dumps(self.doc))
        next(n for n in bad['scripts']['nodes'] if n['type']=='OnCollision')['params']['other']='100'
        with self.assertRaisesRegex(ValueError,'target object'):compile_graph(bad)

class SaveTests(unittest.TestCase):
    def test_new_scene_save_as_once_and_reopen(self):
        from visual_editor import Studio
        app=Studio();app.withdraw();app.update_idletasks()
        try:
            app.new_scene();app.add_primitive('cube.obj')
            with tempfile.TemporaryDirectory() as d:
                out=Path(d)/'scene.sg3d.json'
                with patch('visual_editor.filedialog.asksaveasfilename',return_value=str(out)) as picker:
                    self.assertTrue(app.save_scene())
                    picker.assert_called_once()
                self.assertTrue(out.exists())
                filedoc,base=load_project(out)
                self.assertEqual(len(filedoc['objects']),1)
                self.assertTrue(resolve(base,filedoc['objects'][0]['mesh']).is_file())
                app.doc['objects'][0]['position'][0]=23
                with patch('visual_editor.filedialog.asksaveasfilename',side_effect=AssertionError('unexpected dialog')):
                    self.assertTrue(app.save_scene())
                reopen,_=load_project(out)
                self.assertEqual(reopen['objects'][0]['position'][0],23)
        finally:app.destroy()

    def test_save_as_preserves_referenced_files(self):
        from visual_editor import Studio
        app=Studio();app.withdraw();app.update_idletasks()
        try:
            # This is a v0.9 compatibility regression, so explicitly load v0.9.
            app.doc,_=load_project(ROOT/'examples/platformer_v09.sg3d.json')
            app.path=ROOT/'examples/platformer_v09.sg3d.json'
            app._prepare_scenes()
            with tempfile.TemporaryDirectory() as d:
                dest=Path(d)/'subfolder'/'scene.sg3d.json'
                with patch('visual_editor.filedialog.asksaveasfilename',return_value=str(dest)):
                    self.assertTrue(app.save_as())
                loaded,base=load_project(dest)
                self.assertTrue(resolve(base,loaded['objects'][0]['mesh']).is_file())
                self.assertEqual(len(loaded['scripts']['nodes']),15)
                self.assertEqual(app.path,dest)
        finally:app.destroy()

if __name__=='__main__':unittest.main(verbosity=2)
