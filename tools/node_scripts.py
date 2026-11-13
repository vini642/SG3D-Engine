"""SG3D v0.8 visual node graphs -> deterministic, freestanding GBA C.

Flow links connect output ports to one target input; no arbitrary C/eval is
accepted. Execution graphs are cycle-free; bounded loop nodes and reusable functions provide structured repetition.
"""
import re
from orbit_controller import orbit_script_controls

NODE_TYPES = {
    'OnStart': ('Event: Start', ['next']),
    'OnUpdate': ('Event: Every frame', ['next']),
    'OnKeyHeld': ('Event: Key held', ['next']),
    'OnKeyPressed': ('Event: Key pressed', ['next']),
    'IfKeyHeld': ('Branch: Key held?', ['true', 'false']),
    'IfVariable': ('Branch: Compare variable', ['true', 'false']),
    'MoveObject': ('Move object (delta)', ['next']),
    'RotateObject': ('Rotate object (delta)', ['next']),
    'SetObjectPosition': ('Set object position', ['next']),
    'MoveCamera': ('Move camera (delta)', ['next']),
    'RotateCamera': ('Rotate camera (delta)', ['next']),
    'SetVariable': ('Set variable', ['next']),
    'AddVariable': ('Add to variable', ['next']),
    'MovePlayer': ('Move character (collision)', ['next']),
    'MoveRelative': ('Move relative to camera', ['next']),
    'DriveVehicle': ('Drive racing vehicle (D-pad)', ['next']),
    'IfNearObject': ('Branch: Object within radius', ['true','false']),
    'JumpObject': ('Jump if grounded', ['next']),
    'SetVelocity': ('Set velocity', ['next']),
    'IfGrounded': ('Branch: Grounded?', ['true','false']),
    'IfTouching': ('Branch: Touching?', ['true','false']),
    'OnCollision': ('Event: Collision begins', ['next']),
    'FollowObject': ('Camera follow target', ['next']),
    'LoadScene': ('Load scene', ['next']),
    'PlayAnimation': ('Play animation', ['next']),
    'StopAnimation': ('Stop animation', ['next']),
    'PlaySound': ('Play WAV effect', ['next']),
    'StopSound': ('Stop WAV effect', ['next']),
    'SetUIValue': ('UI: Set counter / bar', ['next']),
    'ShowUI': ('UI: Show element', ['next']),
    'HideUI': ('UI: Hide element', ['next']),
    'GetKeyHeld': ('Value: Key held (0/1)', []),
    'MathClamp': ('Math: Clamp value', []),
    'Number': ('Value: Number', []),
    'GetVariable': ('Value: Get variable', []),
    'MathAdd': ('Math: Add', []),
    'MathSubtract': ('Math: Subtract', []),
    'MathMultiply': ('Math: Multiply', []),
    'MathDivide': ('Math: Divide', []),
    'GetProperty': ('Value: Object property', []),
    'SetProperty': ('Set object property', ['next']),
    'GetObjectX': ('Value: Object X', []),
    'GetObjectY': ('Value: Object Y', []),
    'GetObjectZ': ('Value: Object Z', []),
    'Boolean': ('Value: True / False', []),
    'Compare': ('Boolean: Compare numbers', []),
    'LogicAnd': ('Boolean: AND', []),
    'LogicOr': ('Boolean: OR', []),
    'LogicNot': ('Boolean: NOT', []),
    'IfBool': ('Branch: Boolean', ['true','false']),
    'Repeat': ('Loop: Repeat (max 64)', ['body','next']),
    'WhileBool': ('Loop: While true (max 64)', ['body','next']),
    'LoopIndex': ('Value: Current loop index', []),
    'BreakLoop': ('Loop: Break', []),
    'FunctionDefinition': ('Function: Define', ['next']),
    'FunctionArgument': ('Value: Function argument', []),
    'CallFunction': ('Function: Call', ['next']),
    'ReturnFunction': ('Function: Return', []),
    'MoveLocal': ('Move relative to object yaw', ['next']),
    'SetCameraPosition': ('Camera: Set position', ['next']),
    'SetCameraRotation': ('Camera: Set rotation', ['next']),
    'SetObjectRotation': ('Object: Set rotation', ['next']),
    'SetObjectScale': ('Object: Set scale', ['next']),
    'GetCameraX': ('Value: Camera X', []),
    'GetCameraY': ('Value: Camera Y', []),
    'GetCameraZ': ('Value: Camera Z', []),
    'GetCameraYaw': ('Value: Camera yaw (deg)', []),
    'GetObjectYaw': ('Value: Object yaw (deg)', []),
    'GetVelocityX': ('Value: Velocity X', []),
    'GetVelocityY': ('Value: Velocity Y', []),
    'GetVelocityZ': ('Value: Velocity Z', []),
    'IsGrounded': ('Boolean: Object grounded', []),
    'KeyPressed': ('Boolean: Key just pressed', []),
    'NonZero': ('Boolean: Number not zero', []),
    'MathAbs': ('Math: Absolute', []),
    'MathMin': ('Math: Minimum', []),
    'MathMax': ('Math: Maximum', []),
    'SetVelocity3D': ('Physics: Set XYZ velocity', ['next']),
    'MakeVector': ('Vector: Make XYZ', []),
    'GetObjectVector': ('Vector: Object position', []),
    'GetCameraVector': ('Vector: Camera position', []),
    'VectorAdd': ('Vector: Add', []),
    'VectorSubtract': ('Vector: Subtract', []),
    'VectorScale': ('Vector: Multiply by scalar', []),
    'VectorX': ('Vector: X component', []),
    'VectorY': ('Vector: Y component', []),
    'VectorZ': ('Vector: Z component', []),
    'MoveObjectVector': ('Object: Move by vector', ['next']),
    'SetObjectVector': ('Object: Set position vector', ['next']),
    'GetArray': ('Array: Read number', []),
    'ArrayLength': ('Array: Length', []),
    'SetArray': ('Array: Write number', ['next']),
    'ObjectRef': ('Object: Reference', []),
    'ObjectCount': ('Object: Count', []),
    'LoopObject': ('Object: Current in ForEach', []),
    'ForEachObject': ('Loop: For each object', ['body','next']),
    'WorldToLocal': ('Transform: World to local', []),
    'LocalToWorld': ('Transform: Local to world', []),
    'CircleSegmentOverlap': ('Collision: Circle vs segment (XZ)', []),
    'SphereBoxOverlap': ('Collision: Sphere vs object box', []),
    'RaycastBox': ('Collision: Ray vs object box', []),
    'FunctionArgumentB': ('Function: Argument B', []),
    'FunctionArgumentVector': ('Function: Vector argument', []),
    'FunctionArgumentObject': ('Function: Object argument', []),
    'MathSinDeg': ('Math: Sin degrees', []),
    'MathCosDeg': ('Math: Cos degrees', []),
    'VectorDot': ('Vector: Dot product', []),
    'VectorDistanceSqXZ': ('Vector: Distance squared XZ', []),
    'ClosestPointBox': ('Collision: Closest point on box', []),
    'GetObjectHalfExtents': ('Collision: Box half extents', []),
    'CircleSegmentNormal': ('Collision: Segment contact direction', []),
    'OnEvent': ('Event: Custom message', ['next']),
    'EmitEvent': ('Event: Send message', ['next']),
    'EventValue': ('Value: Event number', []),
    'EventObject': ('Object: Event object', []),


}
EVENTS = {'OnStart', 'OnUpdate', 'OnKeyHeld', 'OnKeyPressed', 'OnCollision', 'FunctionDefinition','OnEvent'}
KEYS = {'A':'A', 'B':'B', 'START':'START', 'SELECT':'SEL',
        'UP':'UP','DOWN':'DOWN','LEFT':'LEFT','RIGHT':'RIGHT','L':'L','R':'R'}
PARAMS = {
    'OnStart': [], 'OnUpdate': [], 'OnEvent':[('event','name')],
    'OnKeyHeld': [('key','key')], 'OnKeyPressed':[('key','key')],
    'IfKeyHeld':[('key','key')],
    'IfVariable':[('variable','variable'),('op','operator'),('value','number')],
    'MoveObject':[('object','object'),('x','number'),('y','number'),('z','number')],
    'RotateObject':[('object','object'),('yaw','number'),('pitch','number')],
    'SetObjectPosition':[('object','object'),('x','number'),('y','number'),('z','number')],
    'MoveCamera':[('x','number'),('y','number'),('z','number')],
    'RotateCamera':[('yaw','number'),('pitch','number')],
    'SetVariable':[('variable','variable'),('value','number')],
    'AddVariable':[('variable','variable'),('value','number')],
    'MovePlayer':[('object','object'),('x','number'),('z','number')],
    'MoveRelative':[('object','object'),('x','number'),('z','number')],
    'DriveVehicle':[('object','object'),('acceleration','number'),('maxspeed','number'),('drag','number'),('turn','number')],
    'IfNearObject':[('object','object'),('other','object'),('radius','number')],
    'JumpObject':[('object','object'),('impulse','number')],
    'SetVelocity':[('object','object'),('x','number'),('z','number')],
    'IfGrounded':[('object','object')],
    'IfTouching':[('object','object'),('other','object')],
    'OnCollision':[('object','object'),('other','object')],
    'FollowObject':[('object','object'),('x','number'),('y','number'),('z','number')],
    'LoadScene':[('scene','scene')],
    'PlayAnimation':[('animation','animation')],
    'StopAnimation':[('animation','animation')],
    'PlaySound':[('sound','sound')],
    'StopSound':[],
    'SetUIValue':[('element','ui'),('value','number')],
    'ShowUI':[('element','ui')],
    'HideUI':[('element','ui')],
    'Number':[('value','number')],
    'GetKeyHeld':[('key','key')],
    'MathClamp':[('value','number'),('min','number'),('max','number')],
    'GetVariable':[('variable','variable')],
    'MathAdd':[('a','number'),('b','number')],
    'MathSubtract':[('a','number'),('b','number')],
    'MathMultiply':[('a','number'),('b','number')],
    'MathDivide':[('a','number'),('b','number')],
    'GetProperty':[('object','object'),('property','name')],
    'SetProperty':[('object','object'),('property','name'),('value','number')],
    'GetObjectX':[('object','object')],
    'GetObjectY':[('object','object')],
    'GetObjectZ':[('object','object')],
    'Boolean':[('value','bool')],
    'Compare':[('a','number'),('b','number'),('op','operator')],
    'LogicAnd':[('a','bool'),('b','bool')],
    'LogicOr':[('a','bool'),('b','bool')],
    'LogicNot':[('value','bool')],
    'IfBool':[('value','bool')],
    'Repeat':[('count','number')],
    'WhileBool':[('value','bool')],
    'LoopIndex':[], 'BreakLoop':[],
    'FunctionDefinition':[('function','name')],
    'FunctionArgument':[],
    'CallFunction':[('function','name'),('argument','number'),('argument_b','number'),('argument_vector','vector'),('argument_object','object'),('result','variable_optional')],
    'ReturnFunction':[('value','number')],
    'MoveLocal':[('object','object'),('x','number'),('z','number')],
    'SetCameraPosition':[('x','number'),('y','number'),('z','number')],
    'SetCameraRotation':[('yaw','number'),('pitch','number')],
    'SetObjectRotation':[('object','object'),('yaw','number'),('pitch','number')],
    'SetObjectScale':[('object','object'),('value','number')],
    'GetCameraX':[], 'GetCameraY':[], 'GetCameraZ':[], 'GetCameraYaw':[],
    'GetObjectYaw':[('object','object')],
    'GetVelocityX':[('object','object')], 'GetVelocityY':[('object','object')], 'GetVelocityZ':[('object','object')],
    'IsGrounded':[('object','object')], 'KeyPressed':[('key','key')],
    'NonZero':[('value','number')],
    'MathAbs':[('value','number')], 'MathMin':[('a','number'),('b','number')], 'MathMax':[('a','number'),('b','number')],
    'SetVelocity3D':[('object','object'),('x','number'),('y','number'),('z','number')],
    'MakeVector':[('x','number'),('y','number'),('z','number')],
    'GetObjectVector':[('object','object')],
    'GetCameraVector':[],
    'VectorAdd':[('a','vector'),('b','vector')],
    'VectorSubtract':[('a','vector'),('b','vector')],
    'VectorScale':[('vector','vector'),('factor','number')],
    'VectorX':[('vector','vector')],
    'VectorY':[('vector','vector')],
    'VectorZ':[('vector','vector')],
    'MoveObjectVector':[('object','object'),('vector','vector')],
    'SetObjectVector':[('object','object'),('vector','vector')],
    'GetArray':[('array','array'),('index','number')],
    'ArrayLength':[('array','array')],
    'SetArray':[('array','array'),('index','number'),('value','number')],
    'ObjectRef':[('object','object')], 'ObjectCount':[], 'LoopObject':[],
    'ForEachObject':[('property','name_optional')],
    'WorldToLocal':[('object','object'),('vector','vector')],
    'LocalToWorld':[('object','object'),('vector','vector')],
    'CircleSegmentOverlap':[('point','vector'),('a','vector'),('b','vector'),('radius','number')],
    'SphereBoxOverlap':[('object','object'),('point','vector'),('radius','number')],
    'RaycastBox':[('object','object'),('a','vector'),('b','vector')],
    'FunctionArgumentB':[], 'FunctionArgumentVector':[], 'FunctionArgumentObject':[],
    'MathSinDeg':[('degrees','number')], 'MathCosDeg':[('degrees','number')],
    'VectorDot':[('a','vector'),('b','vector')],
    'VectorDistanceSqXZ':[('a','vector'),('b','vector')],
    'ClosestPointBox':[('object','object'),('point','vector')],
    'GetObjectHalfExtents':[('object','object')],
    'CircleSegmentNormal':[('point','vector'),('a','vector'),('b','vector')],
    'EmitEvent':[('event','name'),('value','number'),('object','object')],
    'EventValue':[], 'EventObject':[],


}
DEFAULTS = {'key':'A', 'object':'0', 'variable':'score', 'op':'>=', 'value':'1',
            'x':'0', 'y':'0', 'z':'0', 'yaw':'0', 'pitch':'0',
            'other':'1', 'impulse':'0.36', 'scene':'0', 'animation':'0', 'sound':'0', 'element':'0', 'a':'0', 'b':'0', 'acceleration':'0.025', 'maxspeed':'0.3', 'drag':'0.012', 'turn':'3', 'radius':'2', 'min':'0', 'max':'1', 'property':'speed', 'count':'4', 'function':'MyFunction', 'argument':'0', 'result':'', 'value':'1', 'array':'items', 'index':'0', 'vector':'0,0,0', 'factor':'1', 'event':'MyEvent', 'argument_b':'0', 'argument_object':'0', 'degrees':'0', 'argument_vector':'0,0,0', 'point':'0,0,0'}


VALUE_NODES = {'Number', 'GetVariable', 'MathAdd', 'MathSubtract',
               'MathMultiply', 'MathDivide', 'GetProperty', 'GetObjectX', 'GetObjectY', 'GetObjectZ', 'GetKeyHeld', 'MathClamp', 'Boolean','Compare','LogicAnd','LogicOr',
               'LogicNot','LoopIndex','FunctionArgument','GetCameraX','GetCameraY','GetCameraZ',
               'GetCameraYaw','GetObjectYaw','GetVelocityX','GetVelocityY','GetVelocityZ',
               'IsGrounded','KeyPressed','NonZero','MathAbs','MathMin','MathMax',
               'MakeVector','GetObjectVector','GetCameraVector','VectorAdd','VectorSubtract',
               'VectorScale','VectorX','VectorY','VectorZ','GetArray','ArrayLength',
               'ObjectRef','ObjectCount','LoopObject','WorldToLocal','LocalToWorld',
               'CircleSegmentOverlap','SphereBoxOverlap','RaycastBox','FunctionArgumentB','FunctionArgumentVector','FunctionArgumentObject',
               'MathSinDeg','MathCosDeg','VectorDot','VectorDistanceSqXZ',
               'ClosestPointBox','GetObjectHalfExtents','CircleSegmentNormal','EventValue','EventObject'}
VALUE_INPUTS = {kind:[key for key,form in PARAMS[kind] if form in ('number','bool','vector','object')]
                for kind in NODE_TYPES}
# IfVariable normally reads its named variable; a data input may override it.
VALUE_INPUTS['IfVariable']=['a','value']
VALUE_INPUTS['Number']=[]
VALUE_INPUTS['Boolean']=[]
VALUE_OUTPUT_TYPES = {k:('bool' if k in ('Boolean','Compare','LogicAnd','LogicOr','LogicNot','IsGrounded','KeyPressed','NonZero','GetKeyHeld','CircleSegmentOverlap','SphereBoxOverlap','RaycastBox') else
                'vector' if k in ('MakeVector','GetObjectVector','GetCameraVector','VectorAdd','VectorSubtract','VectorScale','WorldToLocal','LocalToWorld','FunctionArgumentVector','ClosestPointBox','GetObjectHalfExtents','CircleSegmentNormal') else
                'object' if k in ('ObjectRef','LoopObject','FunctionArgumentObject','EventObject') else 'number') for k in VALUE_NODES}
VALUE_INPUT_TYPES = {kind:{field:('bool' if form=='bool' else 'vector' if form=='vector' else 'object' if form=='object' else 'number') for field,form in PARAMS[kind] if form in ('bool','number','vector','object')} for kind in NODE_TYPES}
VALUE_INPUT_TYPES['IfVariable']={'a':'number','value':'number'}
VALUE_INPUTS['IfBool']=['value']; VALUE_INPUTS['WhileBool']=['value']


def default_node(node_type, node_id, x=50, y=50):
    if node_type not in NODE_TYPES:
        raise ValueError('Unknown node '+str(node_type))
    params={k:DEFAULTS[k] for k,_ in PARAMS[node_type]}
    if node_type=='ForEachObject':params['property']=''
    return {'id':str(node_id),'type':node_type,'x':int(x),'y':int(y),'params':params}


def _fixed(value, units=256):
    try:
        v=float(value)
    except (TypeError, ValueError):
        raise ValueError('Expected a number, got '+repr(value))
    if not -100000 <= v <= 100000 or v != v:
        raise ValueError('Out of range number '+str(value))
    return str(round(v * units))



def expanded_graph(doc):
    """Merge reusable, project-embedded function libraries into a scene graph.

    Component IDs are namespaced to avoid collisions with hand-authored nodes.
    A component contains functions and their value/action descendants, not
    independent OnUpdate or OnStart hooks. Older project schemas are unchanged.
    """
    import copy
    main=doc.get('scripts') or {}
    result={k:copy.deepcopy(main.get(k,[])) for k in ('nodes','links','data_links')}
    libraries=doc.get('node_components') or []
    if not isinstance(libraries,list) or len(libraries)>16:
        raise ValueError('At most 16 reusable node libraries are supported')
    seen=set()
    for comp_index,lib in enumerate(libraries):
        if not isinstance(lib,dict):raise ValueError('Invalid node library')
        name=str(lib.get('name','')).strip()
        if not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*',name):raise ValueError('Invalid node library name: '+name)
        if name in seen:raise ValueError('Duplicate node library name: '+name)
        seen.add(name)
        graph=lib.get('scripts') or {}
        ns=f'component_{comp_index}_{name}_'
        old_nodes=graph.get('nodes',[])
        if not isinstance(old_nodes,list):raise ValueError('Library nodes must be a list')
        lookup={}
        for n in old_nodes:
            kind=n.get('type')
            if kind in ('OnStart','OnUpdate','OnKeyHeld','OnKeyPressed','OnCollision'):
                raise ValueError(f'Library {name} contains a non-reusable event: {kind}')
            old=str(n.get('id',''))
            if not old or old in lookup:raise ValueError('Duplicate/empty library node ID')
            lookup[old]=ns+old
            new=copy.deepcopy(n);new['id']=lookup[old]
            result['nodes'].append(new)
        for edge_type in ('links','data_links'):
            for e in graph.get(edge_type,[]):
                if str(e.get('from')) not in lookup or str(e.get('to')) not in lookup:
                    raise ValueError('Library link refers to another graph: '+name)
                new=copy.deepcopy(e)
                new['from']=lookup[str(e['from'])];new['to']=lookup[str(e['to'])]
                result[edge_type].append(new)
    return result

def compile_graph(doc, with_physics=False):
    """Return (C declarations, on-start statements, per-frame statements)."""
    graph=expanded_graph(doc)
    orbit_nodes=orbit_script_controls(doc)
    orbit_enabled=bool(((doc.get('camera') or {}).get('orbit') or {}).get('enabled',False))
    # The exporter creates orbit_yaw when orbit is enabled; this value is now
    # updated before scripts, not one frame late like cam.yaw used to be.
    relative_yaw='orbit_yaw' if orbit_enabled else 'cam.yaw'
    nodes=graph.get('nodes',[])
    links=graph.get('links',[])
    data_links=graph.get('data_links',[])
    if not isinstance(nodes,list) or not isinstance(links,list) or not isinstance(data_links,list):
        raise ValueError('scripts.nodes/links must be arrays')
    if len(nodes)>256 or len(links)>512 or len(data_links)>512:
        raise ValueError('Graph limit: 256 nodes, 512 connections')
    names={}
    for node in nodes:
        id_=str(node.get('id',''))
        if not id_ or id_ in names:raise ValueError('Duplicate/empty node ID '+id_)
        if node.get('type') not in NODE_TYPES:raise ValueError('Unknown node type in '+id_)
        names[id_]=node
    outgoing={}
    incoming={}
    for edge in links:
        src,dst=str(edge.get('from','')),str(edge.get('to',''))
        port=edge.get('port','next')
        if src not in names or dst not in names:raise ValueError('Connection references missing node')
        if port not in NODE_TYPES[names[src]['type']][1]:raise ValueError('Bad output port '+str(port))
        if names[dst]['type'] in EVENTS or names[dst]['type'] in VALUE_NODES:
            raise ValueError('Cannot connect execution wire into an event/value node')
        if (src,port) in outgoing:raise ValueError('Only one wire per output port')
        if dst in incoming:raise ValueError('Only one incoming wire per action node (duplicate the node to reuse)')
        outgoing[src,port]=dst;incoming[dst]=src
    data_wires={}
    for e in data_links:
        src,dst=str(e.get('from','')),str(e.get('to',''))
        port=e.get('port','value');input_=e.get('input','')
        if src not in names or dst not in names:raise ValueError('Data connection references missing node')
        if names[src]['type'] not in VALUE_NODES or port!='value':
            raise ValueError('Data source must be a value node')
        if input_ not in VALUE_INPUTS[names[dst]['type']]:
            raise ValueError(f'Invalid value input {dst}.{input_}')
        required=VALUE_INPUT_TYPES[names[dst]['type']].get(input_,'number')
        provided=VALUE_OUTPUT_TYPES[names[src]['type']]
        if required=='bool' and provided!='bool':
            raise ValueError(f'{dst}.{input_} requires a boolean source (use Compare or NonZero)')
        if required=='vector' and provided!='vector':
            raise ValueError(f'{dst}.{input_} requires a vector source (use MakeVector)')
        if required=='object' and provided!='object':
            raise ValueError(f'{dst}.{input_} requires an object reference')
        if required=='number' and provided in ('vector','object'):
            raise ValueError(f'{dst}.{input_} requires a number source (use VectorX/Y/Z)')
        if (dst,input_) in data_wires:raise ValueError('Only one data wire per input')
        data_wires[dst,input_]=src
    def check_data_cycles(id_,visiting,checked):
        if id_ in visiting:raise ValueError('Cycle detected in value graph at '+id_)
        if id_ in checked:return
        for (target,_),source in data_wires.items():
            if target==id_:check_data_cycles(source,visiting|{id_},checked)
        checked.add(id_)
    checked=set()
    for nid in names:check_data_cycles(nid,set(),checked)
    raw_vars=doc.get('variables',{})
    if not isinstance(raw_vars,dict):raise ValueError('variables must be an object')
    if len(raw_vars)>32:raise ValueError('Maximum 32 script variables')
    decl=[];vars_={};arrays_={}
    raw_arrays=doc.get('arrays',{})
    if not isinstance(raw_arrays,dict) or len(raw_arrays)>16:raise ValueError('Maximum 16 numeric arrays')
    for name,values in raw_arrays.items():
        if not re.fullmatch('[A-Za-z_][A-Za-z_0-9]*',name):raise ValueError('Invalid array name: '+str(name))
        if not isinstance(values,list) or not 1<=len(values)<=64:raise ValueError('Array '+name+' must have 1–64 values')
        symbol='sga_'+name
        arrays_[name]=(symbol,len(values))
        decl.append('static int32_t '+symbol+'[] = {'+','.join(_fixed(x) for x in values)+'};')
    for name,initial in raw_vars.items():
        if not re.fullmatch('[A-Za-z_][A-Za-z_0-9]*',name):
            raise ValueError('Variable name must be a C-style identifier: '+name)
        var='sgv_'+name
        vars_[name]=var
        decl.append(f'static int32_t {var} = {_fixed(initial)}; /* fixed 8.8 */')
    objs=doc.get('objects',[])
    def param(node,key,default=None):return node.get('params',{}).get(key,default if default is not None else DEFAULTS.get(key,'0'))
    def objnum(node,field='object'):
        try:i=int(param(node,field))
        except (ValueError,TypeError):raise ValueError('Invalid object index in '+node['id'])
        if not (0<=i<len(objs)):raise ValueError(f'Node {node["id"]}: target object {i} not in scene')
        return i
    def objidx(node):
        return f'scene_objects[{objnum(node)}].transform'
    def ref_expr(node,field='object',scope=None):
        # 8.8 object reference, converted to signed integer index. Unlinked
        # static indices are validated at export time as before.
        if (node['id'],field) in data_wires:
            return f'({value_for(node,field,scope=scope)} >> 8)'
        return str(objnum(node,field))
    def dynamic_ref(node,field='object'):
        return (node['id'],field) in data_wires
    def variable(node):
        name=str(param(node,'variable'))
        if name not in vars_:raise ValueError(f'Node {node["id"]}: undefined variable {name!r} (add in Variables)')
        return vars_[name]
    def property_name(node):
        name=str(param(node,'property',''))
        i=objnum(node) if not dynamic_ref(node) else None
        if not re.fullmatch('[A-Za-z_][A-Za-z_0-9]*',name):
            raise ValueError(f'Node {node["id"]}: invalid property name')
        if not any(name in (o.get('properties') or {}) for o in (objs if i is None else [objs[i]])):
            raise ValueError(f'Node {node["id"]}: {name} is not declared on object {i}')
        return name
    def array_info(node):
        name=str(param(node,'array',''))
        if name not in arrays_:raise ValueError(f'Node {node["id"]}: missing numeric array {name!r}')
        return arrays_[name]
    def key(node):
        name=str(param(node,'key','A')).upper()
        if name not in KEYS:raise ValueError(f'Node {node["id"]}: unknown key {name}')
        return KEYS[name]
    def value_for(node,field,visiting=None,scope=None):
        """Produce a 24.8 fixed-point C expression. Validate value graph recursively."""
        visiting=set() if visiting is None else visiting
        nid=node['id']
        if nid in visiting:raise ValueError('Value cycle at '+nid)
        visiting=visiting|{nid}
        upstream=data_wires.get((nid,field))
        if upstream:return value_node(names[upstream],visiting,scope)
        if field=='a' and node['type']=='IfVariable':return variable(node)
        if field in ('argument_object',) and not upstream:return '-256' # optional: no object
        if node['type']=='EmitEvent' and field=='object' and not upstream:return '-256'
        if VALUE_INPUT_TYPES.get(node['type'],{}).get(field)=='object':return str(objnum(node,field)*256)
        if field=='value' and node['type']=='Boolean':return '256' if str(param(node,'value','1')).lower() in ('1','true','yes') else '0'
        if VALUE_INPUT_TYPES.get(node['type'],{}).get(field)=='vector':
            return 'sg3d_v3(0,0,0)'
        return _fixed(param(node,field,'0'))
    def value_node(node,visiting,scope=None):
        kind=node['type']
        if kind=='Number':return _fixed(param(node,'value'))
        if kind=='Boolean':return '256' if str(param(node,'value','1')).lower() in ('1','true','yes') else '0'
        if kind=='MakeVector':
            return f'sg3d_v3({value_for(node,"x",visiting,scope)},{value_for(node,"y",visiting,scope)},{value_for(node,"z",visiting,scope)})'
        if kind=='GetObjectVector':return f'sg3d_node_position(scene_objects,SCENE_COUNT,{ref_expr(node,scope=scope)})'
        if kind=='GetCameraVector':return 'sg3d_v3(cam.x,cam.y,cam.z)'
        if kind in ('VectorAdd','VectorSubtract'):
            fun='sg3d_vadd' if kind=='VectorAdd' else 'sg3d_vsub'
            return f'{fun}({value_for(node,"a",visiting,scope)},{value_for(node,"b",visiting,scope)})'
        if kind=='VectorScale':return f'sg3d_vscale({value_for(node,"vector",visiting,scope)},{value_for(node,"factor",visiting,scope)})'
        if kind in ('VectorX','VectorY','VectorZ'):
            return f'({value_for(node,"vector",visiting,scope)}.{kind[-1].lower()})'
        if kind=='GetArray':
            name,size=array_info(node)
            return f'sg3d_array_get({name},{size},{value_for(node,"index",visiting,scope)})'
        if kind=='ArrayLength':return str(array_info(node)[1]*256)
        if kind=='EventValue':
            if not scope or not scope.get('event'):raise ValueError('EventValue requires OnEvent called by EmitEvent')
            return scope['event']
        if kind=='EventObject':
            if not scope or not scope.get('event_object'):raise ValueError('EventObject requires OnEvent called by EmitEvent')
            return scope['event_object']
        if kind=='ObjectRef':return str(objnum(node)*256)
        if kind=='ObjectCount':return str(len(objs)*256)
        if kind=='LoopObject':
            if not scope or scope.get('object') is None:raise ValueError('LoopObject requires ForEachObject')
            return f'({scope["object"]} << 8)'
        if kind in ('WorldToLocal','LocalToWorld'):
            return f'sg3d_node_{"to_local" if kind=="WorldToLocal" else "to_world"}(scene_objects,SCENE_COUNT,{ref_expr(node,scope=scope)},{value_for(node,"vector",visiting,scope)})'
        if kind=='CircleSegmentOverlap':
            return f'(sg3d_node_circle_segment({value_for(node,"point",visiting,scope)},{value_for(node,"a",visiting,scope)},{value_for(node,"b",visiting,scope)},{value_for(node,"radius",visiting,scope)}) ? 256 : 0)'
        if kind=='SphereBoxOverlap':
            return f'(sg3d_node_sphere_box(physics_bodies,SCENE_COUNT,{ref_expr(node,scope=scope)},{value_for(node,"point",visiting,scope)},{value_for(node,"radius",visiting,scope)}) ? 256 : 0)'
        if kind=='RaycastBox':
            return f'(sg3d_node_raycast_box(physics_bodies,SCENE_COUNT,{ref_expr(node,scope=scope)},{value_for(node,"a",visiting,scope)},{value_for(node,"b",visiting,scope)}) ? 256 : 0)'
        if kind in ('MathSinDeg','MathCosDeg'):
            shift='64' if kind=='MathCosDeg' else '0'
            return f'(int32_t)sin_table[(uint8_t)(({value_for(node,"degrees",visiting,scope)}/360)+{shift})]'
        if kind=='VectorDot':
            return f'sg3d_node_dot({value_for(node,"a",visiting,scope)},{value_for(node,"b",visiting,scope)})'
        if kind=='VectorDistanceSqXZ':
            return f'sg3d_node_distance_sq_xz({value_for(node,"a",visiting,scope)},{value_for(node,"b",visiting,scope)})'
        if kind=='ClosestPointBox':
            return f'sg3d_node_closest_box(physics_bodies,SCENE_COUNT,{ref_expr(node,scope=scope)},{value_for(node,"point",visiting,scope)})'
        if kind=='GetObjectHalfExtents':
            return f'sg3d_node_extents(physics_bodies,SCENE_COUNT,{ref_expr(node,scope=scope)})'
        if kind=='CircleSegmentNormal':
            return f'sg3d_node_segment_normal({value_for(node,"point",visiting,scope)},{value_for(node,"a",visiting,scope)},{value_for(node,"b",visiting,scope)})'
        if kind=='FunctionArgumentObject':
            if not scope or not scope.get('argo'):raise ValueError('FunctionArgumentObject used outside a function')
            return scope['argo']
        if kind=='FunctionArgumentB':
            if not scope or not scope.get('argb'):raise ValueError('FunctionArgumentB used outside a function')
            return scope['argb']
        if kind=='FunctionArgumentVector':
            if not scope or not scope.get('argv'):raise ValueError('FunctionArgumentVector used outside a function')
            return scope['argv']
        if kind=='FunctionArgument':
            if not scope or not scope.get('arg'):raise ValueError('FunctionArgument used outside a function')
            return scope['arg']
        if kind=='LoopIndex':
            if not scope or not scope.get('loop'):raise ValueError('LoopIndex used outside a Repeat/WhileBool')
            return f'(({scope["loop"]}) << 8)'
        if kind in ('GetCameraX','GetCameraY','GetCameraZ'):
            return f'cam.{kind[-1].lower()}'
        if kind=='GetCameraYaw':return '((int32_t)cam.yaw * 360)'
        if kind=='GetObjectYaw':return f'sg3d_node_yaw(scene_objects,SCENE_COUNT,{ref_expr(node,scope=scope)})'
        if kind.startswith('GetVelocity'):
            return f'physics_bodies[{objnum(node)}].v{kind[-1].lower()}'
        if kind=='IsGrounded':return f'(physics_bodies[{objnum(node)}].grounded ? 256 : 0)'
        if kind=='KeyPressed':return f'(((keys & {key(node)}) && !(prev & {key(node)})) ? 256 : 0)'
        if kind=='NonZero':return f'(({value_for(node,"value",visiting,scope)}) != 0 ? 256 : 0)'
        if kind in ('LogicAnd','LogicOr'):
            a=value_for(node,'a',visiting,scope);b=value_for(node,'b',visiting,scope)
            return f'((({a}) {"&&" if kind=="LogicAnd" else "||"} ({b})) ? 256 : 0)'
        if kind=='LogicNot':return f'(!({value_for(node,"value",visiting,scope)}) ? 256 : 0)'
        if kind=='Compare':
            op=str(param(node,'op','>='))
            if op not in ('==','!=','<','<=','>','>='):raise ValueError('Invalid Compare operator')
            return f'(({value_for(node,"a",visiting,scope)}) {op} ({value_for(node,"b",visiting,scope)}) ? 256 : 0)'
        if kind=='MathAbs':return f'sg3d_abs_fx({value_for(node,"value",visiting,scope)})'
        if kind in ('MathMin','MathMax'):
            a=value_for(node,'a',visiting,scope);b=value_for(node,'b',visiting,scope)
            return f'sg3d_{"min" if kind=="MathMin" else "max"}_fx({a},{b})'
        if kind=='GetKeyHeld':return f'((keys & {key(node)}) ? 256 : 0)'
        if kind=='MathClamp':
            v=value_for(node,'value',visiting,scope);lo=value_for(node,'min',visiting,scope);hi=value_for(node,'max',visiting,scope)
            return f'sg3d_clamp_fx({v},{lo},{hi})'
        if kind=='GetVariable':return variable(node)
        if kind=='GetProperty':return f'sg3d_get_property(&script_context,{ref_expr(node,scope=scope)},"{property_name(node)}")'
        if kind.startswith('GetObject'):
            return f'sg3d_node_position(scene_objects,SCENE_COUNT,{ref_expr(node,scope=scope)}).{kind[-1].lower()}'
        if kind in ('MathAdd','MathSubtract','MathMultiply','MathDivide'):
            a=value_for(node,'a',visiting,scope);b=value_for(node,'b',visiting,scope)
            if kind=='MathAdd':return f'(({a}) + ({b}))'
            if kind=='MathSubtract':return f'(({a}) - ({b}))'
            if kind=='MathMultiply':return f'sg3d_fxmul({a},{b})'
            return f'sg3d_fxdiv({a},{b})'
        raise ValueError('Unsupported value source '+kind)
    def changes(node,expr,fields,angle=False,add=True,scope=None):
        operator='+=' if add else '='
        result=[]
        for axis in fields:
            unit=256/360 if angle else 256
            val=value_for(node,axis,scope=scope) if (node['id'],axis) in data_wires else _fixed(param(node,axis,'0'),unit)
            # yaw/pitch are GBA wraparound angle bytes
            if angle:val=f'(({val}) / 360)' if (node['id'],axis) in data_wires else str(int(val)&255)
            result.append(f'{expr}.{axis} {operator} {val};')
        return result
    functions={}
    for node in nodes:
        if node['type']=='FunctionDefinition':
            fname=str(param(node,'function','')).strip()
            if not re.fullmatch('[A-Za-z_][A-Za-z_0-9]*',fname):raise ValueError('Invalid function name: '+fname)
            if fname in functions:raise ValueError('Duplicate function name '+fname)
            functions[fname]=node
    custom_events={}
    for evt in nodes:
        if evt['type']=='OnEvent':
            ename=str(param(evt,'event','')).strip()
            if not re.fullmatch('[A-Za-z_][A-Za-z_0-9]*',ename):raise ValueError('Invalid custom event name: '+ename)
            custom_events.setdefault(ename,[]).append(evt)
    counter=[0]
    def unique():
        counter[0]+=1
        if counter[0]>2048:raise ValueError('Node graph expansion too large')
        return counter[0]
    def block(id_,stack,scope=None,func_stack=()):
        if id_ is None:return []
        if id_ in stack:raise ValueError('Cycle detected through node '+id_+'; use OnUpdate for repetition')
        node=names[id_];kind=node['type'];stack=stack | {id_}
        if kind in EVENTS:raise ValueError('Event can only start a graph')
        out=[]
        if kind=='IfKeyHeld':
            condition=f'(keys & {key(node)})'
        elif kind=='IfGrounded':
            condition=f'(physics_bodies[{objnum(node)}].grounded)'
        elif kind=='IfTouching':
            condition=f'(sg3d_physics_touching(physics_bodies,SCENE_COUNT,{objnum(node)},{objnum(node,"other")}))'
        elif kind=='IfNearObject':
            a=objnum(node);b=objnum(node,'other');radius=value_for(node,'radius',scope=scope)
            condition=f'(sg3d_near_objects(&scene_objects[{a}].transform,&scene_objects[{b}].transform,{radius}))'
        elif kind=='IfBool':
            condition=f'({value_for(node,"value",scope=scope)} != 0)'
        elif kind=='IfVariable':
            operator=str(param(node,'op','>='))
            if operator not in ('==','!=','<','<=','>','>='):raise ValueError('Invalid comparison operator')
            condition=f'({value_for(node,"a",scope=scope)} {operator} {value_for(node,"value",scope=scope)})'
        else:condition=None
        if condition is not None:
            yes=block(outgoing.get((id_,'true')),stack,scope,func_stack)
            no=block(outgoing.get((id_,'false')),stack,scope,func_stack)
            out += [f'if {condition} {{']+['    '+s for s in yes]+['}']
            if no:out+=['else {']+['    '+s for s in no]+['}']
            return out
        if kind in ('Repeat','WhileBool','ForEachObject'):
            number=unique();iterator=f'sg3d_loop_{number}'
            loop_scope=dict(scope or {});loop_scope['loop']=iterator
            if kind=='ForEachObject':
                tag=str(param(node,'property','')).strip()
                if tag and not re.fullmatch('[A-Za-z_][A-Za-z_0-9]*',tag):raise ValueError('Invalid ForEachObject property filter')
                loop_scope['object']=iterator
                body=block(outgoing.get((id_,'body')),stack,loop_scope,func_stack)
                out += [f'for(int {iterator}=0; {iterator}<SCENE_COUNT; ++{iterator}) {{']
                if tag:
                    if not any(tag in (o.get('properties') or {}) for o in objs):
                        out.append('    continue; /* no scene object has requested property */')
                    else:
                        out.append(f'    if(sg3d_get_property(&script_context,{iterator},"{tag}") < 256) continue;')
                out += ['    '+line for line in body]+['}']
                return out + block(outgoing.get((id_,'next')),stack,scope,func_stack)
            body=block(outgoing.get((id_,'body')),stack,loop_scope,func_stack)
            if kind=='Repeat':
                count=value_for(node,'count',scope=scope)
                # Bound execution even for a user-provided huge or negative number.
                out += [f'for(int {iterator}=0, sg3d_count_{number}=sg3d_bound_loop({count}); {iterator}<sg3d_count_{number}; ++{iterator}) {{']
            else:
                condition=value_for(node,'value',scope=loop_scope)
                out += [f'for(int {iterator}=0; {iterator}<64 && ({condition}); ++{iterator}) {{']
            out+=['    '+line for line in body]+['}']
            return out + block(outgoing.get((id_,'next')),stack,scope,func_stack)
        if kind=='BreakLoop':
            if not scope or not scope.get('loop'):raise ValueError('BreakLoop must be inside Repeat/WhileBool')
            return ['break;']
        if kind=='ReturnFunction':
            if not scope or not scope.get('exit'):raise ValueError('ReturnFunction must be inside a function')
            return [f'{scope["return"]} = {value_for(node,"value",scope=scope)};',f'goto {scope["exit"]};']
        if kind=='EmitEvent':
            ename=str(param(node,'event','')).strip()
            if not re.fullmatch('[A-Za-z_][A-Za-z_0-9]*',ename):raise ValueError('Invalid emitted event name: '+ename)
            number=unique();evtval=f'sg3d_evt_val_{number}';evtobj=f'sg3d_evt_obj_{number}'
            new_scope=dict(scope or {});new_scope['event']=evtval;new_scope['event_object']=evtobj
            out += ['{',f'    int32_t {evtval} = {value_for(node,"value",scope=scope)};',f'    int32_t {evtobj} = {value_for(node,"object",scope=scope)};']
            for listener in custom_events.get(ename,[]):
                branch=block(outgoing.get((listener['id'],'next')),stack|{listener['id']},new_scope,func_stack)
                out += ['    '+line for line in branch]
            out+=['}']
            return out+block(outgoing.get((id_,'next')),stack,scope,func_stack)
        if kind=='CallFunction':
            name=str(param(node,'function','')).strip()
            if name not in functions:raise ValueError('Undefined function '+name)
            if name in func_stack:raise ValueError('Recursive function calls are not supported: '+name)
            if len(func_stack)>8:raise ValueError('Function nesting limit (8)')
            number=unique();arg=f'sg3d_arg_{number}';argb=f'sg3d_argb_{number}';argv=f'sg3d_argv_{number}';argo=f'sg3d_argo_{number}';result=f'sg3d_result_{number}';label=f'sg3d_function_end_{number}'
            nested={'arg':arg,'argb':argb,'argv':argv,'argo':argo,'return':result,'exit':label,'loop':None,'object':None}
            inner=block(outgoing.get((functions[name]['id'],'next')),{functions[name]['id']},nested,func_stack+(name,))
            out += ['{', f'    int32_t {arg} = {value_for(node,"argument",scope=scope)};', f'    int32_t {argb} = {value_for(node,"argument_b",scope=scope)};', f'    SG3DVec3 {argv} = {value_for(node,"argument_vector",scope=scope)};', f'    int32_t {argo} = {value_for(node,"argument_object",scope=scope)};', f'    int32_t {result} = 0;']
            out += ['    '+line for line in inner]
            out += [f'    {label}: ;']
            variable_name=str(param(node,'result','')).strip()
            if variable_name:
                if variable_name not in vars_:raise ValueError('CallFunction result variable is not defined: '+variable_name)
                out += [f'    {vars_[variable_name]} = {result};']
            out += ['}']
            return out + block(outgoing.get((id_,'next')),stack,scope,func_stack)
        if kind=='MoveObject' and dynamic_ref(node):
            out.append(f'sg3d_node_move(physics_bodies,SCENE_COUNT,{ref_expr(node,scope=scope)},{value_for(node,"x",scope=scope)},{value_for(node,"y",scope=scope)},{value_for(node,"z",scope=scope)});')
        elif kind=='MoveObject':
            i=objnum(node)
            if str(node['id']) in orbit_nodes and orbit_enabled:
                out.append(f'sg3d_move_relative(physics_bodies,SCENE_COUNT,{i},{relative_yaw},'+value_for(node,'x',scope=scope)+','+value_for(node,'z',scope=scope)+');')
                out.append(f'sg3d_physics_move(physics_bodies,SCENE_COUNT,{i},0,{value_for(node,"y",scope=scope)},0);')
            else:
                out.append(f'sg3d_physics_move(physics_bodies,SCENE_COUNT,{i},'+','.join(value_for(node,axis,scope=scope) for axis in ('x','y','z'))+');')
        elif kind=='RotateObject' and dynamic_ref(node):
            out.append(f'sg3d_node_rotate(scene_objects,SCENE_COUNT,{ref_expr(node,scope=scope)},{value_for(node,"yaw",scope=scope)},{value_for(node,"pitch",scope=scope)});')
        elif kind=='RotateObject':out+=changes(node,objidx(node),('yaw','pitch'),angle=True,scope=scope)
        elif kind=='SetObjectPosition' and dynamic_ref(node):
            out.append(f'sg3d_node_set_position(scene_objects,SCENE_COUNT,{ref_expr(node,scope=scope)},{value_for(node,"x",scope=scope)},{value_for(node,"y",scope=scope)},{value_for(node,"z",scope=scope)});')
        elif kind=='SetObjectPosition':out+=changes(node,objidx(node),('x','y','z'),add=False,scope=scope)
        elif kind=='MoveCamera':out+=changes(node,'cam',('x','y','z'),scope=scope)
        elif kind=='RotateCamera':out+=changes(node,'cam',('yaw','pitch'),angle=True,scope=scope)
        elif kind=='SetProperty':out.append(f'sg3d_set_property(&script_context,{ref_expr(node,scope=scope)},"{property_name(node)}",{value_for(node,"value",scope=scope)});')
        elif kind=='SetVariable':out.append(f'{variable(node)} = {value_for(node,"value",scope=scope)};')
        elif kind=='AddVariable':out.append(f'{variable(node)} += {value_for(node,"value",scope=scope)};')
        elif kind=='MovePlayer':
            i=ref_expr(node,scope=scope)
            if str(node['id']) in orbit_nodes and orbit_enabled:
                out.append(f'sg3d_move_relative(physics_bodies,SCENE_COUNT,{i},{relative_yaw},{value_for(node,"x",scope=scope)},{value_for(node,"z",scope=scope)});')
            else:
                out.append(f'sg3d_physics_move(physics_bodies,SCENE_COUNT,{i},{value_for(node,"x",scope=scope)},0,{value_for(node,"z",scope=scope)});')
        elif kind=='MoveRelative':
            out.append(f'sg3d_move_relative(physics_bodies,SCENE_COUNT,{ref_expr(node,scope=scope)},{relative_yaw},{value_for(node,"x",scope=scope)},{value_for(node,"z",scope=scope)});')
        elif kind=='DriveVehicle':
            i=objnum(node)
            turn=value_for(node,'turn',scope=scope)
            out.append(f'sg3d_drive_vehicle(physics_bodies,SCENE_COUNT,{i},&vehicle_states[{i}],keys,{value_for(node,"acceleration",scope=scope)},{value_for(node,"maxspeed",scope=scope)},{value_for(node,"drag",scope=scope)},(uint8_t)({turn}>>8));')
        elif kind=='JumpObject':
            if dynamic_ref(node):
                out.append(f'sg3d_node_jump(physics_bodies,SCENE_COUNT,{ref_expr(node,scope=scope)},{value_for(node,"impulse",scope=scope)});')
            else:
                out.append(f'sg3d_physics_jump(physics_bodies,SCENE_COUNT,{objnum(node)},{value_for(node,"impulse",scope=scope)});')
        elif kind=='SetVelocity':
            idx=objnum(node)
            out.append(f'physics_bodies[{idx}].vx = {value_for(node,"x",scope=scope)};')
            out.append(f'physics_bodies[{idx}].vz = {value_for(node,"z",scope=scope)};')
        elif kind=='FollowObject':
            idx=objidx(node)
            for axis in ('x','y','z'):
                out.append(f'cam.{axis} = {idx}.{axis} + {value_for(node,axis,scope=scope)};')
        elif kind in ('PlayAnimation','StopAnimation'):
            target=str(param(node,'animation','0'))
            clips=doc.get('animations') or []
            try:idx=int(target)
            except ValueError:
                clip_names=[c['name'] for c in clips]
                if target not in clip_names:raise ValueError('Unknown animation '+target)
                idx=clip_names.index(target)
            if not 0<=idx<len(clips):raise ValueError(f'Node {node["id"]}: invalid animation clip {target}')
            out.append(f'sg3d_anim_{"play" if kind=="PlayAnimation" else "stop"}({idx});')
        elif kind=='PlaySound':
            target=str(param(node,'sound','0'))
            sounds=doc.get('sounds') or []
            try:idx=int(target)
            except ValueError:
                sound_names=[s['name'] for s in sounds]
                if target not in sound_names:raise ValueError('Unknown sound '+target)
                idx=sound_names.index(target)
            if not 0<=idx<len(sounds):raise ValueError(f'Node {node["id"]}: invalid WAV sound {target}')
            out.append(f'sg3d_audio_play(sg3d_sound_{idx},SG3D_SOUND_{idx}_LENGTH);')
        elif kind=='StopSound':out.append('sg3d_audio_stop();')
        elif kind in ('SetUIValue','ShowUI','HideUI'):
            try:ui=int(param(node,'element','0'))
            except (ValueError,TypeError):raise ValueError('Invalid UI element index')
            if not 0<=ui<len(doc.get('hud',[])):raise ValueError(f'Node {node["id"]}: HUD element {ui} does not exist')
            if kind=='SetUIValue':out.append(f'sg3d_hud_set_value({ui},({value_for(node,"value",scope=scope)})>>8);')
            else:out.append(f'sg3d_hud_set_visible({ui},{1 if kind=="ShowUI" else 0});')
        elif kind=='MoveLocal':
            i=ref_expr(node,scope=scope)
            out.append(f'sg3d_move_relative(physics_bodies,SCENE_COUNT,{i},sg3d_node_yaw_byte(scene_objects,SCENE_COUNT,{i}),{value_for(node,"x",scope=scope)},{value_for(node,"z",scope=scope)});')
        elif kind=='SetCameraPosition':out+=changes(node,'cam',('x','y','z'),add=False,scope=scope)
        elif kind=='SetCameraRotation':out+=changes(node,'cam',('yaw','pitch'),angle=True,add=False,scope=scope)
        elif kind=='SetObjectRotation':out+=changes(node,objidx(node),('yaw','pitch'),angle=True,add=False,scope=scope)
        elif kind=='SetObjectScale':out.append(f'{objidx(node)}.scale = (uint16_t)sg3d_clamp_fx({value_for(node,"value",scope=scope)},1,65535);')
        elif kind in ('MoveObjectVector','SetObjectVector'):
            i=ref_expr(node,scope=scope);number=unique();vec=f'sg3d_vector_{number}'
            out.append('{')
            out.append(f'    SG3DVec3 {vec} = {value_for(node,"vector",scope=scope)};')
            if kind=='MoveObjectVector':
                out.append(f'    sg3d_node_move(physics_bodies,SCENE_COUNT,{i},{vec}.x,{vec}.y,{vec}.z);')
            else:
                out.append(f'    sg3d_node_set_position(scene_objects,SCENE_COUNT,{i},{vec}.x,{vec}.y,{vec}.z);')
            out.append('}')
        elif kind=='SetArray':
            name,size=array_info(node)
            out.append(f'sg3d_array_set({name},{size},{value_for(node,"index",scope=scope)},{value_for(node,"value",scope=scope)});')
        elif kind=='SetVelocity3D':
            out.append(f'sg3d_node_velocity(physics_bodies,SCENE_COUNT,{ref_expr(node,scope=scope)},{value_for(node,"x",scope=scope)},{value_for(node,"y",scope=scope)},{value_for(node,"z",scope=scope)});')
        elif kind=='LoadScene':
            target=str(param(node,'scene','0'))
            scene_names=doc.get('scene_names') or [s.get('name',f'Scene {i}') for i,s in enumerate(doc.get('scenes',[]))]
            if not scene_names:raise ValueError('LoadScene requires a multi-scene project')
            try:idx=int(target)
            except ValueError:
                if target not in scene_names:raise ValueError(f'Unknown scene {target}')
                idx=scene_names.index(target)
            if idx<0 or idx>=len(scene_names):raise ValueError('LoadScene target is outside project')
            out.append(f'sg3d_requested_scene = {idx};')
        else:raise ValueError('Unsupported action '+kind)
        return out + block(outgoing.get((id_,'next')),stack,scope,func_stack)
    start=[];update=[];post_physics=[]
    for node in nodes:
        kind=node['type']
        if kind not in EVENTS or kind in ('FunctionDefinition','OnEvent'):continue
        commands=block(outgoing.get((node['id'],'next')),{node['id']})
        if kind=='OnStart':start+=commands
        elif kind=='OnUpdate':update+=commands
        elif kind=='OnKeyHeld':
            update+= [f'if (keys & {key(node)}) {{']+['    '+s for s in commands]+['}']
        elif kind=='OnKeyPressed':
            update+= [f'if ((keys & {key(node)}) && !(prev & {key(node)})) {{']+['    '+s for s in commands]+['}']
        elif kind=='OnCollision':
            a=objnum(node);b=objnum(node,'other')
            post_physics += [f'if (sg3d_physics_touching(physics_bodies,SCENE_COUNT,{a},{b}) && !collision_previous[{a}][{b}]) {{']+['    '+s for s in commands]+['}']
    # Structured flow functions and loops compile to native C. The GBA doesn't
    # interpret node graphs at runtime; a fixed 64-iteration cap protects the frame.
    if any(n['type'] in ('Repeat','WhileBool') for n in nodes):
        decl.append('static inline int sg3d_bound_loop(int32_t n){ n >>= 8; return n < 0 ? 0 : n > 64 ? 64 : (int)n; }')
    if any(n['type'] in ('MakeVector','GetObjectVector','GetCameraVector','VectorAdd','VectorSubtract','VectorScale','VectorX','VectorY','VectorZ','MoveObjectVector','SetObjectVector','WorldToLocal','LocalToWorld','CircleSegmentOverlap','SphereBoxOverlap','RaycastBox','FunctionArgumentVector','CallFunction','VectorDot','VectorDistanceSqXZ','ClosestPointBox','GetObjectHalfExtents','CircleSegmentNormal','GetObjectX','GetObjectY','GetObjectZ','GetObjectYaw','MoveObject','RotateObject','SetObjectPosition','SetVelocity3D','JumpObject','MoveLocal','VectorDot','VectorDistanceSqXZ','ClosestPointBox','GetObjectHalfExtents','CircleSegmentNormal') for n in nodes):
        decl.extend([
            'typedef struct {int32_t x,y,z;} SG3DVec3;',
            'static inline SG3DVec3 sg3d_v3(int32_t x,int32_t y,int32_t z){SG3DVec3 r={x,y,z};return r;}',
            'static inline SG3DVec3 sg3d_vadd(SG3DVec3 a,SG3DVec3 b){return sg3d_v3(a.x+b.x,a.y+b.y,a.z+b.z);}',
            'static inline SG3DVec3 sg3d_vsub(SG3DVec3 a,SG3DVec3 b){return sg3d_v3(a.x-b.x,a.y-b.y,a.z-b.z);}',
            'static inline SG3DVec3 sg3d_vscale(SG3DVec3 a,int32_t k){return sg3d_v3((int32_t)(((int64_t)a.x*k)>>8),(int32_t)(((int64_t)a.y*k)>>8),(int32_t)(((int64_t)a.z*k)>>8));}'
        ])
    if (any(n['type'] in ('WorldToLocal','LocalToWorld','CircleSegmentOverlap','SphereBoxOverlap','RaycastBox',
                           'GetObjectX','GetObjectY','GetObjectZ','GetObjectVector','GetObjectYaw',
                           'MoveObjectVector','SetObjectVector','MoveObject','RotateObject',
                           'SetObjectPosition','SetVelocity3D','JumpObject','MoveLocal') for n in nodes)):
        # These helpers accept dynamic object indices, reject invalid ids, and
        # use only fixed-point math, bounded loops, and the existing physics array.
        decl.extend([
            'static inline int sg3d_node_valid(int i,int count){return i>=0 && i<count;}',
            'static inline SG3DVec3 sg3d_node_position(const SceneObject *o,int n,int i){return sg3d_node_valid(i,n)?sg3d_v3(o[i].transform.x,o[i].transform.y,o[i].transform.z):sg3d_v3(0,0,0);}',
            'static inline int32_t sg3d_node_yaw(const SceneObject *o,int n,int i){return sg3d_node_valid(i,n)?(int32_t)o[i].transform.yaw*360:0;}',
            'static inline uint8_t sg3d_node_yaw_byte(const SceneObject *o,int n,int i){return sg3d_node_valid(i,n)?o[i].transform.yaw:0;}',
            'static inline void sg3d_node_move(SG3DPhysicsBody *b,int n,int i,int32_t x,int32_t y,int32_t z){if(sg3d_node_valid(i,n))sg3d_physics_move(b,n,i,x,y,z);}',
            'static inline void sg3d_node_jump(SG3DPhysicsBody *b,int n,int i,int32_t impulse){if(sg3d_node_valid(i,n))sg3d_physics_jump(b,n,i,impulse);}',
            'static inline void sg3d_node_velocity(SG3DPhysicsBody *b,int n,int i,int32_t x,int32_t y,int32_t z){if(sg3d_node_valid(i,n)){b[i].vx=x;b[i].vy=y;b[i].vz=z;}}',
            'static inline void sg3d_node_set_position(SceneObject *o,int n,int i,int32_t x,int32_t y,int32_t z){if(sg3d_node_valid(i,n)){o[i].transform.x=x;o[i].transform.y=y;o[i].transform.z=z;}}',
            'static inline void sg3d_node_rotate(SceneObject *o,int n,int i,int32_t yaw,int32_t pitch){if(sg3d_node_valid(i,n)){o[i].transform.yaw+=(uint8_t)(yaw/360);o[i].transform.pitch+=(uint8_t)(pitch/360);}}',
        ])
    if any(n['type'] in ('WorldToLocal','LocalToWorld','CircleSegmentOverlap','SphereBoxOverlap','RaycastBox','ClosestPointBox','GetObjectHalfExtents','CircleSegmentNormal') for n in nodes):
        decl.extend([
            'static inline int32_t sg3d_node_clamp(int32_t v,int32_t a,int32_t b){return v<a?a:v>b?b:v;}',
            'static inline SG3DVec3 sg3d_node_to_local(const SceneObject *o,int n,int i,SG3DVec3 p){',
            ' if(!sg3d_node_valid(i,n))return p; const SG3DTransform *t=&o[i].transform;',
            ' int32_t dx=p.x-t->x,dy=p.y-t->y,dz=p.z-t->z;',
            ' int32_t c=sin_table[(uint8_t)(t->yaw+64)],s=sin_table[t->yaw];',
            ' int32_t cp=sin_table[(uint8_t)(t->pitch+64)],sp=sin_table[t->pitch];',
            ' int32_t yy=(int32_t)(((int64_t)cp*dy+(int64_t)sp*dz)>>8);',
            ' int32_t zz=(int32_t)(((int64_t)cp*dz-(int64_t)sp*dy)>>8);',
            ' int32_t xx=(int32_t)(((int64_t)c*dx-(int64_t)s*zz)>>8);',
            ' zz=(int32_t)(((int64_t)s*dx+(int64_t)c*zz)>>8);',
            ' int32_t scale=t->scale?t->scale:256;',
            ' return sg3d_v3(sg3d_fxdiv(xx,scale),sg3d_fxdiv(yy,scale),sg3d_fxdiv(zz,scale));}',
            'static inline SG3DVec3 sg3d_node_to_world(const SceneObject *o,int n,int i,SG3DVec3 p){',
            ' if(!sg3d_node_valid(i,n))return p; const SG3DTransform *t=&o[i].transform;',
            ' int32_t c=sin_table[(uint8_t)(t->yaw+64)],s=sin_table[t->yaw];',
            ' int32_t cp=sin_table[(uint8_t)(t->pitch+64)],sp=sin_table[t->pitch];',
            ' int32_t scale=t->scale?t->scale:256;',
            ' int32_t x=(int32_t)(((int64_t)p.x*scale)>>8),y=(int32_t)(((int64_t)p.y*scale)>>8),z=(int32_t)(((int64_t)p.z*scale)>>8);',
            ' int32_t xx=(int32_t)(((int64_t)c*x+(int64_t)s*z)>>8);',
            ' int32_t zz=(int32_t)(((int64_t)c*z-(int64_t)s*x)>>8);',
            ' int32_t yy=(int32_t)(((int64_t)cp*y-(int64_t)sp*zz)>>8);',
            ' zz=(int32_t)(((int64_t)sp*y+(int64_t)cp*zz)>>8);',
            ' return sg3d_v3(t->x+xx,t->y+yy,t->z+zz);}',
            'static inline SG3DVec3 sg3d_node_extents(const SG3DPhysicsBody *b,int n,int i){return sg3d_node_valid(i,n)?sg3d_v3(b[i].hx,b[i].hy,b[i].hz):sg3d_v3(0,0,0);}',
            'static inline SG3DVec3 sg3d_node_closest_box(const SG3DPhysicsBody *b,int n,int i,SG3DVec3 p){',
            ' if(!sg3d_node_valid(i,n)||!b[i].transform)return p;',
            ' const SG3DTransform *t=b[i].transform;',
            ' return sg3d_v3(sg3d_node_clamp(p.x,t->x-b[i].hx,t->x+b[i].hx),sg3d_node_clamp(p.y,t->y-b[i].hy,t->y+b[i].hy),sg3d_node_clamp(p.z,t->z-b[i].hz,t->z+b[i].hz));}',
            'static inline SG3DVec3 sg3d_node_segment_normal(SG3DVec3 p,SG3DVec3 a,SG3DVec3 b){',
            ' int32_t dx=b.x-a.x,dz=b.z-a.z,px=p.x-a.x,pz=p.z-a.z;',
            ' int32_t denom=(int32_t)(((int64_t)dx*dx+(int64_t)dz*dz)>>8);',
            ' int32_t proj=denom?sg3d_fxdiv((int32_t)(((int64_t)px*dx+(int64_t)pz*dz)>>8),denom):0;',
            ' proj=sg3d_node_clamp(proj,0,256);',
            ' int32_t nx=px-(int32_t)(((int64_t)dx*proj)>>8),nz=pz-(int32_t)(((int64_t)dz*proj)>>8);',
            ' int32_t ax=nx<0?-nx:nx,az=nz<0?-nz:nz,largest=ax>az?ax:az;',
            ' if(!largest){nx=-dz;nz=dx;ax=nx<0?-nx:nx;az=nz<0?-nz:nz;largest=ax>az?ax:az;}',
            ' if(!largest)return sg3d_v3(0,0,0);',
            ' return sg3d_v3(sg3d_fxdiv(nx,largest),0,sg3d_fxdiv(nz,largest));}',
            'static inline int sg3d_node_circle_segment(SG3DVec3 p,SG3DVec3 a,SG3DVec3 b,int32_t radius){',
            ' if(radius<0)return 0; int64_t dx=(int64_t)b.x-a.x,dz=(int64_t)b.z-a.z;',
            ' int64_t px=(int64_t)p.x-a.x,pz=(int64_t)p.z-a.z,r=radius;',
            ' /* Preserve full pixel precision for short rails; scale only large inputs.',
            '    Prevent squared cross products from overflowing signed 64-bit. */',
            ' int64_t m=dx<0?-dx:dx; int64_t v=dz<0?-dz:dz;if(v>m)m=v;',
            ' v=px<0?-px:px;if(v>m)m=v;v=pz<0?-pz:pz;if(v>m)m=v;if(r>m)m=r;',
            ' while(m>8192){dx>>=1;dz>>=1;px>>=1;pz>>=1;r=(r+1)>>1;m=(m+1)>>1;}',
            ' int64_t len=dx*dx+dz*dz,dist;',
            ' if(len==0)return px*px+pz*pz<=r*r;',
            ' int64_t dot=px*dx+pz*dz;',
            ' if(dot<=0)dist=px*px+pz*pz;',
            ' else if(dot>=len){px-=dx;pz-=dz;dist=px*px+pz*pz;}',
            ' else {int64_t cross=px*dz-pz*dx;return cross*cross<=r*r*len;}',
            ' return dist<=r*r;}',
            'static inline int sg3d_node_sphere_box(const SG3DPhysicsBody *b,int n,int i,SG3DVec3 p,int32_t r){',
            ' if(!sg3d_node_valid(i,n)||!b[i].transform||r<0)return 0;',
            ' const SG3DTransform *t=b[i].transform;',
            ' int64_t dx=(int64_t)p.x-sg3d_node_clamp(p.x,t->x-b[i].hx,t->x+b[i].hx);',
            ' int64_t dy=(int64_t)p.y-sg3d_node_clamp(p.y,t->y-b[i].hy,t->y+b[i].hy);',
            ' int64_t dz=(int64_t)p.z-sg3d_node_clamp(p.z,t->z-b[i].hz,t->z+b[i].hz);',
            ' return dx*dx+dy*dy+dz*dz<=(int64_t)r*r;}',
            'static inline int sg3d_node_raycast_box(const SG3DPhysicsBody *b,int n,int i,SG3DVec3 a,SG3DVec3 end){',
            ' if(!sg3d_node_valid(i,n)||!b[i].transform)return 0;',
            ' const SG3DTransform *t=b[i].transform;int32_t lo=0,hi=256;',
            ' int32_t origin[3]={a.x,a.y,a.z},delta[3]={end.x-a.x,end.y-a.y,end.z-a.z};',
            ' int32_t center[3]={t->x,t->y,t->z},ext[3]={b[i].hx,b[i].hy,b[i].hz};',
            ' for(int k=0;k<3;k++){int32_t mn=center[k]-ext[k],mx=center[k]+ext[k];',
            ' if(!delta[k]){if(origin[k]<mn||origin[k]>mx)return 0;continue;}',
            ' int32_t u=sg3d_fxdiv(mn-origin[k],delta[k]),v=sg3d_fxdiv(mx-origin[k],delta[k]);',
            ' if(u>v){int32_t tmp=u;u=v;v=tmp;}if(u>lo)lo=u;if(v<hi)hi=v;if(lo>hi)return 0;}',
            ' return 1;}',
        ])
    if any(n['type'] in ('GetArray','SetArray') for n in nodes):
        decl.extend([
            'static inline int32_t sg3d_array_get(const int32_t *a,unsigned n,int32_t i){ i >>= 8; return (i>=0 && (uint32_t)i<n) ? a[i] : 0; }',
            'static inline void sg3d_array_set(int32_t *a,unsigned n,int32_t i,int32_t v){ i >>= 8; if(i>=0 && (uint32_t)i<n)a[i]=v; }',
        ])
    if any(n['type'] in ('VectorDot','VectorDistanceSqXZ') for n in nodes):
        decl.extend([
            'static inline int32_t sg3d_node_dot(SG3DVec3 a,SG3DVec3 b){return (int32_t)(((int64_t)a.x*b.x+(int64_t)a.y*b.y+(int64_t)a.z*b.z)>>8);}',
            'static inline int32_t sg3d_node_distance_sq_xz(SG3DVec3 a,SG3DVec3 b){int64_t x=(int64_t)a.x-b.x,z=(int64_t)a.z-b.z;return (int32_t)((x*x+z*z)>>8);}',
        ])
    if any(n['type']=='MathAbs' for n in nodes):
        decl.append('static inline int32_t sg3d_abs_fx(int32_t v){return v==(-2147483647-1)?2147483647:(v<0?-v:v);}')
    if any(n['type']=='MathMin' for n in nodes):
        decl.append('static inline int32_t sg3d_min_fx(int32_t a,int32_t b){return a<b?a:b;}')
    if any(n['type']=='MathMax' for n in nodes):
        decl.append('static inline int32_t sg3d_max_fx(int32_t a,int32_t b){return a>b?a:b;}')
    if with_physics:return decl,start,update,post_physics
    return decl,start,update
