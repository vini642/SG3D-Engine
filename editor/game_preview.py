"""Lightweight PC play-test for SG3D graphs. Not a GBA emulator.

Keeps a separate copy of the scene, simulates frame-based visual node scripts
and the same axis-aligned collision rules. Only built-in node types are run.
"""
import copy
import math
from pathlib import Path
from project_export import parse_obj, resolve
from node_scripts import compile_graph, expanded_graph, EVENTS, NODE_TYPES, KEYS, VALUE_INPUT_TYPES
from orbit_controller import orbit_script_controls
from animation_assets import validated_clips,pose_at

class PreviewGame:
    def __init__(self,document,base,scene_index=None,shared_variables=None):
        self.doc=copy.deepcopy(document)
        self.base=Path(base)
        self.scene_index=int(self.doc.get('active_scene',0) if scene_index is None else scene_index)
        if 'scenes' in self.doc:
            scene=self.doc['scenes'][self.scene_index]
            for k in ('objects','camera','scripts','physics','animations','hud','skybox'):
                self.doc[k]=copy.deepcopy(scene.get(k,[] if k in ('objects','animations') else {}))
        compile_graph(self.doc)
        self.arrays={name:list(map(float,values)) for name,values in self.doc.get('arrays',{}).items()}
        self.variables=({key:float(val) for key,val in self.doc.get('variables',{}).items()}
                        if shared_variables is None else dict(shared_variables))
        self.requested_scene=None
        graph=expanded_graph(self.doc)
        self.nodes={str(n['id']):n for n in graph.get('nodes',[])}
        self.edges={(str(e['from']),e.get('port','next')):str(e['to']) for e in graph.get('links',[])}
        self.data_edges={(str(e['to']),e['input']):str(e['from']) for e in graph.get('data_links',[])}
        self.prev=set()
        self._eval_scope={}
        self.functions={str(n.get('params',{}).get('function','')):n for n in self.nodes.values() if n['type']=='FunctionDefinition'}
        self._exec_budget=8192
        self.orbit_directional_nodes=orbit_script_controls(self.doc)
        # Persist the orbit elevation separately from the renderer's view
        # pitch: SG3D's camera transform takes the opposite sign.
        orbit=(self.doc.get('camera') or {}).get('orbit') or {}
        self.orbit_elevation_units=(max(-52,min(52,round(float(orbit.get('pitch',-10))*256/360)))
                                    if orbit.get('enabled',False) else 0)
        if orbit.get('enabled',False):
            self.doc['camera']['rotation'][1]=-self.orbit_elevation_units*360/256
        self.previous_touch=set()
        self.bodies=[]
        for obj in self.doc['objects']:
            settings=obj.get('physics') or {}
            if 'half_extents' in settings:extent=[float(n) for n in settings['half_extents']]
            else:
                mesh=parse_obj(resolve(self.base,obj['mesh'])) if obj.get('mesh') else None
                sc=float(obj.get('scale',1))
                extent=[max(.125,(max(v[i] for v in mesh['vertices'])-min(v[i] for v in mesh['vertices']))*sc*.5)
                        for i in range(3)] if mesh else [0.5,0.5,0.5]
            self.bodies.append({'half':extent,'dynamic':bool(settings.get('dynamic',False)),
                                'solid':bool(settings.get('solid',False)),
                                'vy':0.0,'vx':0.0,'vz':0.0,'grounded':False})
        self.doc.setdefault('hud',[])
        self.frames=0
        self.clips=validated_clips(self.doc)
        self.clip_states={i:0 for i,c in enumerate(self.clips) if c['autoplay']}
        self.facing_targets=[None for _ in self.doc['objects']]
        self.vehicle_speeds=[0.0 for _ in self.doc['objects']]
        self.sound_events=[]  # PC preview logs effect requests but does not drive GBA audio.
        self._keys=set()
        self.execute_events('OnStart',set())

    def param(self,node,key,default=0):
        return node.get('params',{}).get(key,default)
    def number(self,node,key,default=0):
        src=self.data_edges.get((str(node['id']),key))
        if src is not None:return self.value(self.nodes[src])
        if node['type']=='IfVariable' and key=='a':return self.variables[str(self.param(node,'variable'))]
        if VALUE_INPUT_TYPES.get(node['type'],{}).get(key)=='vector':
            return (0.,0.,0.)
        raw=self.param(node,key,default)
        if isinstance(raw,bool):return float(raw)
        if isinstance(raw,str) and raw.lower() in ('true','false'):return 1.0 if raw.lower()=='true' else 0.0
        return float(raw)
    def value(self,node):
        typ=node['type']
        if typ=='Number':return self.number(node,'value')
        if typ=='Boolean':return self.number(node,'value')
        if typ=='MakeVector':return tuple(self.number(node,axis) for axis in ('x','y','z'))
        if typ=='GetObjectVector':return tuple(self.doc['objects'][self.objindex(node)]['position'])
        if typ=='GetCameraVector':return tuple(self.doc['camera']['position'])
        if typ in ('VectorAdd','VectorSubtract'):
            a=self.number(node,'a');b=self.number(node,'b')
            return tuple(a[i]+b[i] if typ=='VectorAdd' else a[i]-b[i] for i in range(3))
        if typ=='VectorScale':
            a=self.number(node,'vector');factor=self.number(node,'factor')
            return tuple(t*factor for t in a)
        if typ in ('VectorX','VectorY','VectorZ'):return self.number(node,'vector')['XYZ'.index(typ[-1])]
        if typ=='GetArray':
            a=self.arrays[str(self.param(node,'array',''))];i=math.floor(self.number(node,'index'))
            return a[i] if 0<=i<len(a) else 0
        if typ=='ArrayLength':return len(self.arrays[str(self.param(node,'array',''))])
        if typ=='EventValue':
            if 'event' not in self._eval_scope:raise ValueError('EventValue used outside custom event')
            return self._eval_scope['event']
        if typ=='EventObject':
            if 'event_object' not in self._eval_scope:raise ValueError('EventObject used outside custom event')
            return self._eval_scope['event_object']
        if typ=='ObjectRef':return self.objindex(node)
        if typ=='ObjectCount':return len(self.doc['objects'])
        if typ=='LoopObject':
            if 'object' not in self._eval_scope:raise ValueError('LoopObject outside ForEachObject')
            return self._eval_scope['object']
        if typ in ('WorldToLocal','LocalToWorld'):
            ref=self.objindex(node)
            v=self.number(node,'vector')
            if ref<0 or ref>=len(self.doc['objects']):return v
            obj=self.doc['objects'][ref];t=obj['position']
            yaw=math.radians(float(obj['rotation'][0]));pitch=math.radians(float(obj['rotation'][1]));sc=float(obj.get('scale',1)) or 1
            co=math.cos(yaw);si=math.sin(yaw);cp=math.cos(pitch);sp=math.sin(pitch)
            if typ=='WorldToLocal':
                dx,dy,dz=[v[k]-t[k] for k in range(3)]
                yy=cp*dy+sp*dz;zz=cp*dz-sp*dy
                return ((co*dx-si*zz)/sc,yy/sc,(si*dx+co*zz)/sc)
            x,y,z=[u*sc for u in v]
            xx=co*x+si*z;zz=co*z-si*x
            return (t[0]+xx,t[1]+cp*y-sp*zz,t[2]+sp*y+cp*zz)
        if typ=='CircleSegmentOverlap':
            point=self.number(node,'point');a=self.number(node,'a');b=self.number(node,'b');r=max(0,self.number(node,'radius'))
            dx=b[0]-a[0];dz=b[2]-a[2]
            t=max(0,min(1,((point[0]-a[0])*dx+(point[2]-a[2])*dz)/(dx*dx+dz*dz))) if (dx or dz) else 0
            return float((point[0]-a[0]-t*dx)**2+(point[2]-a[2]-t*dz)**2<=r*r)
        if typ=='SphereBoxOverlap':
            ref=self.objindex(node)
            if not 0<=ref<len(self.bodies):return 0.0
            p=self.number(node,'point');r=max(0,self.number(node,'radius'))
            center=self.doc['objects'][ref]['position'];half=self.bodies[ref]['half']
            ds=[max(abs(p[k]-center[k])-half[k],0) for k in range(3)]
            return float(sum(d*d for d in ds)<=r*r)
        if typ=='RaycastBox':
            ref=self.objindex(node)
            if not 0<=ref<len(self.bodies):return 0.0
            a=self.number(node,'a');b=self.number(node,'b')
            center=self.doc['objects'][ref]['position'];half=self.bodies[ref]['half'];low=0.;high=1.
            for k in range(3):
                delta=b[k]-a[k];minimum=center[k]-half[k];maximum=center[k]+half[k]
                if abs(delta)<1e-9:
                    if a[k]<minimum or a[k]>maximum:return 0.0
                else:
                    u=(minimum-a[k])/delta;v=(maximum-a[k])/delta
                    if u>v:u,v=v,u
                    low=max(low,u);high=min(high,v)
                    if low>high:return 0.0
            return 1.0
        if typ=='MathSinDeg':return math.sin(math.radians(self.number(node,'degrees')))
        if typ=='MathCosDeg':return math.cos(math.radians(self.number(node,'degrees')))
        if typ=='VectorDot':
            a=self.number(node,'a');b=self.number(node,'b');return sum(x*y for x,y in zip(a,b))
        if typ=='VectorDistanceSqXZ':
            a=self.number(node,'a');b=self.number(node,'b');return (a[0]-b[0])**2+(a[2]-b[2])**2
        if typ=='GetObjectHalfExtents':
            ref=self.objindex(node);return tuple(self.bodies[ref]['half']) if 0<=ref<len(self.bodies) else (0.,0.,0.)
        if typ=='ClosestPointBox':
            ref=self.objindex(node);p=self.number(node,'point')
            if not 0<=ref<len(self.bodies):return p
            center=self.doc['objects'][ref]['position'];half=self.bodies[ref]['half']
            return tuple(max(center[k]-half[k],min(center[k]+half[k],p[k])) for k in range(3))
        if typ=='CircleSegmentNormal':
            point=self.number(node,'point');a=self.number(node,'a');b=self.number(node,'b')
            dx=b[0]-a[0];dz=b[2]-a[2]
            t=max(0,min(1,((point[0]-a[0])*dx+(point[2]-a[2])*dz)/(dx*dx+dz*dz))) if (dx or dz) else 0
            nx=point[0]-a[0]-t*dx;nz=point[2]-a[2]-t*dz
            if not (nx or nz):nx,nz=-dz,dx
            m=max(abs(nx),abs(nz));return (nx/m,0.,nz/m) if m else (0.,0.,0.)
        if typ=='FunctionArgumentObject':return self._eval_scope.get('argo',0)
        if typ=='FunctionArgumentB':return self._eval_scope.get('argb',0)
        if typ=='FunctionArgumentVector':return self._eval_scope.get('argv',(0.,0.,0.))
        if typ=='FunctionArgument':return self._eval_scope.get('arg',0)
        if typ=='LoopIndex':return self._eval_scope.get('index',0)
        if typ=='KeyPressed':return 1 if str(self.param(node,'key','A')).upper() in self._keys-self.prev else 0
        if typ=='GetProperty':
            obj=self.doc['objects'][self.objindex(node)]
            return float((obj.get('properties') or {}).get(str(self.param(node,'property','speed')),0))
        if typ=='IsGrounded':return 1 if self.bodies[self.objindex(node)]['grounded'] else 0
        if typ in ('GetCameraX','GetCameraY','GetCameraZ'):
            return self.doc['camera']['position']['XYZ'.index(typ[-1])]
        if typ=='GetCameraYaw':return self.doc['camera']['rotation'][0]
        if typ=='GetObjectYaw':return self.doc['objects'][self.objindex(node)]['rotation'][0]
        if typ.startswith('GetVelocity'):
            return self.bodies[self.objindex(node)]['v'+typ[-1].lower()]
        if typ=='NonZero':return 1 if self.number(node,'value')!=0 else 0
        if typ=='MathAbs':return abs(self.number(node,'value'))
        if typ=='MathMin':return min(self.number(node,'a'),self.number(node,'b'))
        if typ=='MathMax':return max(self.number(node,'a'),self.number(node,'b'))
        if typ=='Compare':
            a=self.number(node,'a');b=self.number(node,'b');op=str(self.param(node,'op','>='))
            return float({'==':a==b,'!=':a!=b,'<':a<b,'<=':a<=b,'>':a>b,'>=':a>=b}[op])
        if typ=='LogicAnd':return float(bool(self.number(node,'a')) and bool(self.number(node,'b')))
        if typ=='LogicOr':return float(bool(self.number(node,'a')) or bool(self.number(node,'b')))
        if typ=='LogicNot':return float(not self.number(node,'value'))
        if typ=='GetKeyHeld':return 1 if str(self.param(node,'key','A')).upper() in self._keys else 0
        if typ=='MathClamp':return max(self.number(node,'min'),min(self.number(node,'max'),self.number(node,'value')))
        if typ=='GetVariable':return self.variables[str(self.param(node,'variable'))]
        if typ.startswith('GetObject'):
            i=self.objindex(node)
            return self.doc['objects'][i]['position']['XYZ'.index(typ[-1])]
        a=self.number(node,'a');b=self.number(node,'b')
        if typ=='MathAdd':return a+b
        if typ=='MathSubtract':return a-b
        if typ=='MathMultiply':return a*b
        if typ=='MathDivide':return (a/b) if b else 0
        raise ValueError('Unsupported data node '+typ)
    def objindex(self,node,key='object'):
        source=self.data_edges.get((str(node['id']),key))
        if source is not None:return int(self.value(self.nodes[source]))
        return int(self.param(node,key))
    def touch(self,a,b):
        if a==b or a<0 or b<0 or a>=len(self.bodies) or b>=len(self.bodies):return False
        pa=self.doc['objects'][a]['position'];pb=self.doc['objects'][b]['position']
        ea=self.bodies[a]['half'];eb=self.bodies[b]['half']
        return all(abs(pa[i]-pb[i])<=ea[i]+eb[i]+2/256 for i in range(3))
    def ground_contact(self,index):
        body=self.bodies[index];p=self.doc['objects'][index]['position'];h=body['half']
        for j,other in enumerate(self.bodies):
            if j==index or not other['solid']:continue
            q=self.doc['objects'][j]['position'];e=other['half']
            if abs(p[0]-q[0])>=h[0]+e[0] or abs(p[2]-q[2])>=h[2]+e[2]:continue
            if abs(p[1]-h[1]-(q[1]+e[1]))<=2/256:return True
        return False
    def axis_move(self,index,axis,delta):
        if not delta:return
        body=self.bodies[index];p=self.doc['objects'][index]['position'];end=p[axis]+delta
        for j,other in enumerate(self.bodies):
            if j==index or not other['solid']:continue
            q=self.doc['objects'][j]['position']
            if any(abs(p[k]-q[k])>=body['half'][k]+other['half'][k]
                   for k in range(3) if k!=axis):continue
            r=body['half'][axis]+other['half'][axis]
            if delta>0 and p[axis]+r<=q[axis] and end+r>q[axis]:end=q[axis]-r
            if delta<0 and p[axis]-r>=q[axis] and end-r<q[axis]:end=q[axis]+r
        if end!=p[axis]+delta:
            if axis==1:body['vy']=0
            elif axis==0:body['vx']=0
            else:body['vz']=0
        p[axis]=round(end*256)/256
    def move(self,index,x,y,z):
        for axis,delta in ((0,x),(2,z),(1,y)):self.axis_move(index,axis,delta)
    def execute_events(self,kind,keys):
        for node in list(self.nodes.values()):
            if node['type']!=kind:continue
            if kind=='OnKeyHeld' and str(self.param(node,'key','A')).upper() not in keys:continue
            if kind=='OnKeyPressed':
                key=str(self.param(node,'key','A')).upper()
                if key not in keys or key in self.prev:continue
            if kind=='OnCollision':
                a=self.objindex(node);b=self.objindex(node,'other')
                if not self.touch(a,b) or (a,b) in self.previous_touch:continue
            self.execute(self.edges.get((str(node['id']),'next')),keys)
    def execute(self,id_,keys,scope=None,function_chain=()):
        if id_ is None:return
        self._exec_budget-=1
        if self._exec_budget<0:raise RuntimeError('Node execution budget exceeded (possible run-away graph)')
        self._eval_scope=scope or {}
        node=self.nodes[id_];kind=node['type'];p=lambda n,d=0:self.param(node,n,d)
        if kind=='FunctionDefinition':return
        if kind=='ForEachObject':
            parent=scope or {}
            tag=str(p('property','')).strip()
            for i,obj in enumerate(self.doc['objects']):
                if tag and float((obj.get('properties') or {}).get(tag,0))<1:continue
                new_scope=dict(parent);new_scope['object']=i;new_scope['index']=i
                result=self.execute(self.edges.get((id_,'body')),keys,new_scope,function_chain)
                if isinstance(result,tuple):
                    if result[0]=='return':return result
                    if result[0]=='break':break
            return self.execute(self.edges.get((id_,'next')),keys,parent,function_chain)
        if kind=='Repeat' or kind=='WhileBool':
            parent=scope or {}
            count=max(0,min(64,int(self.number(node,'count')))) if kind=='Repeat' else 64
            for i in range(count):
                new_scope=dict(parent);new_scope['index']=i
                self._eval_scope=new_scope
                if kind=='WhileBool' and not self.number(node,'value'):break
                result=self.execute(self.edges.get((id_,'body')),keys,new_scope,function_chain)
                if isinstance(result,tuple):
                    if result[0]=='return':return result
                    if result[0]=='break':break
            return self.execute(self.edges.get((id_,'next')),keys,parent,function_chain)
        if kind=='EmitEvent':
            ename=str(p('event',''))
            eventvalue=self.number(node,'value')
            ref_source=self.data_edges.get((id_,'object'))
            objref=int(self.value(self.nodes[ref_source])) if ref_source is not None else -1
            for listener in self.nodes.values():
                if listener['type']=='OnEvent' and str(self.param(listener,'event',''))==ename:
                    new_scope=dict(scope or {});new_scope.update({'event':eventvalue,'event_object':objref})
                    result=self.execute(self.edges.get((str(listener['id']),'next')),keys,new_scope,function_chain)
                    if isinstance(result,tuple) and result[0]=='return':return result
            return self.execute(self.edges.get((id_,'next')),keys,scope,function_chain)
        if kind=='BreakLoop':return ('break',)
        if kind=='ReturnFunction':return ('return',self.number(node,'value'))
        if kind=='CallFunction':
            name=str(p('function',''))
            if name in function_chain:raise ValueError('Recursive node function '+name)
            function=self.functions.get(name)
            if not function:raise ValueError('Unknown node function '+name)
            val=self.number(node,'argument')
            argb=self.number(node,'argument_b')
            argv=self.number(node,'argument_vector')
            argo=self.number(node,'argument_object') if (id_,'argument_object') in self.data_edges else -1
            ret=self.execute(self.edges.get((str(function['id']),'next')),keys,{'arg':val,'argb':argb,'argv':argv,'argo':argo},function_chain+(name,))
            variable=str(p('result','')).strip()
            if variable:self.variables[variable]=ret[1] if isinstance(ret,tuple) and ret[0]=='return' else 0
            return self.execute(self.edges.get((id_,'next')),keys,scope,function_chain)
        if kind.startswith('If'):
            if kind=='IfGrounded':yes=self.bodies[self.objindex(node)]['grounded']
            elif kind=='IfTouching':yes=self.touch(self.objindex(node),self.objindex(node,'other'))
            elif kind=='IfNearObject':
                a=self.doc['objects'][self.objindex(node)]['position'];b=self.doc['objects'][self.objindex(node,'other')]['position']
                yes=sum((a[i]-b[i])**2 for i in range(3))<=self.number(node,'radius')**2
            elif kind=='IfKeyHeld':yes=str(p('key','A')).upper() in keys
            elif kind=='IfBool':yes=bool(self.number(node,'value'))
            else:
                v=self.number(node,'a');x=self.number(node,'value')
                op=str(p('op','>='))
                yes={'==':v==x,'!=':v!=x,'<':v<x,'<=':v<=x,'>':v>x,'>=':v>=x}[op]
            return self.execute(self.edges.get((id_,'true' if yes else 'false')),keys,scope,function_chain)
        if kind in ('MoveObject','SetObjectPosition','RotateObject','MovePlayer','MoveRelative','DriveVehicle','SetVelocity','SetVelocity3D','JumpObject','FollowObject','MoveLocal','SetObjectRotation','SetObjectScale'):
            idx=self.objindex(node);obj=self.doc['objects'][idx];body=self.bodies[idx]
        if kind=='MoveObject':
            x,y,z=[self.number(node,a) for a in ('x','y','z')]
            if str(node['id']) in self.orbit_directional_nodes:
                yaw=math.radians(self.doc['camera']['rotation'][0]);x,z=x*math.cos(yaw)+z*math.sin(yaw),z*math.cos(yaw)-x*math.sin(yaw)
            self.move(idx,x,y,z)
        elif kind=='SetObjectPosition':
            for i,a in enumerate(('x','y','z')):obj['position'][i]=self.number(node,a)
        elif kind=='RotateObject':
            for i,a in enumerate(('yaw','pitch')):obj['rotation'][i]=(obj['rotation'][i]+self.number(node,a))%360
        elif kind=='MovePlayer':
            x,z=self.number(node,'x'),self.number(node,'z')
            if str(node['id']) in self.orbit_directional_nodes:
                yaw=math.radians(self.doc['camera']['rotation'][0]);x,z=x*math.cos(yaw)+z*math.sin(yaw),z*math.cos(yaw)-x*math.sin(yaw)
            self.move(idx,x,0,z)
        elif kind=='MoveLocal':
            yaw=math.radians(obj['rotation'][0]);x=self.number(node,'x');z=self.number(node,'z')
            self.move(idx,x*math.cos(yaw)+z*math.sin(yaw),0,z*math.cos(yaw)-x*math.sin(yaw))
        elif kind=='SetObjectRotation':
            obj['rotation']=[self.number(node,'yaw')%360,self.number(node,'pitch')%360]
        elif kind=='SetObjectScale':obj['scale']=self.number(node,'value')
        elif kind=='MoveRelative':
            yaw=math.radians(self.doc['camera']['rotation'][0]);x=self.number(node,'x');z=self.number(node,'z')
            self.move(idx,x*math.cos(yaw)+z*math.sin(yaw),0,z*math.cos(yaw)-x*math.sin(yaw))
        elif kind=='DriveVehicle':
            acc=self.number(node,'acceleration');drag=self.number(node,'drag');cap=self.number(node,'maxspeed')
            speed=self.vehicle_speeds[idx]
            if 'UP' in keys:speed+=acc
            elif 'DOWN' in keys:speed-=acc
            elif speed>0:speed=max(0,speed-drag)
            elif speed<0:speed=min(0,speed+drag)
            speed=max(-cap/2,min(cap,speed));self.vehicle_speeds[idx]=speed
            turn=self.number(node,'turn')*360/256
            if speed<0:turn=-turn
            if speed:
                if 'LEFT' in keys:obj['rotation'][0]-=turn
                if 'RIGHT' in keys:obj['rotation'][0]+=turn
            yaw=math.radians(obj['rotation'][0]);self.move(idx,speed*math.sin(yaw),0,speed*math.cos(yaw))
        elif kind=='JumpObject':
            if body['dynamic'] and body['grounded']:
                body['vy']=self.number(node,'impulse',.36);body['grounded']=False
        elif kind in ('SetVelocity','SetVelocity3D'):
            body['vx']=self.number(node,'x');body['vz']=self.number(node,'z')
            if kind=='SetVelocity3D':body['vy']=self.number(node,'y')
        elif kind=='FollowObject':
            self.doc['camera']['position']=[obj['position'][i]+self.number(node,a) for i,a in enumerate(('x','y','z'))]
        elif kind=='SetCameraPosition':
            self.doc['camera']['position']=[self.number(node,a) for a in ('x','y','z')]
        elif kind=='SetCameraRotation':
            self.doc['camera']['rotation']=[self.number(node,a)%360 for a in ('yaw','pitch')]
        elif kind=='MoveCamera':
            for i,a in enumerate(('x','y','z')):self.doc['camera']['position'][i]+=self.number(node,a)
        elif kind=='RotateCamera':
            for i,a in enumerate(('yaw','pitch')):self.doc['camera']['rotation'][i]+=self.number(node,a)
        elif kind=='MoveObjectVector':self.move(self.objindex(node),*self.number(node,'vector'))
        elif kind=='SetObjectVector':self.doc['objects'][self.objindex(node)]['position']=list(self.number(node,'vector'))
        elif kind=='SetArray':
            array=self.arrays[str(p('array',''))];i=math.floor(self.number(node,'index'))
            if 0<=i<len(array):array[i]=self.number(node,'value')
        elif kind=='SetProperty':
            obj=self.doc['objects'][self.objindex(node)]
            obj.setdefault('properties',{})[str(p('property','speed'))]=self.number(node,'value')
        elif kind=='SetVariable':self.variables[str(p('variable'))]=self.number(node,'value')
        elif kind=='AddVariable':self.variables[str(p('variable'))]+=self.number(node,'value')
        elif kind in ('PlayAnimation','StopAnimation'):
            target=str(p('animation','0'))
            try:clip=int(target)
            except ValueError:clip=next((i for i,c in enumerate(self.clips) if c['name']==target),-1)
            if not 0<=clip<len(self.clips):raise ValueError('Missing animation '+target)
            if kind=='PlayAnimation':self.clip_states[clip]=0
            else:self.clip_states.pop(clip,None)
        elif kind=='PlaySound':
            idx=str(p('sound','0'))
            try:snd=self.doc.get('sounds',[])[int(idx)]['name']
            except (ValueError,IndexError):snd=idx
            self.sound_events.append((self.frames,snd))
        elif kind=='StopSound':self.sound_events.append((self.frames,'<stop>'))
        elif kind in ('SetUIValue','ShowUI','HideUI'):
            item=self.doc['hud'][int(p('element','0'))]
            if kind=='SetUIValue':item['value']=int(self.number(node,'value'))
            else:item['visible']=kind=='ShowUI'
        elif kind=='LoadScene':
            target=str(p('scene','0'))
            try:self.requested_scene=int(target)
            except ValueError:
                names=[s['name'] for s in self.doc.get('scenes',[])]
                if target not in names:raise ValueError('Unknown scene '+target)
                self.requested_scene=names.index(target)
        else:raise ValueError('Unsupported PC node '+kind)
        return self.execute(self.edges.get((id_,'next')),keys,scope,function_chain)
    def depenetrate(self,index):
        body=self.bodies[index];p=self.doc['objects'][index]['position'];h=body['half']
        for _ in range(4):
            choice=None
            for j,other in enumerate(self.bodies):
                if j==index or not other['solid']:continue
                q=self.doc['objects'][j]['position'];hh=other['half']
                if not all(abs(p[a]-q[a])<h[a]+hh[a] for a in range(3)):continue
                for a in range(3):
                    depth=h[a]+hh[a]-abs(p[a]-q[a])
                    if choice is None or depth<choice[0]:
                        choice=(depth,a,depth if p[a]>=q[a] else -depth)
            if choice is None:break
            _,axis,delta=choice
            p[axis]=round((p[axis]+delta)*256)/256
            if axis==1:body['vy']=0;body['grounded']=delta>0
            else:body['vx' if axis==0 else 'vz']=0

    def _turn_to_movement(self, index, initial):
        obj=self.doc['objects'][index]
        if not obj.get('face_movement',False):return
        dx=obj['position'][0]-initial[0]
        dz=obj['position'][2]-initial[2]
        # Runtime positions are 8.8 fixed; use those quantized displacements.
        fx=round(dx*256);fz=round(dz*256)
        if abs(fx)>=2 or abs(fz)>=2:
            self.facing_targets[index]=(round(math.atan2(fx,fz)*128/math.pi)+
                                        round(float(obj.get('facing_offset',0))*256/360)) & 255
        goal=self.facing_targets[index]
        if goal is None:return
        current=round(obj['rotation'][0]*256/360)&255
        rate=float(obj.get('facing_smooth',0.25))
        if not 0 < rate <= 1:raise ValueError('facing_smooth must be in (0,1]')
        strength=min(255,max(1,round(rate*255)))
        diff=((goal-current+128)&255)-128
        if diff==0:return
        step=abs(diff) if strength==255 else max(1,(abs(diff)*strength+127)>>8)
        current=(current+(step if diff>=0 else -step)) & 255
        obj['rotation'][0]=current*360/256

    def tick(self,keys=()):
        self._exec_budget=8192
        initial_positions=[obj['position'][:] for obj in self.doc['objects']]
        keys=set(keys);self._keys=keys
        orbit=(self.doc.get('camera',{}).get('orbit') or {})
        if orbit.get('enabled',False):
            target=int(orbit.get('target',self.doc['camera'].get('follow',0)))
            rot=self.doc['camera']['rotation']
            if orbit.get('sync_yaw',False):
                rot[0]=self.doc['objects'][target]['rotation'][0]
            else:
                step=max(1,round(float(orbit.get('turn_speed',2))*256/360))*360/256
                if 'L' in keys and 'R' not in keys:rot[0]-=step
                if 'R' in keys and 'L' not in keys:rot[0]+=step
            if 'SELECT' in keys and 'UP' in keys and self.orbit_elevation_units<52:
                self.orbit_elevation_units+=1
            if 'SELECT' in keys and 'DOWN' in keys and self.orbit_elevation_units>-52:
                self.orbit_elevation_units-=1
            rot[1]=-self.orbit_elevation_units*360/256
        for kind in ('OnUpdate','OnKeyHeld','OnKeyPressed'):
            self.execute_events(kind,keys)
        settings=self.doc.get('physics') or {}
        gravity=float(settings.get('gravity',-.025))
        terminal=float(settings.get('terminal_velocity',-.7))
        for i,body in enumerate(self.bodies):
            if not body['dynamic']:continue
            self.depenetrate(i)
            body['grounded']=self.ground_contact(i)
            if not body['grounded']:body['vy']=max(terminal,body['vy']+gravity)
            elif body['vy']<0:body['vy']=0
            self.move(i,body['vx'],body['vy'],body['vz'])
            body['grounded']=self.ground_contact(i)
            if body['grounded'] and body['vy']<0:body['vy']=0
        self.execute_events('OnCollision',keys)
        self.previous_touch={(a,b) for a in range(len(self.bodies)) for b in range(len(self.bodies)) if self.touch(a,b)}
        follow=self.doc.get('camera',{}).get('follow')
        if follow is not None and not (self.doc.get('camera',{}).get('orbit') or {}).get('enabled',False):
            offset=self.doc['camera'].get('follow_offset',[0,2,-7]);pos=self.doc['objects'][int(follow)]['position']
            self.doc['camera']['position']=[pos[i]+offset[i] for i in range(3)]
        if orbit.get('enabled',False):
            target=int(orbit.get('target',follow if follow is not None else 0))
            cam=self.doc['camera'];rot=cam['rotation']
            if orbit.get('auto_move',True) and not self.orbit_directional_nodes and 'SELECT' not in keys:
                speed=float(orbit.get('move_speed',.09))
                dx=speed*(('RIGHT' in keys)-('LEFT' in keys));dz=speed*(('UP' in keys)-('DOWN' in keys))
                yaw=math.radians(rot[0]);self.move(target,dx*math.cos(yaw)+dz*math.sin(yaw),0,dz*math.cos(yaw)-dx*math.sin(yaw))
            r=float(orbit.get('distance',6));h=float(orbit.get('height',1.5));yaw=math.radians(rot[0]);pitch=math.radians(self.orbit_elevation_units*360/256);pos=self.doc['objects'][target]['position']
            cam['position']=[pos[0]-r*math.cos(pitch)*math.sin(yaw),pos[1]+h-r*math.sin(pitch),pos[2]-r*math.cos(pitch)*math.cos(yaw)]
        for i,frame in list(self.clip_states.items()):
            clip=self.clips[i];self.doc['objects'][clip['object']].update(pose_at(clip,frame))
            if frame+1<clip['duration']:self.clip_states[i]=frame+1
            elif clip['loop']:self.clip_states[i]=0
            else:self.clip_states.pop(i,None)
        for i,initial in enumerate(initial_positions):self._turn_to_movement(i,initial)
        self.prev=keys
        self.frames+=1
