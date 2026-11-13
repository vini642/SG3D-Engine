"""SG3D Studio 1.0 packaging, preflight and ROM output tests."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile
from unittest.mock import patch

ROOT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'editor')]
from project_pack import package_project
from project_check import check_project
from project_export import load_project,parse_obj,resolve


class ReleaseTests(unittest.TestCase):
    sample=ROOT/'examples/collectathon_v12.sg3d.json'

    def test_portable_bundle_assets_and_mtl_uv(self):
        with tempfile.TemporaryDirectory() as d:
            dest=Path(d)/'project.zip'
            data=package_project(self.sample,dest)
            self.assertGreaterEqual(data['assets'],5)
            with zipfile.ZipFile(dest) as z:
                z.extractall(Path(d)/'extract')
            doc,base=load_project(Path(d)/'extract'/data['project'])
            for scene in doc['scenes']:
                for obj in scene['objects']:
                    mesh=parse_obj(resolve(base,obj['mesh']))
                    for material in mesh['mtl'].values():
                        if material.get('texture'):
                            self.assertTrue(Path(material['texture']).is_file())
                    if obj.get('texture'):
                        self.assertTrue(resolve(base,obj['texture']).is_file())
                for item in scene.get('hud',[]):
                    if item.get('file'):
                        self.assertTrue(resolve(base,item['file']).is_file())
            for sound in doc['sounds']:
                self.assertTrue(resolve(base,sound['file']).is_file())

    def test_bundle_asset_reference_dedup(self):
        with tempfile.TemporaryDirectory() as d:
            a=package_project(self.sample,Path(d)/'a.zip')
            b=package_project(self.sample,Path(d)/'b.zip')
            self.assertEqual(a['assets'],b['assets'])

    def test_package_rejects_missing_mesh(self):
        doc,_=load_project(self.sample)
        doc['scenes'][0]['objects'][0]['mesh']='not-here.obj'
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(FileNotFoundError):
                package_project(None,Path(d)/'broken.zip',document=doc,source_base=self.sample.parent)
            self.assertFalse((Path(d)/'broken.zip').exists())

    def test_project_preflight_and_heavy_scene_warning(self):
        self.assertFalse([x for x in check_project(self.sample) if x[0]=='ERROR'])
        doc,base=load_project(self.sample)
        doc['scenes'][0]['objects'][0]['mesh']='not-here.obj'
        self.assertTrue(any('OBJ not found' in msg for _,_,msg in check_project(document=doc,base=base)))

    def test_startup_sample_cannot_overwrite_it_accidentally(self):
        from visual_editor import Studio
        app=Studio();app.withdraw();app.update_idletasks()
        try:
            self.assertIsNone(app.path)
            self.assertGreater(len(app.doc['objects']),0)
            with tempfile.TemporaryDirectory() as tmp:
                dest=Path(tmp)/'project.sg3d.json'
                with patch('visual_editor.filedialog.asksaveasfilename',return_value=str(dest)) as picker:
                    self.assertTrue(app.save_scene())
                picker.assert_called_once()
                self.assertTrue(dest.exists())
                self.assertEqual(app.path,dest)
        finally:
            app.destroy()

    def test_build_output_choice_in_editor(self):
        from visual_editor import Studio
        app=Studio();app.withdraw();app.update_idletasks()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                project=Path(tmp)/'myproject.sg3d.json'
                rom=Path(tmp)/'My_Custom_Name.gba'
                with patch('visual_editor.filedialog.asksaveasfilename',side_effect=[str(project),str(rom)]), \
                     patch('visual_editor.messagebox.showinfo'), \
                     patch('visual_editor.messagebox.askyesno',return_value=True):
                    self.assertTrue(app.build_rom())
                self.assertTrue(rom.exists())
                data=rom.read_bytes()
                self.assertEqual(data[0xB2],0x96)
                self.assertEqual((sum(data[0xA0:0xBE])+0x19)&255,0)
                self.assertTrue((ROOT/'build'/'last_build.log').is_file())
        finally:
            app.destroy()

if __name__=='__main__':unittest.main()
