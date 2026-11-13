"""SG3D native Tkinter visual flow scripting editor.
Left choose node type; in graph click an output circle then an input circle
and connect; drag blocks to arrange; edit selected node's parameters on right.
"""
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from node_scripts import NODE_TYPES, EVENTS, PARAMS, KEYS, VALUE_NODES, VALUE_INPUTS, VALUE_OUTPUT_TYPES, VALUE_INPUT_TYPES, default_node, compile_graph

PANEL='#1f2a39';BG='#14202d';TEXT='#e0ecf4';CYAN='#50dccb'
W=190;HEADER=33;ROW=22


class NodeEditor(tk.Toplevel):
    def __init__(self,owner):
        super().__init__(owner)
        self.owner=owner;self.doc=owner.doc
        self.title('SG3D Universal Nodes 3.0')
        self.geometry('1160x720');self.minsize(840,530)
        self.configure(bg=BG)
        self.graph=self.doc.setdefault('scripts',{'nodes':[],'links':[]})
        self.graph.setdefault('nodes',[]);self.graph.setdefault('links',[]);self.graph.setdefault('data_links',[])
        self.selected=None;self.pending=None;self.drag=None
        self.message=tk.StringVar(value='Aqua = flow • orange = numbers • purple = booleans. Bounded loops and reusable functions supported.')
        self.make_ui();self.draw()
        self.protocol('WM_DELETE_WINDOW',self.close)

    def make_ui(self):
        tools=ttk.Frame(self,padding=7);tools.pack(fill='x')
        ttk.Label(tools,text='ADD NODE').pack(side='left',padx=4)
        self.kind=tk.StringVar(value='OnUpdate')
        ttk.Combobox(tools,textvariable=self.kind,values=list(NODE_TYPES),width=22,state='readonly').pack(side='left')
        ttk.Button(tools,text='＋ Add node',command=self.add_node).pack(side='left',padx=5)
        ttk.Button(tools,text='Delete selected',command=self.delete_node).pack(side='left',padx=5)
        ttk.Button(tools,text='Variables...',command=self.edit_vars).pack(side='left',padx=5)
        ttk.Button(tools,text='Arrays...',command=self.edit_arrays).pack(side='left',padx=5)
        ttk.Button(tools,text='Import library',command=self.import_library).pack(side='left',padx=5)
        ttk.Button(tools,text='Export functions',command=self.export_functions).pack(side='left',padx=5)
        ttk.Button(tools,text='Validate graph',command=self.validate).pack(side='left',padx=5)
        ttk.Button(tools,text='Save project',command=self.owner.save_scene).pack(side='left',padx=5)
        ttk.Label(tools,text='No GBA interpreter: graph → C',foreground=CYAN).pack(side='right',padx=8)
        body=ttk.Panedwindow(self,orient='horizontal');body.pack(fill='both',expand=True,padx=8)
        center=ttk.Frame(body);body.add(center,weight=5)
        self.canvas=tk.Canvas(center,bg=BG,highlightthickness=0,scrollregion=(0,0,2300,1600))
        self.canvas.pack(side='left',fill='both',expand=True)
        sy=ttk.Scrollbar(center,orient='vertical',command=self.canvas.yview)
        sx=ttk.Scrollbar(center,orient='horizontal',command=self.canvas.xview)
        sy.pack(side='right',fill='y');sx.pack(side='bottom',fill='x')
        self.canvas.configure(xscrollcommand=sx.set,yscrollcommand=sy.set)
        self.canvas.bind('<ButtonPress-1>',self.on_press)
        self.canvas.bind('<B1-Motion>',self.on_motion)
        self.canvas.bind('<ButtonRelease-1>',lambda e:setattr(self,'drag',None))
        self.canvas.bind('<ButtonPress-3>',self.right_click)
        inspector=ttk.Frame(body,width=260,padding=10);body.add(inspector,weight=1)
        self.inspector=inspector
        self.param_panel=ttk.Frame(inspector);self.param_panel.pack(fill='both',expand=True)
        ttk.Label(self,textvariable=self.message,padding=(12,6)).pack(fill='x')
        self.show_params()

    def close(self):
        try:compile_graph(self.doc)
        except ValueError as e:
            if not messagebox.askyesno('Incomplete graph',str(e)+'\n\nClose editor anyway?\nThe project can be saved, but exporting will fail until fixed.',parent=self):return
        self.owner.draw_scene();self.destroy()

    def get_node(self,id_):
        return next((n for n in self.graph['nodes'] if n['id']==id_),None)

    def add_node(self):
        kind=self.kind.get();ids={n['id'] for n in self.graph['nodes']};num=1
        while 'n'+str(num) in ids:num+=1
        node=default_node(kind,'n'+str(num),80+(num%5)*32,70+(num%5)*38)
        if kind in ('MoveObject','RotateObject','SetObjectPosition','MovePlayer','MoveRelative','DriveVehicle','IfNearObject','JumpObject','SetVelocity','IfGrounded','IfTouching','OnCollision','FollowObject','GetObjectX','GetObjectY','GetObjectZ','GetProperty','SetProperty','ObjectRef','WorldToLocal','LocalToWorld','SphereBoxOverlap','RaycastBox'):
            if not self.doc.get('objects'):
                messagebox.showwarning('No objects','Add a mesh object in the scene editor first.',parent=self);return
            node['params']['object']='0'
        if kind in ('IfVariable','SetVariable','AddVariable','GetVariable'):
            variables=self.doc.setdefault('variables',{'score':0})
            if not variables:variables['score']=0
            node['params']['variable']=next(iter(variables))
        self.graph['nodes'].append(node)
        self.owner._dirty=True
        self.selected=node['id'];self.show_params();self.draw()

    def delete_node(self):
        if self.selected is None:return
        target=self.selected
        self.graph['nodes'][:]=[n for n in self.graph['nodes'] if n['id']!=target]
        self.graph['links'][:]=[e for e in self.graph['links'] if e['from']!=target and e['to']!=target]
        self.graph['data_links'][:]=[e for e in self.graph['data_links'] if e['from']!=target and e['to']!=target]
        self.pending=self.selected=None;self.owner._dirty=True;self.draw();self.show_params()

    def validate(self):
        try:
            decl,start,update=compile_graph(self.doc)
            messagebox.showinfo('Graph is valid',f'{len(self.graph["nodes"])} nodes / {len(self.graph["links"])} connections.\nCompiled {len(start)} Start + {len(update)} Update C statements.\nExport GBA from the main editor to build.',parent=self)
        except Exception as e:messagebox.showerror('Graph error',str(e),parent=self)

    def edit_vars(self):
        var=self.doc.setdefault('variables',{'score':0})
        name=simpledialog.askstring('Script variables','Variable name (A-Z, 0-9, underscore).\nExisting names can be updated.',parent=self)
        if not name:return
        import re
        if not re.fullmatch('[A-Za-z_][A-Za-z_0-9]*',name):
            messagebox.showerror('Bad name','Use letters, digits, and underscores; start with a letter.',parent=self);return
        val=simpledialog.askfloat('Initial value',f'Starting value for {name} (number):',initialvalue=var.get(name,0),parent=self)
        if val is not None:var[name]=val;self.owner._dirty=True;self.message.set('Variable '+name+' = '+str(val));self.show_params()

    def edit_arrays(self):
        arrays=self.doc.setdefault('arrays',{})
        name=simpledialog.askstring('Numeric arrays','Array name (letters/digits/underscore). Existing arrays can be edited.',parent=self)
        if not name:return
        import re
        if not re.fullmatch('[A-Za-z_][A-Za-z_0-9]*',name):
            messagebox.showerror('Invalid name','Use a valid C-style identifier.',parent=self);return
        default=','.join(str(v) for v in arrays.get(name,[0,0,0,0]))
        vals=simpledialog.askstring('Array values','Comma-separated numbers, from 1 to 64 entries.',initialvalue=default,parent=self)
        if vals is None:return
        try:
            numbers=[float(x.strip()) for x in vals.split(',')]
            if not 1<=len(numbers)<=64 or any(not -100000<=n<=100000 for n in numbers):raise ValueError('Expected 1–64 numbers')
        except ValueError as err:
            messagebox.showerror('Invalid array',str(err),parent=self);return
        arrays[name]=numbers
        self.owner._dirty=True;self.message.set(f'Array {name}: {len(numbers)} numbers');self.show_params()

    def import_library(self):
        import json
        path=filedialog.askopenfilename(parent=self,title='Import a reusable SG3D node library',filetypes=[('SG3D component','*.json')])
        if not path:return
        try:
            library=json.load(open(path,encoding='utf8'))
            components=self.doc.setdefault('node_components',[])
            components.append(library)
            try:compile_graph(self.doc)
            except Exception:
                components.pop();raise
            self.owner._dirty=True
            self.message.set('Imported reusable library: '+str(library['name']))
        except Exception as exc:messagebox.showerror('Library error',str(exc),parent=self)

    def export_functions(self):
        import json
        from pathlib import Path
        functions=[n for n in self.graph['nodes'] if n['type']=='FunctionDefinition']
        if not functions:
            messagebox.showinfo('No functions','Create a FunctionDefinition first.',parent=self);return
        name=simpledialog.askstring('Reusable library','Library name (letters/numbers/underscore):',initialvalue='MyFunctions',parent=self)
        import re
        if not name:return
        if not re.fullmatch('[A-Za-z_][A-Za-z_0-9]*',name):
            messagebox.showerror('Invalid name','Use a C-style identifier.',parent=self);return
        links=self.graph.get('links',[]);data=self.graph.get('data_links',[])
        # Include every flow-reachable action and recursively all required value sources.
        include=set(n['id'] for n in functions)
        changed=True
        while changed:
            before=len(include)
            include.update(e['to'] for e in links if e['from'] in include)
            include.update(e['from'] for e in data if e['to'] in include)
            changed=len(include)!=before
        graph={
          'nodes':[n for n in self.graph['nodes'] if n['id'] in include],
          'links':[e for e in links if e['from'] in include and e['to'] in include],
          'data_links':[e for e in data if e['from'] in include and e['to'] in include],
        }
        target=filedialog.asksaveasfilename(parent=self,title='Save SG3D function library',defaultextension='.json',
              initialfile=name+'.sg3dlib.json',filetypes=[('SG3D component','*.json')])
        if not target:return
        try:
            Path(target).write_text(json.dumps({'name':name,'scripts':graph},indent=2),encoding='utf8')
            self.message.set(f'Exported {len(functions)} reusable function(s)')
        except Exception as exc:messagebox.showerror('Export failed',str(exc),parent=self)

    def coords(self,node):return node['x'],node['y']

    def data_pin_location(self,id_,port,output):
        node=self.get_node(id_)
        if not node:return 0,0
        x,y=self.coords(node);kind=node['type'];flow=len(NODE_TYPES[kind][1])
        if output:return x+W,y+HEADER+12
        fields=VALUE_INPUTS[kind]
        return x,y+HEADER+max(1,flow)*ROW+20+fields.index(port)*ROW

    def node_height(self,node):
        kind=node['type'];flows=len(NODE_TYPES[kind][1])
        return HEADER+max(1,flows)*ROW+20+len(VALUE_INPUTS[kind])*ROW+14

    def pin_location(self,id_,port,output):
        node=self.get_node(id_)
        if not node:return 0,0
        x,y=self.coords(node)
        if not output:return x,y+HEADER+12
        ports=NODE_TYPES[node['type']][1]
        i=ports.index(port)
        return x+W,y+HEADER+12+i*ROW

    def draw(self):
        c=self.canvas;c.delete('all')
        # Large user-authored graphs can extend far beyond the old fixed 2300x1600
        # canvas. Expand the scrollable area to include every node and its ports.
        max_x=max([2300]+[int(n['x'])+W+100 for n in self.graph['nodes']])
        max_y=max([1600]+[int(n['y'])+self.node_height(n)+120 for n in self.graph['nodes']])
        c.configure(scrollregion=(0,0,max_x,max_y))
        for x in range(0,max_x+1,80):c.create_line(x,0,x,max_y,fill='#1d2b3b')
        for y in range(0,max_y+1,80):c.create_line(0,y,max_x,y,fill='#1d2b3b')
        for e in self.graph['links']:
            a=self.get_node(e['from']);b=self.get_node(e['to'])
            if not a or not b:continue
            x0,y0=self.pin_location(a['id'],e['port'],True)
            x1,y1=self.pin_location(b['id'],'in',False)
            bend=max(35,abs(x1-x0)*.5)
            c.create_line(x0,y0,x0+bend,y0,x1-bend,y1,x1,y1,smooth=True,
                          splinesteps=16,fill=CYAN,width=3,tags=('wire',f'wire:{e["from"]}:{e["port"]}'))
        for e in self.graph.get('data_links',[]):
            a=self.get_node(e['from']);b=self.get_node(e['to'])
            if not a or not b:continue
            x0,y0=self.data_pin_location(a['id'],'value',True)
            x1,y1=self.data_pin_location(b['id'],e['input'],False)
            bend=max(35,abs(x1-x0)*.5)
            c.create_line(x0,y0,x0+bend,y0,x1-bend,y1,x1,y1,smooth=True,
                          splinesteps=18,fill=('#6ea8ff' if VALUE_OUTPUT_TYPES[a['type']]=='object' else '#c89aff' if VALUE_OUTPUT_TYPES[a['type']]=='bool' else '#8fe0ae' if VALUE_OUTPUT_TYPES[a['type']]=='vector' else '#ffb568'),width=3,
                          tags=('data-wire',f'data-wire:{e["from"]}:{e["to"]}:{e["input"]}'))
        for node in self.graph['nodes']:
            x,y=self.coords(node);id_=node['id'];typ=node['type'];ports=NODE_TYPES[typ][1]
            height=self.node_height(node)
            fill='#315775' if typ in EVENTS else ('#71542f' if typ in VALUE_NODES else ('#604f7a' if typ.startswith('If') else '#294a52'))
            outline=CYAN if id_==self.selected else '#536778'
            tag=('node',f'node:{id_}')
            c.create_rectangle(x+3,y+4,x+W+3,y+height+4,fill='#0c1621',outline='')
            c.create_rectangle(x,y,x+W,y+height,fill=PANEL,outline=outline,width=2,tags=tag)
            c.create_rectangle(x,y,x+W,y+HEADER,fill=fill,outline='',tags=tag)
            c.create_text(x+11,y+HEADER/2,text=NODE_TYPES[typ][0],font=('Segoe UI',10,'bold'),
                          fill=TEXT,anchor='w',tags=tag)
            if typ not in EVENTS and typ not in VALUE_NODES:
                ix,iy=self.pin_location(id_,'in',False)
                c.create_oval(ix-7,iy-7,ix+7,iy+7,fill=CYAN,outline='',tags=(f'input:{id_}',))
                c.create_text(ix+12,iy,anchor='w',text='flow',fill='#9bd9d6',font=('Segoe UI',9),tags=tag)
            for port in ports:
                px,py=self.pin_location(id_,port,True)
                col='#ffdfb1' if self.pending==('flow',id_,port) else CYAN
                c.create_oval(px-7,py-7,px+7,py+7,fill=col,outline='',tags=(f'output:{id_}:{port}',))
                c.create_text(px-12,py,anchor='e',text=port,fill='#a8c6d0',font=('Segoe UI',9),tags=tag)
            if typ in VALUE_NODES:
                px,py=self.data_pin_location(id_,'value',True)
                value_col='#6ea8ff' if VALUE_OUTPUT_TYPES[typ]=='object' else '#c89aff' if VALUE_OUTPUT_TYPES[typ]=='bool' else '#8fe0ae' if VALUE_OUTPUT_TYPES[typ]=='vector' else '#ffb568'
                c.create_oval(px-7,py-7,px+7,py+7,fill=value_col,outline='',tags=(f'data-output:{id_}:value',))
                c.create_text(px-12,py,anchor='e',text=VALUE_OUTPUT_TYPES[typ],fill=value_col,font=('Segoe UI',9),tags=tag)
            for field in VALUE_INPUTS[typ]:
                px,py=self.data_pin_location(id_,field,False)
                used=any(e['to']==id_ and e['input']==field for e in self.graph.get('data_links',[]))
                col='#6ea8ff' if VALUE_INPUT_TYPES[typ].get(field)=='object' else '#c89aff' if VALUE_INPUT_TYPES[typ].get(field)=='bool' else '#8fe0ae' if VALUE_INPUT_TYPES[typ].get(field)=='vector' else '#ffb568'
                c.create_oval(px-6,py-6,px+6,py+6,fill=col if used else PANEL,
                             outline=col,tags=(f'data-input:{id_}:{field}',))
                c.create_text(px+12,py,anchor='w',text=field,fill=col,font=('Segoe UI',9),tags=tag)

    def on_press(self,e):
        c=self.canvas;x=c.canvasx(e.x);y=c.canvasy(e.y)
        tag=c.gettags('current')
        outputs=[t for t in tag if t.startswith('output:')]
        inputs=[t for t in tag if t.startswith('input:')]
        data_outputs=[t for t in tag if t.startswith('data-output:')]
        data_inputs=[t for t in tag if t.startswith('data-input:')]
        nodes=[t for t in tag if t.startswith('node:')]
        if outputs or data_outputs:
            token=(outputs or data_outputs)[0]
            _,id_,port=token.split(':',2)
            self.pending=('flow' if outputs else 'data',id_,port)
            self.message.set(f'Connecting {id_}.{port}: click a matching input socket.')
            self.draw();return
        if inputs or data_inputs:
            token=(inputs or data_inputs)[0]
            bits=token.split(':');id_=bits[1]
            if self.pending:
                mode,src,port=self.pending
                if src==id_:self.message.set('Cannot connect node to itself')
                elif (mode=='flow')!=bool(inputs):self.message.set('Aqua flow ↔ aqua; orange value ↔ orange')
                elif mode=='flow':
                    links=self.graph['links'];backup=[e.copy() for e in links]
                    links[:]=[e for e in links if not (e['from']==src and e['port']==port) and e['to']!=id_]
                    links.append({'from':src,'port':port,'to':id_})
                    try:compile_graph(self.doc)
                    except ValueError as err:links[:]=backup;self.message.set('Rejected: '+str(err))
                    else:self.message.set(f'Connected {src}.{port} → {id_}')
                else:
                    field=bits[2];links=self.graph['data_links'];backup=[e.copy() for e in links]
                    links[:]=[e for e in links if not(e['to']==id_ and e['input']==field)]
                    links.append({'from':src,'port':port,'to':id_,'input':field})
                    try:compile_graph(self.doc)
                    except ValueError as err:links[:]=backup;self.message.set('Rejected: '+str(err))
                    else:self.message.set(f'Connected value {src} → {id_}.{field}')
                self.pending=None;self.draw()
            return
        if nodes:
            id_=nodes[0].split(':',1)[1];self.selected=id_;self.show_params()
            node=self.get_node(id_);self.drag=(id_,x-node['x'],y-node['y']);self.pending=None;self.draw()
        else:self.pending=None;self.selected=None;self.show_params();self.draw()

    def on_motion(self,e):
        if not self.drag:return
        id_,ox,oy=self.drag;node=self.get_node(id_)
        if node:
            node['x']=max(5,int(self.canvas.canvasx(e.x)-ox))
            node['y']=max(5,int(self.canvas.canvasy(e.y)-oy))
            self.owner._dirty=True;self.draw()

    def right_click(self,e):
        tags=self.canvas.gettags('current')
        dwire=[t for t in tags if t.startswith('data-wire:')]
        if dwire:
            _,src,dst,key=dwire[0].split(':',3)
            self.graph['data_links'][:]=[l for l in self.graph['data_links'] if not(l['from']==src and l['to']==dst and l['input']==key)]
            self.owner._dirty=True;self.message.set('Disconnected value '+src+'.value → '+dst+'.'+key);self.draw();return
        wire=[t for t in tags if t.startswith('wire:')]
        if wire:
            _,src,port=wire[0].split(':',2)
            self.graph['links'][:]=[l for l in self.graph['links'] if not (l['from']==src and l['port']==port)]
            self.owner._dirty=True;self.message.set('Disconnected '+src+'.'+port);self.draw()

    def show_params(self):
        for child in self.param_panel.winfo_children():child.destroy()
        node=self.get_node(self.selected)
        self.param_vars={}  # Keep Tk StringVars alive after the inspector function returns.
        if not node:
            ttk.Label(self.param_panel,text='NODE INSPECTOR',font=('Segoe UI',11,'bold')).pack(anchor='w')
            ttk.Label(self.param_panel,text='Click a node to edit it.\n\nCyan = flow. Orange = number. Purple = bool. Green = vector. Blue = object reference.\nRight click wire: disconnect.\n\nGraph runs on GBA as compiled C.',wraplength=220,justify='left').pack(anchor='w',pady=20)
            return
        typ=node['type'];p=node.setdefault('params',{})
        ttk.Label(self.param_panel,text=NODE_TYPES[typ][0],font=('Segoe UI',11,'bold')).pack(anchor='w',pady=(2,12))
        ttk.Label(self.param_panel,text=node['id']+' • '+typ).pack(anchor='w')
        for key,kind in PARAMS[typ]:
            ttk.Label(self.param_panel,text=key.capitalize()).pack(anchor='w',pady=(12,3))
            v=tk.StringVar(value=str(p.get(key,'')))
            self.param_vars[key]=v
            def update(*_,name=key,var=v,node=node,kind=kind):
                value=var.get()
                if kind in ('object','scene','animation','sound','ui'):value=value.split(':')[0]
                if node.setdefault('params',{}).get(name)!=value:self.owner._dirty=True
                node['params'][name]=value
            if kind in ('key','object','operator','variable','variable_optional','bool','array','scene','animation','sound','ui'):
                if kind=='array':values=list(self.doc.get('arrays',{}))
                elif kind=='bool':values=['true','false']
                elif kind=='variable_optional':values=['']+list(self.doc.get('variables',{}))
                elif kind=='key':values=list(KEYS)
                elif kind=='object':values=[f'{i}: {o.get("name", "Object")}' for i,o in enumerate(self.doc.get('objects',[]))]
                elif kind=='operator':values=['==','!=','>','>=','<','<=']
                elif kind=='scene':values=[f'{i}: {o.get("name","Scene")}' for i,o in enumerate(self.doc.get('scenes',[]))]
                elif kind=='animation':values=[f'{i}: {o.get("name","Clip")}' for i,o in enumerate(self.doc.get('animations',[]))]
                elif kind=='sound':values=[f'{i}: {o.get("name","Sound")}' for i,o in enumerate(self.doc.get('sounds',[]))]
                elif kind=='ui':values=[f'{i}: {o.get("name","UI")}' for i,o in enumerate(self.doc.get('hud',[]))]
                else:values=list(self.doc.get('variables',{'score':0}))
                if kind in ('object','scene','animation','sound','ui') and values:
                    for value in values:
                        if value.split(':')[0]==str(p.get(key,'0')):v.set(value);break
                if kind=='variable' and values and v.get() not in values:v.set(values[0])
                field=ttk.Combobox(self.param_panel,textvariable=v,values=values,state='readonly',width=21)
                field.bind('<<ComboboxSelected>>',lambda e,callback=update:callback())
            else:
                field=ttk.Entry(self.param_panel,textvariable=v,width=24)
                field.bind('<KeyRelease>',lambda e,callback=update:callback())
                field.bind('<FocusOut>',lambda e,callback=update:callback())
            field.pack(fill='x')
            update()
        ttk.Label(self.param_panel,text='Flow runs along cyan wires. Number values come from orange wires if connected, otherwise inspector values.\n\nA branch runs only its TRUE or FALSE output.\nKeep graph acyclic (use OnUpdate loops).',wraplength=220,justify='left').pack(anchor='w',pady=22)
