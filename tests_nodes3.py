"""Universal Nodes 3.0: object references, scene queries and spatial math."""
import json
import math
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'editor')]
from node_scripts import compile_graph,default_node
from game_preview import PreviewGame
from project_export import load_project

class Graph:
    def __init__(self):self.nodes=[];self.links=[];self.data_links=[]
    def node(self,kind,**params):
        n=default_node(kind,str(len(self.nodes)+1));n['params'].update({k:str(v) for k,v in params.items()});self.nodes.append(n);return n['id']
    def flow(self,a,b,port='next'):self.links.append({'from':a,'to':b,'port':port})
    def data(self,a,b,key):self.data_links.append({'from':a,'to':b,'port':'value','input':key})
    def doc(self):
        return {'objects':[
          {'name':'A','mesh':'cube.obj','position':[0,0,0],'rotation':[0,0],'scale':1,'properties':{'tag':1}},
          {'name':'B','mesh':'cube.obj','position':[2,0,0],'rotation':[90,0],'scale':1,'properties':{'tag':0}},
          {'name':'C','mesh':'cube.obj','position':[3,0,0],'rotation':[0,0],'scale':1,'properties':{'tag':1}}],
        'variables':{'count':0,'last_x':0,'result':0,'hit':0},
        'camera':{'position':[0,1,-5],'rotation':[0,0]},
        'scripts':{'nodes':self.nodes,'links':self.links,'data_links':self.data_links}}

class Nodes3Tests(unittest.TestCase):
    def test_for_each_filter_and_dynamic_getproperty(self):
        g=Graph(); start=g.node('OnStart');loop=g.node('ForEachObject',property='tag');g.flow(start,loop)
        count=g.node('AddVariable',variable='count',value=1);g.flow(loop,count,'body')
        ref=g.node('LoopObject');pos=g.node('GetObjectX',object=0);g.data(ref,pos,'object')
        assign=g.node('SetVariable',variable='last_x');g.data(pos,assign,'value');g.flow(count,assign)
        code=compile_graph(g.doc())[1];self.assertIn('for(int sg3d_loop_',str(code))
        preview=PreviewGame(g.doc(),ROOT/'examples')
        self.assertEqual(preview.variables['count'],2)
        self.assertEqual(preview.variables['last_x'],3)
    def test_dynamic_write_property(self):
        g=Graph();event=g.node('OnStart');loop=g.node('ForEachObject',property='tag');g.flow(event,loop)
        ref=g.node('LoopObject');setp=g.node('SetProperty',object=0,property='tag',value=5)
        g.flow(loop,setp,'body');g.data(ref,setp,'object')
        code=str(compile_graph(g.doc())[1]);self.assertIn('sg3d_set_property',code)
        game=PreviewGame(g.doc(),ROOT/'examples')
        self.assertEqual([o['properties']['tag'] for o in game.doc['objects']],[5,0,5])
    def test_inverse_transform_and_segment(self):
        g=Graph();loc=g.node('WorldToLocal',object=1)
        world=g.node('MakeVector',x=3,y=0,z=0);g.data(world,loc,'vector')
        to_world=g.node('LocalToWorld',object=1);g.data(loc,to_world,'vector')
        game=PreviewGame(g.doc(),ROOT/'examples')
        got=game.value(game.nodes[to_world]);self.assertAlmostEqual(got[0],3,places=5)
        self.assertAlmostEqual(got[2],0,places=5)
        c=g.node('CircleSegmentOverlap',radius=.15);p=g.node('MakeVector',x=.10,z=.5)
        a=g.node('MakeVector',x=0,z=0);b=g.node('MakeVector',x=0,z=1)
        g.data(p,c,'point');g.data(a,c,'a');g.data(b,c,'b')
        game=PreviewGame(g.doc(),ROOT/'examples')
        self.assertEqual(game.value(game.nodes[c]),1)
        normal=g.node('CircleSegmentNormal');g.data(p,normal,'point');g.data(a,normal,'a');g.data(b,normal,'b')
        game=PreviewGame(g.doc(),ROOT/'examples')
        self.assertAlmostEqual(game.value(game.nodes[normal])[0],1.0)
    def test_aabb_ray_sphere_extents_and_distance(self):
        g=Graph();a=g.node('MakeVector',x=2,y=0,z=-2);b=g.node('MakeVector',x=2,y=0,z=2)
        ray=g.node('RaycastBox',object=1);g.data(a,ray,'a');g.data(b,ray,'b')
        point=g.node('MakeVector',x=3.3);sphere=g.node('SphereBoxOverlap',object=1,radius=.15);g.data(point,sphere,'point')
        cp=g.node('ClosestPointBox',object=1);g.data(point,cp,'point')
        dims=g.node('GetObjectHalfExtents',object=1)
        dist=g.node('VectorDistanceSqXZ');g.data(a,dist,'a');g.data(b,dist,'b')
        game=PreviewGame(g.doc(),ROOT/'examples')
        self.assertEqual(game.value(game.nodes[ray]),1)
        self.assertEqual(game.value(game.nodes[sphere]),0)  # outside B's box by .3
        self.assertAlmostEqual(game.value(game.nodes[cp])[0],3.0)
        self.assertEqual(tuple(game.value(game.nodes[dims])),(1.0,1.0,1.0))
        self.assertEqual(game.value(game.nodes[dist]),16)
    def test_functions_receive_multiple_types(self):
        g=Graph();start=g.node('OnStart');call=g.node('CallFunction',function='Compute',argument=2,argument_b=3,result='result');g.flow(start,call)
        vec=g.node('MakeVector',x=4,y=0,z=0);g.data(vec,call,'argument_vector')
        ref=g.node('ObjectRef',object=2);g.data(ref,call,'argument_object')
        fun=g.node('FunctionDefinition',function='Compute');ret=g.node('ReturnFunction');g.flow(fun,ret)
        arg=g.node('FunctionArgument');argb=g.node('FunctionArgumentB');argv=g.node('FunctionArgumentVector');argo=g.node('FunctionArgumentObject')
        x=g.node('VectorX');g.data(argv,x,'vector')
        ad=g.node('MathAdd');g.data(arg,ad,'a');g.data(argb,ad,'b')
        ad2=g.node('MathAdd');g.data(ad,ad2,'a');g.data(x,ad2,'b')
        # Object argument feeds an object position getter.
        objx=g.node('GetObjectX',object=0);g.data(argo,objx,'object')
        ad3=g.node('MathAdd');g.data(ad2,ad3,'a');g.data(objx,ad3,'b');g.data(ad3,ret,'value')
        game=PreviewGame(g.doc(),ROOT/'examples')
        self.assertEqual(game.variables['result'],2+3+4+3)
        decl,start,_=compile_graph(g.doc())
        self.assertIn('sg3d_argo_',str(start));self.assertIn('SG3DVec3',str(decl))
    def test_wrong_object_pin_type_rejected(self):
        g=Graph();num=g.node('Number');move=g.node('MoveObject',object=0)
        g.data(num,move,'object')
        with self.assertRaisesRegex(ValueError,'object reference'):compile_graph(g.doc())
    def test_invalid_function_and_scope_rejected(self):
        g=Graph();up=g.node('OnUpdate');s=g.node('SetVariable',variable='count');g.flow(up,s)
        ref=g.node('LoopObject');g.data(ref,s,'value')
        with self.assertRaisesRegex(ValueError,'number source'):compile_graph(g.doc())
    def test_custom_event_number_and_object_payload(self):
        g=Graph();start=g.node('OnStart');emit=g.node('EmitEvent',event='Pickup',value=7)
        g.flow(start,emit)
        ref=g.node('ObjectRef',object=2);g.data(ref,emit,'object')
        on=g.node('OnEvent',event='Pickup');save=g.node('SetVariable',variable='result');g.flow(on,save)
        value=g.node('EventValue');g.data(value,save,'value')
        save_x=g.node('SetVariable',variable='last_x');g.flow(save,save_x)
        who=g.node('EventObject');x=g.node('GetObjectX',object=0);g.data(who,x,'object');g.data(x,save_x,'value')
        decl,start,update=compile_graph(g.doc());self.assertIn('sg3d_evt_val',str(start))
        game=PreviewGame(g.doc(),ROOT/'examples')
        self.assertEqual(game.variables['result'],7)
        self.assertEqual(game.variables['last_x'],3)
    def test_recursive_custom_event_rejected(self):
        g=Graph();start=g.node('OnStart');emit=g.node('EmitEvent',event='Ping');g.flow(start,emit)
        listener=g.node('OnEvent',event='Ping');emit2=g.node('EmitEvent',event='Ping');g.flow(listener,emit2)
        # Two emitters recurse through the same named listener, but Event→EmitEvent creates recursive emission.
        with self.assertRaisesRegex(ValueError,'Cycle'):compile_graph(g.doc())
    def test_embedded_reusable_function_library(self):
        g=Graph();start=g.node('OnStart');call=g.node('CallFunction',function='Triple',argument=3,result='result');g.flow(start,call)
        d=g.doc()
        fn=default_node('FunctionDefinition','def');fn['params']['function']='Triple'
        arg=default_node('FunctionArgument','arg')
        mul=default_node('MathMultiply','mul');mul['params']['b']='3'
        ret=default_node('ReturnFunction','ret')
        d['node_components']=[{'name':'MathLibrary','scripts':{
             'nodes':[fn,arg,mul,ret],
             'links':[{'from':'def','to':'ret','port':'next'}],
             'data_links':[{'from':'arg','to':'mul','input':'a','port':'value'},
                           {'from':'mul','to':'ret','input':'value','port':'value'}]
        }}]
        gdecl,start,update=compile_graph(d)
        self.assertIn('sg3d_arg_',str(start))
        game=PreviewGame(d,ROOT/'examples')
        self.assertEqual(game.variables['result'],9)
    def test_invalid_reusable_lib_rejected(self):
        g=Graph();d=g.doc()
        d['node_components']=[{'name':'Bad','scripts':{'nodes':[default_node('OnUpdate','e')], 'links':[],'data_links':[]}}]
        with self.assertRaisesRegex(ValueError,'non-reusable event'):compile_graph(d)

    def test_real_golf_has_tagged_tiles(self):
        p=ROOT/'examples'/'SG3D_MiniGolf_Nodes3_Diagnostics.sg3d.json'
        if not p.is_file():self.skipTest('external diagnostic project not packaged')
        doc,base=load_project(p)
        game=PreviewGame(doc,base)
        self.assertEqual(game.variables['tile_count'],18)

if __name__=='__main__':unittest.main()
