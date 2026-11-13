"""GBA smooth-turning feature integration tests."""
import json, tempfile, unittest, subprocess, shutil
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'editor')]
from project_export import export_project
from game_preview import PreviewGame

class FacingTests(unittest.TestCase):
    def setUp(self):
        self.path=ROOT/'examples/turning_player_v12_1.sg3d.json'
        self.doc=json.loads(self.path.read_text())

    def test_scene_export_both_scenes(self):
        with tempfile.TemporaryDirectory() as out:
            result=export_project(self.path,out)
            self.assertEqual(result['scenes'],2)
            for i in range(2):
                c=(Path(out)/f'scene_{i}.c').read_text()
                self.assertIn('sg3d_facing_capture',c)
                self.assertIn('sg3d_facing_update',c)
                self.assertIn('static SG3DFacing facing_states[]',c)
                self.assertIn('sg3d_facing.h',c)
                self.assertIn('0,0,1,64,0,0,0}',c)

    def test_turns_eases_and_remembers_when_stopped(self):
        sim=PreviewGame(self.doc,self.path.parent)
        initial=sim.doc['objects'][0]['rotation'][0]
        # Player D-pad right in this scene is a movement action.
        for i in range(4):sim.tick(('RIGHT',))
        facing=sim.doc['objects'][0]['rotation'][0]
        self.assertNotEqual(facing,initial)
        self.assertGreater(facing,0)
        self.assertLess(facing,90)
        for i in range(100):sim.tick(('RIGHT',))
        self.assertAlmostEqual(sim.doc['objects'][0]['rotation'][0],90,delta=3)
        before=sim.doc['objects'][0]['rotation'][0]
        for i in range(5):sim.tick(())
        self.assertEqual(sim.doc['objects'][0]['rotation'][0],before)

    def test_finishes_easing_after_key_released(self):
        sim=PreviewGame(self.doc,self.path.parent)
        sim.tick(('RIGHT',))
        at_release=sim.doc['objects'][0]['rotation'][0]
        self.assertTrue(0<at_release<90)
        for _ in range(40):sim.tick(())
        final=sim.doc['objects'][0]['rotation'][0]
        self.assertGreater(final,at_release)
        self.assertAlmostEqual(final,90,delta=3)

    def test_backward_axis_offset(self):
        sim=PreviewGame(self.doc,self.path.parent)
        obj=sim.doc['objects'][0]
        obj['facing_offset']=180
        obj['facing_smooth']=1.0
        sim._turn_to_movement(0,[obj['position'][0]-0.1,obj['position'][1],obj['position'][2]])
        self.assertEqual(round(obj['rotation'][0])%360,270)  # +X movement, backwards model

    def test_old_projects_opt_out_by_default(self):
        import copy
        doc=copy.deepcopy(self.doc)
        for sc in doc['scenes']:
            for obj in sc['objects']:
                obj.pop('face_movement',None)
        sim=PreviewGame(doc,self.path.parent)
        initial=sim.doc['objects'][0]['rotation'][0]
        sim.tick(('RIGHT',))
        self.assertEqual(sim.doc['objects'][0]['rotation'][0],initial)

    def test_invalid_strength_rejected(self):
        doc=json.loads(self.path.read_text())
        doc['scenes'][0]['objects'][0]['facing_smooth']=0
        with tempfile.TemporaryDirectory() as out:
            with self.assertRaisesRegex(ValueError,'facing_smooth'):
                export_project(self.path,out) if False else self._export_edited(doc,out)

    def _export_edited(self,doc,dir_):
        # Original asset base location must be preserved by saving adjacent to sample.
        temp=self.path.parent/'_temporary_facing_test.sg3d.json'
        try:
            temp.write_text(json.dumps(doc))
            export_project(temp,dir_)
        finally:temp.unlink(missing_ok=True)

    def test_native_cardinal_angles(self):
        if not shutil.which('gcc'):self.skipTest('gcc unavailable')
        with tempfile.TemporaryDirectory() as out:
            executable=Path(out)/'face_test'
            cmd=['gcc','-std=c11','-Wall','-Wextra','-Werror','-I'+str(ROOT/'engine'),
                 str(ROOT/'tests/facing_host.c'),str(ROOT/'engine/sg3d_facing.c'),'-o',str(executable)]
            subprocess.run(cmd,check=True,capture_output=True,text=True)
            subprocess.run([executable],check=True,capture_output=True,text=True)

if __name__=='__main__':unittest.main()
