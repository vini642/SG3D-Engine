"""RC2 Export GBA regression tests: self-contained saves must return success."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'editor'),str(ROOT/'tools')]
from visual_editor import Studio
from project_export import load_project
from project_pack import save_embedded_document

class ExportHotfixTests(unittest.TestCase):
    def setUp(self):
        self.app=Studio()
        self.app.withdraw()
        self.app.update_idletasks()
        self.tmp=tempfile.TemporaryDirectory()
        self.base=Path(self.tmp.name)

    def tearDown(self):
        self.app.destroy()
        self.tmp.cleanup()

    def load_embedded(self):
        doc,assets=load_project(ROOT/'examples/orbit_sky_demo.sg3d.json')
        path=self.base/'one_file.sg3d.json'
        save_embedded_document(doc,assets,path)
        self.app.doc,self.app.asset_base=load_project(path)
        self.app.path=path
        self.app._prepare_scenes()
        self.app._bind_scene(self.app.doc['active_scene'])
        self.app.populate()
        return path

    def test_embedded_saves_report_success(self):
        path=self.load_embedded()
        self.assertIs(self.app.save_scene(),True)
        self.assertTrue(path.is_file())
        self.assertIs(self.app._write_project(path),True)

    def test_embedded_gui_export_button_builds_rom(self):
        self.load_embedded()
        rom=self.base/'output.gba'
        buttons=[]
        def find(widget):
            for child in widget.winfo_children():
                if child.winfo_class()=='TButton' and child.cget('text')=='Export GBA':
                    buttons.append(child)
                find(child)
        find(self.app)
        self.assertEqual(len(buttons),1)
        with patch('tkinter.filedialog.asksaveasfilename',return_value=str(rom)) as dialog, \
             patch('tkinter.messagebox.askyesno',return_value=True), \
             patch('tkinter.messagebox.showinfo') as info, \
             patch('tkinter.messagebox.showerror') as err:
            buttons[0].invoke()
            self.assertEqual(dialog.call_count,1)
            self.assertFalse(err.called,str(err.call_args))
            self.assertTrue(info.called)
        self.assertTrue(rom.is_file())
        self.assertGreater(rom.stat().st_size,0xC0)

    def test_cancel_unsaved_export_gives_status(self):
        self.app.path=None
        with patch('tkinter.filedialog.asksaveasfilename',return_value='') as dialog, \
             patch('visual_editor.export_project') as exporter:
            self.assertIs(self.app.build_rom(),False)
            self.assertEqual(dialog.call_count,1)
            self.assertFalse(exporter.called)
        self.assertIn('cancelled',self.app.stat.get().lower())

if __name__=='__main__':
    unittest.main()
