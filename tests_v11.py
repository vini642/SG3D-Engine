"""v0.11 animation, PCM asset, script, multiscene and GUI save tests."""
import copy,json,sys,tempfile,unittest,wave
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'editor')]
from animation_assets import validated_clips,pose_at,bake,emit_c
from audio_assets import convert_wav,sound_manifest
from project_export import export_project,load_project,resolve
from node_scripts import compile_graph,default_node
from game_preview import PreviewGame

class AnimationTests(unittest.TestCase):
    def setUp(self):
        self.project=ROOT/'examples/animation_audio_lab_v11.sg3d.json'
        self.doc,self.base=load_project(self.project)
        self.clip=validated_clips(self.doc)[0]
    def test_keyframe_interpolation_baked(self):
        first=pose_at(self.clip,0)
        middle=pose_at(self.clip,32)
        self.assertGreater(middle['position'][1],first['position'][1])
        frames=bake(self.clip)
        self.assertEqual(len(frames),64)
        self.assertEqual(frames[0][3],0)
        self.assertTrue(frames[32][3]>0)
        self.assertIn('sg3d_anim_step',emit_c(self.doc)[0])
    def test_reject_bad_dynamic_animation(self):
        bad=copy.deepcopy(self.doc)
        bad['animations'][0]['object']=0
        with self.assertRaisesRegex(ValueError,'dynamic physics'):validated_clips(bad)
    def test_control_nodes_compile(self):
        decl,start,update=compile_graph(self.doc)
        self.assertIn('sg3d_audio_play(sg3d_sound_0',str(update))
        self.assertIn('sg3d_anim_play(0)',str(update))
        self.assertIn('sg3d_anim_stop(0)',str(update))
    def test_invalid_refs(self):
        bad=copy.deepcopy(self.doc)
        node=next(n for n in bad['scripts']['nodes'] if n['type']=='PlaySound')
        node['params']['sound']='99'
        with self.assertRaisesRegex(ValueError,'invalid WAV sound'):compile_graph(bad)
    def test_play_mode_and_sfx(self):
        sim=PreviewGame(self.doc,self.base,scene_index=0)
        objidx=self.clip['object']
        before=sim.doc['objects'][objidx]['position'][1]
        for _ in range(33):sim.tick([])
        self.assertGreater(sim.doc['objects'][objidx]['position'][1],before)
        sim.tick(['SELECT'])
        self.assertTrue(any(name=='chime' for _,name in sim.sound_events))
        sim.tick([]);sim.tick(['L'])
        self.assertNotIn(0,sim.clip_states)
        sim.tick([]);sim.tick(['R'])
        self.assertIn(0,sim.clip_states)
        self.assertEqual(self.doc['objects'][objidx]['position'][1],before)
    def test_multiscene_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            report=export_project(self.project,tmp)
            out=Path(tmp)
            self.assertEqual(report['scenes'],2)
            self.assertEqual(report['animations'],2)
            self.assertEqual(report['sounds'],2)
            self.assertIn('sg3d_anim_frames_0', (out/'scene_0.c').read_text())
            self.assertIn('sg3d_audio_play(', (out/'scene_1.c').read_text())
            self.assertIn('sg3d_audio_init()', (out/'main.c').read_text())
            self.assertIn('sg3d_sound_0', (out/'audio_assets.h').read_text())

class AudioTests(unittest.TestCase):
    def test_pcm_converter(self):
        data=convert_wav(ROOT/'examples/sounds/chime.wav')
        self.assertEqual(len(data),2048)
        self.assertTrue(all(-128<=v<=127 for v in data))
    def test_reject_empty_wave(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'empty.wav'
            with wave.open(str(p),'wb') as f:
                f.setnchannels(1);f.setsampwidth(1);f.setframerate(8192);f.writeframes(b'')
            with self.assertRaisesRegex(ValueError,'Empty WAV'):convert_wav(p)

class SaveAndGuiTests(unittest.TestCase):
    def test_save_sound_paths_and_animations(self):
        from visual_editor import Studio
        app=Studio();app.withdraw();app.update_idletasks()
        try:
            with tempfile.TemporaryDirectory() as d:
                dest=Path(d)/'game'/'save.sg3d.json'
                self.assertTrue(app._write_project(dest))
                loaded,base=load_project(dest)
                self.assertEqual(len(loaded['scenes']),2)
                self.assertEqual(len(loaded['sounds']),2)
                self.assertEqual(len(loaded['animations']),1)
                for sound in loaded['sounds']:
                    self.assertTrue(resolve(base,sound['file']).is_file())
                # Re-export from moved project: all source assets still resolve.
                result=export_project(dest,Path(d)/'compiled')
                self.assertEqual(result['animations'],2)
        finally:app.destroy()
    def test_open_animation_manager(self):
        from visual_editor import Studio
        from assets_editor import AnimationEditor,SoundEditor
        app=Studio();app.withdraw();app.update_idletasks()
        try:
            a=AnimationEditor(app);a.update_idletasks()
            self.assertEqual(len(a.clips_data()),1)
            a.close()
            s=SoundEditor(app);s.update_idletasks()
            self.assertEqual(s.list.size(),2)
            s.destroy()
        finally:app.destroy()

if __name__=='__main__':unittest.main(verbosity=2)
