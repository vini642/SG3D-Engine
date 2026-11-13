"""Node-only Mini Golf experiment: compiler + PC-preview behavior."""
import sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'editor')]
from project_export import load_project
from node_scripts import compile_graph
from game_preview import PreviewGame
PROJECT=ROOT/'examples'/'mini_golf_nodes'/'MiniGolf_NodesOnly.sg3d.json'
class GolfNodePortTests(unittest.TestCase):
    def setUp(self):
        self.scene,self.base=load_project(PROJECT)
    def test_no_custom_c_and_graph_valid(self):
        self.assertEqual(142,len(self.scene['scripts']['nodes']))
        self.assertFalse(any(obj.get('c_scripts') for obj in self.scene['objects']))
        self.assertFalse(any(key.endswith('.c') for key in self.scene.get('embedded_assets',{})))
        self.assertTrue(compile_graph(self.scene)[2])
    def test_charge_release_and_penalty_reset(self):
        game=PreviewGame(self.scene,self.base)
        for _ in range(12):game.tick({'A'})
        self.assertEqual(36,game.variables['charge'])
        self.assertEqual(0,game.variables['strokes'])
        game.tick(())
        self.assertEqual(1,game.variables['strokes'])
        self.assertGreater(game.doc['objects'][0]['position'][2],0)
        for _ in range(10):game.tick(())
        game.tick({'B'})
        self.assertEqual(2,game.variables['strokes'])
        self.assertAlmostEqual(0,game.doc['objects'][0]['position'][2])
        game.tick(())
        game.tick({'START'})
        self.assertEqual(0,game.variables['strokes'])
    def test_aim_camera_overview_and_moved_tee(self):
        game=PreviewGame(self.scene,self.base)
        game.tick({'RIGHT'});game.tick({'RIGHT'})
        self.assertGreaterEqual(game.variables['aim'],2)
        game.tick(())
        game.tick({'R'})
        self.assertEqual(1,game.variables['overview'])
        # Reset is linked to the existing tagged tee at index 19, not fixed world zero.
        game.doc['objects'][19]['position'][0]=3
        game.tick(())
        game.tick({'START'})
        self.assertAlmostEqual(3,game.doc['objects'][0]['position'][0])
if __name__=='__main__':unittest.main()
