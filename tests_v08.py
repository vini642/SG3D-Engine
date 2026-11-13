#!/usr/bin/env python3
"""Node compiler, GBA-resolution textured preview, legacy compatibility."""
import copy, json, sys, unittest
from pathlib import Path
ROOT=Path(__file__).parent
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'editor')]
from node_scripts import compile_graph, default_node
from project_export import export_project
from gba_preview import render_scene

class V08Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc=json.loads((ROOT/'examples/scripted_project.sg3d.json').read_text())

    def test_scripted_graph_compiles(self):
        decl,start,update=compile_graph(self.doc)
        s='\n'.join(update)
        self.assertIn('scene_objects[0].transform.yaw += 1;',s)
        self.assertIn('if (keys & UP)',s)
        self.assertIn('if ((keys & A) && !(prev & A))',s)
        self.assertIn('if (sgv_score >= 768)',s)
        self.assertIn('sgv_score += 256;',s)
        self.assertEqual(start,[])

    def test_missing_object_is_rejected(self):
        doc=copy.deepcopy(self.doc)
        next(n for n in doc['scripts']['nodes'] if n['type']=='RotateObject')['params']['object']='99'
        with self.assertRaisesRegex(ValueError,'target object'):compile_graph(doc)

    def test_unknown_variable_rejected(self):
        doc=copy.deepcopy(self.doc)
        next(n for n in doc['scripts']['nodes'] if n['type']=='AddVariable')['params']['variable']='missing'
        with self.assertRaisesRegex(ValueError,'undefined variable'):compile_graph(doc)

    def test_graph_cycle_rejected(self):
        doc=copy.deepcopy(self.doc)
        doc['scripts']['links'].append({'from':'n15','port':'next','to':'n12'})
        # Here n12 has two inputs. It must reject bad graph even before cycle walk.
        with self.assertRaises(ValueError):compile_graph(doc)

    def test_duplicate_output_rejected(self):
        doc=copy.deepcopy(self.doc)
        doc['scripts']['links'].append({'from':'n1','port':'next','to':'n5'})
        with self.assertRaises(ValueError):compile_graph(doc)

    def test_preview_is_GBA_native_and_textured(self):
        image,n=render_scene(self.doc,ROOT/'examples')
        self.assertEqual(image.size,(240,160))
        self.assertGreater(n,0)
        colors=set(image.get_flattened_data() if hasattr(image,"get_flattened_data") else image.getdata())
        self.assertGreater(len(colors),5)
        self.assertTrue(all(image.getpixel((x,y))==image.getpixel((x+1,y))
                            for y in range(0,160,2) for x in range(0,240,2)))

    def test_compiled_c_has_graph_and_is_backward_compatible(self):
        path=ROOT/'examples/scripted_project.sg3d.json'
        import tempfile
        with tempfile.TemporaryDirectory() as t:
            report=export_project(path,t)
            code=(Path(t)/'main.c').read_text()
            self.assertEqual(report['script_nodes'],19)
            self.assertIn('OnUpdate and button events',code)
            self.assertIn('scene_objects[0].transform.yaw += 1;',code)
        with tempfile.TemporaryDirectory() as t:
            report=export_project(ROOT/'examples/demo_project.sg3d.json',t)
            code=(Path(t)/'main.c').read_text()
            self.assertEqual(report['script_nodes'],0)
            self.assertIn('if(keys&LEFT)cam.x-=16',code)

if __name__=='__main__':unittest.main(verbosity=2)
