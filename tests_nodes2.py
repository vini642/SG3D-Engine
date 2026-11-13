"""SG3D Universal Nodes 2.0: validation + GBA/preview parity tests."""
import json
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'editor')]
from node_scripts import default_node,compile_graph
from game_preview import PreviewGame

class Graph:
    def __init__(self):self.nodes=[];self.links=[];self.data_links=[]
    def node(self,kind,**params):
        n=default_node(kind,str(len(self.nodes)+1));n['params'].update({k:str(v) for k,v in params.items()});self.nodes.append(n);return n['id']
    def flow(self,a,b,port='next'):self.links.append({'from':a,'port':port,'to':b})
    def data(self,a,b,field):self.data_links.append({'from':a,'port':'value','to':b,'input':field})
    def doc(self,**more):
        o={'objects':[{'name':'Cube','mesh':'cube.obj','position':[0,0,7],'rotation':[0,0],'scale':1,'properties':{}}],
           'camera':{'position':[0,0,0],'rotation':[0,0]},'variables':{'score':0},
           'scripts':{'nodes':self.nodes,'links':self.links,'data_links':self.data_links}}
        o.update(more);return o
class Nodes2Tests(unittest.TestCase):
    def test_reusable_function_return_and_bounded_loop(self):
        g=Graph();s=g.node('OnStart');call=g.node('CallFunction',function='Twice',argument=4,result='score');g.flow(s,call)
        repeat=g.node('Repeat',count=1000);g.flow(call,repeat)
        plus=g.node('AddVariable',variable='score',value=1);g.flow(repeat,plus,'body')
        function=g.node('FunctionDefinition',function='Twice');ret=g.node('ReturnFunction');g.flow(function,ret)
        arg=g.node('FunctionArgument');two=g.node('Number',value=2);mul=g.node('MathMultiply')
        g.data(arg,mul,'a');g.data(two,mul,'b');g.data(mul,ret,'value')
        doc=g.doc();decl,start,update=compile_graph(doc)
        self.assertIn('sg3d_bound_loop','\n'.join(decl))
        self.assertIn('goto sg3d_function_end_', '\n'.join(start))
        preview=PreviewGame(doc,ROOT/'examples')
        self.assertEqual(preview.variables['score'],72)  # (4*2) + 64 * 1
    def test_array_read_write_and_vector_action(self):
        g=Graph();s=g.node('OnStart');write=g.node('SetArray',array='waypoints',index=1,value=5);g.flow(s,write)
        val=g.node('GetArray',array='waypoints',index=1)
        setprop=g.node('SetVariable',variable='score');g.flow(write,setprop);g.data(val,setprop,'value')
        update=g.node('OnUpdate');move=g.node('MoveObjectVector',object=0);g.flow(update,move)
        v=g.node('MakeVector',x=1,y=0,z=0);g.data(v,move,'vector')
        doc=g.doc(arrays={'waypoints':[1,2,3]})
        decl,start,each=compile_graph(doc)
        self.assertIn('sg3d_array_set','\n'.join(start))
        self.assertIn('sg3d_v3(','\n'.join(each))
        preview=PreviewGame(doc,ROOT/'examples')
        self.assertEqual(preview.variables['score'],5)
        preview.tick()
        self.assertAlmostEqual(preview.doc['objects'][0]['position'][0],1)
    def test_typed_connections_are_rejected(self):
        g=Graph();v=g.node('MakeVector');b=g.node('IfBool');g.data(v,b,'value')
        with self.assertRaisesRegex(ValueError,'boolean source'):compile_graph(g.doc())
        g=Graph();n=g.node('Number');m=g.node('MoveObjectVector');g.data(n,m,'vector')
        with self.assertRaisesRegex(ValueError,'vector source'):compile_graph(g.doc())
        g=Graph();v=g.node('MakeVector');m=g.node('MathAdd');g.data(v,m,'a')
        with self.assertRaisesRegex(ValueError,'number source'):compile_graph(g.doc())
    def test_while_is_bounded_and_bool_condition_dynamic(self):
        g=Graph();start=g.node('OnStart');w=g.node('WhileBool');g.flow(start,w)
        check=g.node('Compare',op='<');g.data(check,w,'value')
        value=g.node('GetVariable',variable='score');ten=g.node('Number',value=10)
        g.data(value,check,'a');g.data(ten,check,'b')
        add=g.node('AddVariable',variable='score',value=1);g.flow(w,add,'body')
        doc=g.doc();preview=PreviewGame(doc,ROOT/'examples')
        self.assertEqual(preview.variables['score'],10)
        self.assertIn('64', '\n'.join(compile_graph(doc)[1]))
    def test_recursion_detected_and_bad_break(self):
        g=Graph();s=g.node('OnStart');call=g.node('CallFunction',function='spin');g.flow(s,call)
        fn=g.node('FunctionDefinition',function='spin');inner=g.node('CallFunction',function='spin');g.flow(fn,inner)
        with self.assertRaisesRegex(ValueError,'Recursive'):compile_graph(g.doc())
        g=Graph();s=g.node('OnStart');br=g.node('BreakLoop');g.flow(s,br)
        with self.assertRaisesRegex(ValueError,'inside'):compile_graph(g.doc())
    def test_examples_compile(self):
        for filename in ['universal_nodes2_explore.sg3d.json','universal_nodes2_drive.sg3d.json']:
            doc=json.loads((ROOT/'examples'/filename).read_text())
            _,start,update=compile_graph(doc)
            self.assertTrue(start or update)
            preview=PreviewGame(doc,ROOT/'examples');preview.tick(['UP','A'])

if __name__=='__main__':unittest.main()
