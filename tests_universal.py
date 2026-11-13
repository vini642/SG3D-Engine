"""Regression tests for genre-neutral, compiled C behavior components."""
import copy
import json
import pathlib
import sys
import tempfile
import unittest
import zipfile

ROOT=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools'))
from project_export import export_project,load_project
from project_pack import package_project,make_embedded_document
from custom_scripts import validate_components,starter
from node_scripts import compile_graph,default_node

PROJECT=ROOT/'examples/universal_three_controllers.sg3d.json'

class UniversalTests(unittest.TestCase):
    def test_three_genre_behaviors_from_c_files(self):
        doc,base=load_project(PROJECT)
        self.assertEqual(len(doc['scenes']),3)
        for scene in doc['scenes']:
            files=validate_components(scene['objects'],base)
            self.assertEqual(len(files),1)
        with tempfile.TemporaryDirectory() as temp:
            result=export_project(PROJECT,temp)
            self.assertEqual(len(result['user_sources']),3)
            manifest=json.loads((pathlib.Path(temp)/'sg3d_manifest.json').read_text())
            self.assertEqual(len(manifest['user_sources']),3)
            self.assertEqual(manifest['scenes'],3)
            for i in range(3):
                source=(pathlib.Path(temp)/f'scene_{i}.c').read_text()
                self.assertIn('_Update(&script_context,0)',source)
                self.assertIn('_Collision(&script_context,0,other)',source)
                self.assertIn('script_properties_0',source)

    def test_node_and_c_share_properties(self):
        doc,base=load_project(PROJECT)
        scene=copy.deepcopy(doc['scenes'][0]);scene['objects'][0]['properties']['points']=3
        n0=default_node('OnUpdate','evt');n1=default_node('GetProperty','get');n2=default_node('SetProperty','set')
        n1['params'].update(object='0',property='points')
        n2['params'].update(object='0',property='points')
        scene['scripts']={'nodes':[n0,n1,n2],'links':[{'from':'evt','port':'next','to':'set'}], 'data_links':[{'from':'get','port':'value','to':'set','input':'value'}]}
        decl,start,update,post=compile_graph(scene,with_physics=True)
        self.assertTrue(any('sg3d_get_property' in x and 'sg3d_set_property' in x for x in update))
        with tempfile.TemporaryDirectory() as tmp:
            p=pathlib.Path(tmp)/'level.sg3d.json'
            for obj in scene['objects']:
                for field in ('mesh','texture'):
                    if obj.get(field):obj[field]=str((base/obj[field]).resolve())
                obj['c_scripts']=[str((base/v).resolve()) for v in obj.get('c_scripts',[])]
            p.write_text(json.dumps(scene))
            report=export_project(p,pathlib.Path(tmp)/'out')
            generated=(pathlib.Path(tmp)/'out/main.c').read_text()
            self.assertIn('sg3d_get_property',generated)
            self.assertIn('sg3d_set_property',generated)

    def test_portable_project_contains_custom_c(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=pathlib.Path(tmp)/'pack.zip'
            package_project(PROJECT,path)
            with zipfile.ZipFile(path) as z:
                names=z.namelist()
                scripts=[x for x in names if x.startswith('assets/scripts/')]
                self.assertEqual(len(scripts),3)
                z.extractall(tmp)
                scene=list(pathlib.Path(tmp).glob('*.sg3d.json'))[0]
                out=pathlib.Path(tmp)/'compiled'
                report=export_project(scene,out)
                self.assertEqual(len(report['user_sources']),3)

    def test_embedded_code_survives_save_reload(self):
        doc,base=load_project(PROJECT)
        embedded=make_embedded_document(doc,base)
        with tempfile.TemporaryDirectory() as tmp:
            path=pathlib.Path(tmp)/'single.sg3d.json';path.write_text(json.dumps(embedded))
            out=pathlib.Path(tmp)/'generated'
            result=export_project(path,out)
            self.assertEqual(len(result['user_sources']),3)

    def test_invisible_object_with_attached_script(self):
        doc,base=load_project(PROJECT)
        scene=copy.deepcopy(doc['scenes'][0]);obj=scene['objects'][0]
        obj['mesh']='';obj['mode']='flat';obj['texture']=''
        obj['physics']={'solid':False,'dynamic':False}
        for field in ('mesh','texture'):
            if scene['objects'][1].get(field):scene['objects'][1][field]=str((base/scene['objects'][1][field]).resolve())
        obj['c_scripts']=[str((base/v).resolve()) for v in obj['c_scripts']]
        with tempfile.TemporaryDirectory() as tmp:
            file=pathlib.Path(tmp)/'empty.sg3d.json';file.write_text(json.dumps(scene))
            export_project(file,pathlib.Path(tmp)/'generated')
            source=(pathlib.Path(tmp)/'generated/main.c').read_text()
            self.assertIn('if(o->mesh)sg3d_draw_mesh',source)
            self.assertIn('{0,0,0,{',source)

    def test_script_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=pathlib.Path(tmp)
            (base/'steer.c').write_text(starter('steer'))
            self.assertIn('steer',validate_components([{'c_scripts':['steer.c'],'properties':{'steer':1.5}}],base))
            with self.assertRaisesRegex(ValueError,'missing'):
                validate_components([{'c_scripts':['absent.c']}],base)
            with self.assertRaisesRegex(ValueError,'missing steer_Collision'):
                (base/'steer.c').write_text('void steer_Start(){}\nvoid steer_Update(){}\n')
                validate_components([{'c_scripts':['steer.c']}],base)

if __name__=='__main__':unittest.main()
