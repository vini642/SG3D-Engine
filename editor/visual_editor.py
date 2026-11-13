#!/usr/bin/env python3
"""SG3D Studio v1.0: lightweight visual GBA 3D game editor.

Run: python editor/visual_editor.py
Optional: pip install Pillow (for PNG texture thumbnail colour in preview).
The preview uses flat shaded 3D polygons, *not* the GBA assembly rasterizer.
"""
import copy
import json
import math
import os
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
sys.path.insert(0,str(ROOT/'editor'))
from project_export import MODES, export_project, load_project, parse_obj, resolve

ACCENT='#4bd6cc';BG='#17202d';PANEL='#1f2a39';LIGHT='#d9e6ef'

def transform(vertex,obj):
    x,y,z=[t*float(obj.get('scale',1.0)) for t in vertex]
    yaw,pitch=[math.radians(v) for v in obj.get('rotation',[0,0])]
    x,z=x*math.cos(yaw)+z*math.sin(yaw),z*math.cos(yaw)-x*math.sin(yaw)
    y,z=y*math.cos(pitch)-z*math.sin(pitch),y*math.sin(pitch)+z*math.cos(pitch)
    return (x+obj['position'][0],y+obj['position'][1],z+obj['position'][2])

def view_transform(vertex,camera):
    x=vertex[0]-camera['position'][0]
    y=vertex[1]-camera['position'][1]
    z=vertex[2]-camera['position'][2]
    yaw,pitch=[math.radians(-v) for v in camera['rotation']]
    x,z=x*math.cos(yaw)+z*math.sin(yaw),z*math.cos(yaw)-x*math.sin(yaw)
    y,z=y*math.cos(pitch)-z*math.sin(pitch),y*math.sin(pitch)+z*math.cos(pitch)
    return x,y,z

class Studio(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('SG3D Studio • Universal Scripting Preview')
        self.geometry('1230x780');self.minsize(940,560)
        self.configure(bg=BG)
        style=ttk.Style(self);style.theme_use('clam')
        style.configure('.',background=PANEL,foreground=LIGHT,fieldbackground='#2b3c4e',bordercolor='#35495d')
        style.configure('TFrame',background=PANEL)
        style.configure('TLabel',background=PANEL,foreground=LIGHT)
        style.configure('TButton',padding=(8,6),background='#304457',foreground=LIGHT)
        style.map('TButton',background=[('active','#356575')])
        style.configure('TEntry',fieldbackground='#293949',foreground=LIGHT)
        style.configure('TCombobox',fieldbackground='#293949',foreground=LIGHT)
        style.map('TCombobox',fieldbackground=[('readonly','#293949')],foreground=[('readonly',LIGHT)])
        style.configure('Treeview',fieldbackground='#243344',background='#243344',foreground=LIGHT,rowheight=29)
        style.configure('Treeview.Heading',background='#324557',foreground=LIGHT)
        style.map('Treeview',background=[('selected','#278c89')],foreground=[('selected','#ffffff')])
        # Open a COPY of the sample. Save opens Save As, preserving shipped examples.
        self.path=None
        self.doc,self.asset_base=load_project(ROOT/'examples/collectathon_v12.sg3d.json')
        self._prepare_scenes()
        self._dirty=False
        self.sim=None;self.play_keys=set();self._play_after=None;self._gizmo_drag=None
        self.cache={};self.texcache={};self._selected=None;self.drag=None;self.preview_wire=tk.BooleanVar(value=False)
        self.preview_gba=tk.BooleanVar(value=True);self.preview_tex=tk.BooleanVar(value=True);self._preview_photo=None
        self.stat=tk.StringVar(value='Sample loaded (unsaved) • Save As to start a project • GBA preview is approximate')
        self.build_gui();self._bind_scene(self.doc['active_scene']);self.populate();self.after(150,self.draw_scene)
        self.bind_all('<Control-s>',lambda e:self.save_scene(),add='+')
        self.bind_all('<Control-o>',lambda e:self.open_scene(),add='+')
        self.bind_all('<Control-Shift-S>',lambda e:self.save_as(),add='+')

    def build_gui(self):
        menubar=tk.Menu(self)
        file=tk.Menu(menubar,tearoff=False)
        for name,command in [('New project',self.new_scene),('Open project...',self.open_scene),
                             ('Save',self.save_scene),('Save as...',self.save_as),('Save all assets IN project...',self.save_self_contained),('Package portable project...',self.package_project),('Check project...',self.check_project),
                             ('Node scripts...',self.edit_scripts),('Custom C scripts...',self.edit_c_scripts),('Orbit camera / skybox...',self.edit_camera_sky),('Racing controller preset...',self.make_racer),('Animations...',self.edit_animations),('Sounds...',self.edit_sounds),('HUD elements...',self.edit_hud),('Project settings...',self.edit_settings),
                             ('Export C project',self.export),('Export + build ROM',self.build_rom)]:
            file.add_command(label=name,command=command)
        menubar.add_cascade(label='File',menu=file)
        tools_menu=tk.Menu(menubar,tearoff=False)
        tools_menu.add_command(label='Check project',command=self.check_project)
        tools_menu.add_command(label='Camera / skybox',command=self.edit_camera_sky)
        tools_menu.add_command(label='Add racing controller',command=self.make_racer)
        tools_menu.add_command(label='Save self-contained project',command=self.save_self_contained)
        tools_menu.add_command(label='Package project ZIP',command=self.package_project)
        menubar.add_cascade(label='Tools',menu=tools_menu)
        helpmenu=tk.Menu(menubar,tearoff=False)
        helpmenu.add_command(label='Controls / about',command=self.show_help)
        helpmenu.add_command(label='Quick start guide',command=self.show_quick_start)
        menubar.add_cascade(label='Help',menu=helpmenu);self.config(menu=menubar)
        bar=ttk.Frame(self,padding=(8,5));bar.pack(fill='x')
        bar2=ttk.Frame(self,padding=(8,2));bar2.pack(fill='x')
        for button_index,(label,action) in enumerate([('＋ Cube',lambda:self.add_primitive('cube.obj')),
                             ('＋ Pyramid',lambda:self.add_primitive('pyramid.obj')),('＋ Empty',self.add_empty),
                             ('Import OBJ...',self.import_obj),('Duplicate',self.duplicate),
                             ('Delete',self.delete),('Node Scripts',self.edit_scripts),('C Scripts',self.edit_c_scripts),('Animations',self.edit_animations),('Sounds',self.edit_sounds),('HUD',self.edit_hud),('Settings',self.edit_settings),('▶ Play',self.play),
                             ('■ Stop',self.stop),('Camera / Sky',self.edit_camera_sky),('Save',self.save_scene),('Export GBA',self.build_rom)]):
            ttk.Button(bar if button_index<6 else bar2,text=label,command=action).pack(side='left',padx=3)
        ttk.Checkbutton(bar2,text='Wireframe (PC)',variable=self.preview_wire,command=self.draw_scene).pack(side='right',padx=5)
        ttk.Checkbutton(bar2,text='GBA pixels',variable=self.preview_gba,command=self.draw_scene).pack(side='right',padx=5)
        ttk.Checkbutton(bar2,text='Textures',variable=self.preview_tex,command=self.draw_scene).pack(side='right',padx=5)

        # IMPORTANT: Do not use a ttk.Panedwindow for the primary editor layout.
        # On some Windows/Tk configurations the deferred sash positioning from v0.8
        # collapsed the hierarchy and viewport, leaving ONLY the inspector visible.
        # The grid below gives sidebars fixed, non-propagating widths and gives the
        # viewport ALL remaining width, even after maximizing or resizing the app.
        body=ttk.Frame(self)
        body.pack(fill='both',expand=True,padx=8,pady=(0,6))
        body.grid_rowconfigure(0,weight=1)
        body.grid_columnconfigure(0,weight=0,minsize=215)
        body.grid_columnconfigure(1,weight=1,minsize=280)
        body.grid_columnconfigure(2,weight=0,minsize=310)

        left=ttk.Frame(body,width=215,padding=7)
        left.grid(row=0,column=0,sticky='nsew')
        left.grid_propagate(False)
        ttk.Label(left,text='SCENES / LEVELS',font=('Segoe UI',10,'bold')).pack(anchor='w',pady=(3,5))
        self.scene_var=tk.StringVar()
        self.scene_list=ttk.Combobox(left,textvariable=self.scene_var,state='readonly',width=19)
        self.scene_list.pack(fill='x',pady=(0,4))
        self.scene_list.bind('<<ComboboxSelected>>',self._select_scene)
        scene_tools=ttk.Frame(left);scene_tools.pack(fill='x',pady=(0,8))
        ttk.Button(scene_tools,text='+ Scene',command=self.add_scene).pack(side='left')
        ttk.Button(scene_tools,text='Rename',command=self.rename_scene).pack(side='left',padx=3)
        ttk.Button(scene_tools,text='Delete',command=self.remove_scene).pack(side='left')
        ttk.Button(left,text='Set current as startup scene',command=self.set_startup_scene).pack(fill='x',pady=(0,8))
        ttk.Label(left,text='SCENE HIERARCHY',font=('Segoe UI',10,'bold')).pack(anchor='w',pady=(3,8))
        self.tree=ttk.Treeview(left,show='tree',selectmode='browse')
        self.tree.column('#0',width=185,minwidth=170,stretch=True)
        self.tree.pack(fill='both',expand=True)
        self.tree.bind('<<TreeviewSelect>>',self.on_tree_select)

        center=ttk.Frame(body)
        center.grid(row=0,column=1,sticky='nsew',padx=(3,3))
        center.grid_rowconfigure(0,weight=1)
        center.grid_columnconfigure(0,weight=1)
        self.canvas=tk.Canvas(center,bg='#14273a',highlightthickness=0,cursor='fleur',width=480,height=320)
        self.canvas.grid(row=0,column=0,sticky='nsew')
        self.canvas.bind('<Configure>',lambda e:self.draw_scene())
        self.canvas.bind('<ButtonPress-1>',self.drag_start)
        self.canvas.bind('<ButtonRelease-1>',lambda e:setattr(self,'_gizmo_drag',None))
        self.canvas.bind('<B1-Motion>',self.drag_camera)
        self.canvas.bind('<MouseWheel>',self.zoom)
        self.canvas.bind('<Button-4>',lambda e:self.zoom_step(1))
        self.canvas.bind('<Button-5>',lambda e:self.zoom_step(-1))
        self.canvas.bind('<KeyPress>',self.move_key)
        self.bind_all('<KeyPress>',self._on_keypress,add='+')
        self.bind_all('<KeyRelease>',self._on_keyrelease,add='+')
        self.canvas.focus_set()

        # Fixed-width, VERTICALLY SCROLLABLE inspector.  Its children cannot push
        # the viewport off-screen on high-DPI Windows or narrow displays.
        inspector_box=ttk.Frame(body,width=310)
        inspector_box.grid(row=0,column=2,sticky='nsew')
        inspector_box.grid_propagate(False)
        self.inspector_scroll=tk.Canvas(inspector_box,bg=PANEL,highlightthickness=0,borderwidth=0)
        scrollbar=ttk.Scrollbar(inspector_box,orient='vertical',command=self.inspector_scroll.yview)
        self.inspector_scroll.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right',fill='y')
        self.inspector_scroll.pack(side='left',fill='both',expand=True)
        right=ttk.Frame(self.inspector_scroll,padding=10)
        inspector_window=self.inspector_scroll.create_window((0,0),window=right,anchor='nw')
        right.bind('<Configure>',lambda e:self.inspector_scroll.configure(
            scrollregion=self.inspector_scroll.bbox('all')))
        self.inspector_scroll.bind('<Configure>',lambda e:self.inspector_scroll.itemconfigure(
            inspector_window,width=e.width))
        ttk.Label(right,text='INSPECTOR',font=('Segoe UI',10,'bold')).pack(anchor='w',pady=(3,10))
        self.vars={}
        for key,label in [('name','Object name'),('x','Position X'),('y','Position Y'),('z','Position Z'),
                          ('yaw','Yaw (degrees)'),('pitch','Pitch (degrees)'),('scale','Scale'),
                          ('mesh','Mesh (.obj)'),('texture','Override texture (.png)')]:
            ttk.Label(right,text=label).pack(fill='x',pady=(7,2))
            row=ttk.Frame(right);row.pack(fill='x')
            v=tk.StringVar();self.vars[key]=v
            entry=ttk.Entry(row,textvariable=v);entry.pack(side='left',fill='x',expand=True)
            entry.bind('<Return>',self.apply_inspector);entry.bind('<FocusOut>',self.apply_inspector)
            if key=='texture':
                ttk.Button(row,text='...',width=3,command=self.browse_texture).pack(side='right')
        ttk.Label(right,text='CHARACTER FACING',font=('Segoe UI',10,'bold')).pack(anchor='w',pady=(12,2))
        self.face_movement=tk.BooleanVar(value=False)
        ttk.Checkbutton(right,text='Face movement direction (Play / GBA)',
                        variable=self.face_movement,command=self.apply_inspector).pack(anchor='w')
        for key,title in (('facing_smooth','Turn smoothing (0.01 to 1.0)'),
                          ('facing_offset','Model forward offset (degrees)')):
            ttk.Label(right,text=title).pack(fill='x',pady=(5,2))
            var=tk.StringVar();self.vars[key]=var
            entry=ttk.Entry(right,textvariable=var);entry.pack(fill='x')
            entry.bind('<Return>',self.apply_inspector)
            entry.bind('<FocusOut>',self.apply_inspector)
        ttk.Label(right,text='0.25 = smooth turn; 1 = instant. Offset 180 flips backwards models.',
                  wraplength=260).pack(anchor='w',pady=(4,2))
        ttk.Label(right,text='PHYSICS / COLLISION',font=('Segoe UI',10,'bold')).pack(anchor='w',pady=(12,2))
        self.phy_dynamic=tk.BooleanVar(value=False)
        self.phy_solid=tk.BooleanVar(value=False)
        ttk.Checkbutton(right,text='Dynamic (gravity / jump)',variable=self.phy_dynamic,
                        command=self.apply_inspector).pack(anchor='w')
        ttk.Checkbutton(right,text='Solid box collider',variable=self.phy_solid,
                        command=self.apply_inspector).pack(anchor='w')
        ttk.Label(right,text='Uses OBJ bounding box unless physics.half_extents is set.',
                  wraplength=255).pack(anchor='w')
        ttk.Button(right,text='Custom properties + C scripts...',command=self.edit_c_scripts).pack(fill='x',pady=(8,3))
        ttk.Button(right,text='Camera follow selected',command=self.set_follow).pack(fill='x',pady=(10,2))
        ttk.Button(right,text='Stop camera follow',command=self.clear_follow).pack(fill='x',pady=2)
        ttk.Label(right,text='Raster mode').pack(fill='x',pady=(9,2))
        self.vars['mode']=tk.StringVar()
        mode=ttk.Combobox(right,textvariable=self.vars['mode'],values=list(MODES),state='readonly')
        mode.pack(fill='x');mode.bind('<<ComboboxSelected>>',self.apply_inspector)
        ttk.Button(right,text='Apply properties',command=self.apply_inspector).pack(fill='x',pady=(13,2))
        ttk.Label(right,text='Drag viewport = orbit camera\nWheel = camera distance\nW/S = forward/back\nA/D = strafe; Q/E = up/down\n\nPreview: GBA 120×80 → 240×160\nRGB332 colors + affine textures\nExport: real ARM rasterizer',justify='left').pack(fill='x',pady=18)
        ttk.Label(self,textvariable=self.stat,padding=(12,5),anchor='w').pack(fill='x')

    def _prepare_scenes(self):
        # v0.9 project files become one-scene projects without losing script data.
        if 'scenes' not in self.doc:
            self.doc['scenes']=[{k:self.doc.get(k,default) for k,default in (
                ('name',self.doc.get('name','Scene 1')),('objects',[]),
                ('camera',{'position':[0,0,0],'rotation':[0,0]}),
                ('scripts',{'nodes':[],'links':[]}),('physics',{}),('animations',[]),('hud',[]),('skybox',{}))}]
            self.doc['initial_scene']=0
        self.doc.setdefault('variables',{})
        self.doc.setdefault('sounds',[])
        self.doc.setdefault('settings',{'title':'SG3D GAME','code':'SG12','maker':'00','profiler':False})
        self._bind_scene(int(self.doc.get('active_scene',0)))

    def _bind_scene(self,index):
        if not 0<=index<len(self.doc['scenes']):raise ValueError('invalid scene index')
        scene=self.doc['scenes'][index]
        for key,default in (('objects',[]),('camera',{'position':[0,0,0],'rotation':[0,0]}),
                            ('scripts',{'nodes':[],'links':[]}),('physics',{}),('animations',[]),('hud',[]),('skybox',{})):
            self.doc[key]=scene.setdefault(key,copy.deepcopy(default))
        self.doc['active_scene']=index
        if hasattr(self,'scene_list'):
            self.scene_list.configure(values=[s.get('name',f'Scene {i+1}') for i,s in enumerate(self.doc['scenes'])])
            self.scene_list.current(index)

    def _select_scene(self,event=None):
        i=self.scene_list.current()
        if i<0:return
        self.stop();self._bind_scene(i);self._selected=None;self.populate()
        self.stat.set('Editing scene: '+self.doc['scenes'][i]['name'])

    def add_scene(self):
        from tkinter import simpledialog
        name=simpledialog.askstring('New scene','Scene name:',initialvalue=f'Scene {len(self.doc["scenes"])+1}',parent=self)
        if not name:return
        if any(s['name']==name for s in self.doc['scenes']):
            messagebox.showerror('Duplicate','Scene names must be unique',parent=self);return
        self.doc['scenes'].append({'name':name,'objects':[],
           'camera':{'position':[0,0,0],'rotation':[0,0]},
           'scripts':{'nodes':[],'links':[],'data_links':[]},'physics':{},'animations':[],'hud':[],'skybox':{}})
        self._dirty=True;self.stop();self._bind_scene(len(self.doc['scenes'])-1);self._selected=None
        self.populate();self.stat.set('Added scene '+name+' • add at least one object to export')

    def rename_scene(self):
        from tkinter import simpledialog
        sc=self.doc['scenes'][self.doc['active_scene']]
        name=simpledialog.askstring('Rename scene','New name:',initialvalue=sc['name'],parent=self)
        if not name:return
        if any(s is not sc and s['name']==name for s in self.doc['scenes']):
            messagebox.showerror('Duplicate','Scene names must be unique',parent=self);return
        sc['name']=name;self._dirty=True;self._bind_scene(self.doc['active_scene'])

    def set_startup_scene(self):
        self.doc['initial_scene']=self.doc['active_scene']
        self._dirty=True
        self.stat.set('Startup level: '+self.doc['scenes'][self.doc['active_scene']]['name'])

    def remove_scene(self):
        if len(self.doc['scenes'])<2:
            messagebox.showwarning('Cannot delete','A project needs at least one scene.',parent=self);return
        i=self.doc['active_scene']
        if not messagebox.askyesno('Delete scene',f'Delete {self.doc["scenes"][i]["name"]}?\nAll its objects and scripts will be removed.',parent=self):return
        self.stop();del self.doc['scenes'][i]
        # Prevent LoadScene indices silently changing to a different level.
        for sc in self.doc['scenes']:
            for node in (sc.get('scripts') or {}).get('nodes',[]):
                if node.get('type')=='LoadScene':
                    try:t=int(node.get('params',{}).get('scene','0'))
                    except ValueError:continue
                    if t==i:node['params']['scene']='-1' # Export reports broken target
                    elif t>i:node['params']['scene']=str(t-1)
        current=self.doc.get('initial_scene',0)
        self.doc['initial_scene']=0 if current==i else max(0,current-(current>i))
        self._dirty=True;self._bind_scene(min(i,len(self.doc['scenes'])-1));self._selected=None;self.populate()

    def selected_index(self):
        selected=self.tree.selection()
        if not selected:return None
        idx=int(selected[0]);return idx if 0<=idx<len(self.doc['objects']) else None

    def populate(self,selected=None):
        old=selected if selected is not None else self._selected
        self.tree.delete(*self.tree.get_children())
        for i,obj in enumerate(self.doc['objects']):
            self.tree.insert('',tk.END,iid=str(i),text='  ◆  '+obj.get('name','Unnamed'))
        if old is not None and 0<=old<len(self.doc['objects']):
            self.tree.selection_set(str(old));self.tree.see(str(old))
        elif self.doc['objects']:
            self.tree.selection_set('0')
        self.on_tree_select();self.draw_scene()

    def on_tree_select(self,event=None):
        index=self.selected_index();self._selected=index
        if index is None:
            for v in self.vars.values():v.set('')
            self.draw_scene();return
        obj=self.doc['objects'][index]
        values={'name':obj.get('name','Object'), 'mesh':obj.get('mesh',''),
                'texture':obj.get('texture',''),'mode':obj.get('mode','texture'),
                'x':obj['position'][0],'y':obj['position'][1],'z':obj['position'][2],
                'yaw':obj['rotation'][0],'pitch':obj['rotation'][1],'scale':obj.get('scale',1),
                'facing_smooth':obj.get('facing_smooth',0.25),'facing_offset':obj.get('facing_offset',0)}
        for k,v in values.items():self.vars[k].set(str(v))
        phy=obj.get('physics') or {}
        self.face_movement.set(bool(obj.get('face_movement',False)))
        self.phy_dynamic.set(bool(phy.get('dynamic',False)))
        self.phy_solid.set(bool(phy.get('solid',False)))
        self.draw_scene()

    def apply_inspector(self,event=None):
        index=self.selected_index()
        if index is None:return
        old=self.doc['objects'][index]
        try:
            new=copy.deepcopy(old)
            new.update(name=self.vars['name'].get().strip() or 'Unnamed',
                       mesh=self.vars['mesh'].get().strip(),
                       texture=self.vars['texture'].get().strip(),mode=self.vars['mode'].get())
            new['position']=[float(self.vars[k].get()) for k in ('x','y','z')]
            new['rotation']=[float(self.vars[k].get()) for k in ('yaw','pitch')]
            new['scale']=float(self.vars['scale'].get())
            new['face_movement']=bool(self.face_movement.get())
            new['facing_smooth']=float(self.vars['facing_smooth'].get())
            new['facing_offset']=float(self.vars['facing_offset'].get())
            if not math.isfinite(new['facing_offset']):raise ValueError('forward offset must be finite')
            if not math.isfinite(new['facing_smooth']) or not 0 < new['facing_smooth'] <= 1:
                raise ValueError('turn smoothing must be > 0 and <= 1')
            if not 0<new['scale']<=255:raise ValueError('scale must be >0 and <=255')
            if new['mode'] not in MODES:raise ValueError('unknown render mode')
            physics=new.get('physics') or {}
            if self.phy_dynamic.get() or self.phy_solid.get() or physics:
                physics['dynamic']=bool(self.phy_dynamic.get())
                physics['solid']=bool(self.phy_solid.get())
                new['physics']=physics
            if new != old:
                self._dirty=True
                self.stat.set('Modified scene (save to keep changes)')
            self.doc['objects'][index]=new
            self.tree.item(str(index),text='  ◆  '+new['name'])
            self.draw_scene()
        except ValueError as e:
            self.stat.set('Invalid property: '+str(e))

    def add_primitive(self,name):
        self._dirty=True
        path=ROOT/'examples'/name
        self.doc['objects'].append(dict(name=name.removesuffix('.obj').title(),mesh=os.path.relpath(path,self._scene_base()),
                                         position=[0,0,8],rotation=[0,0],scale=1.0,mode='texture',texture=''))
        self.populate(len(self.doc['objects'])-1)

    def add_empty(self):
        self._dirty=True
        self.doc['objects'].append(dict(name='Empty Object',mesh='',position=[0,0,8],rotation=[0,0],scale=1.0,mode='flat',texture='',properties={},c_scripts=[]))
        self.populate(len(self.doc['objects'])-1)

    def import_obj(self):
        path=filedialog.askopenfilename(filetypes=[('Wavefront OBJ','*.obj')],title='Import 3D model')
        if not path:return
        try:parse_obj(Path(path))
        except Exception as e:messagebox.showerror('Cannot import OBJ',str(e));return
        self._dirty=True
        self.doc['objects'].append(dict(name=Path(path).stem,mesh=os.path.relpath(path,self._scene_base()),
                                         position=[0,0,8],rotation=[0,0],scale=1.0,mode='texture',texture=''))
        self.populate(len(self.doc['objects'])-1)

    def edit_c_scripts(self):
        """Attach/edit native GBA C scripts and reusable per-object properties.

        The editor can edit source text, but only the ARM exporter executes C;
        desktop Play remains a lightweight node/physics preview.
        """
        from tkinter import simpledialog
        import re
        from custom_scripts import starter
        index=self.selected_index()
        if index is None:
            messagebox.showinfo('C scripts','Select an object first.',parent=self);return
        obj=self.doc['objects'][index]
        paths=obj.setdefault('c_scripts',[])
        win=tk.Toplevel(self);win.title('C scripts: '+obj.get('name','Object'))
        win.geometry('590x570')
        frame=ttk.Frame(win,padding=12);frame.pack(fill='both',expand=True)
        ttk.Label(frame,text='Attach any C component to this object. Each .c file is compiled into the GBA ROM.',wraplength=540).pack(anchor='w')
        lst=tk.Listbox(frame,height=5,bg='#263748',fg='#f2f5f6',selectbackground='#276e75')
        lst.pack(fill='x',pady=7)
        def refresh():
            lst.delete(0,tk.END)
            for x in paths:lst.insert(tk.END,str(x))
        def choose():
            picks=lst.curselection()
            return picks[0] if picks else None
        def attach():
            filename=filedialog.askopenfilename(parent=win,filetypes=[('GBA C source','*.c')])
            if filename:
                rel=os.path.relpath(filename,self._scene_base())
                if rel not in paths:
                    paths.append(rel);self._dirty=True;refresh()
        def create():
            name=simpledialog.askstring('New C component','Script filename (letters, numbers, underscores):',parent=win)
            if not name:return
            if not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*',name):
                messagebox.showerror('Invalid name','Use a C identifier, such as my_controller.',parent=win);return
            folder=(self.path.parent if self.path else ROOT/'examples')/'scripts'
            folder.mkdir(parents=True,exist_ok=True)
            dest=folder/(name+'.c')
            if dest.exists():
                messagebox.showerror('Already exists','That script already exists.',parent=win);return
            dest.write_text(starter(name),encoding='utf-8')
            paths.append(os.path.relpath(dest,self._scene_base()))
            self._dirty=True;refresh()
        def edit_source():
            i=choose()
            if i is None:return
            path=resolve(self._scene_base(),paths[i])
            if not path.is_file():
                messagebox.showerror('Missing source',str(path),parent=win);return
            sub=tk.Toplevel(win);sub.title('Edit C • '+path.name);sub.geometry('900x640')
            editor=tk.Text(sub,undo=True,wrap='none',font=('Consolas',11),bg='#162231',fg='#ecf1f8',insertbackground='white')
            editor.pack(fill='both',expand=True,padx=6,pady=6)
            editor.insert('1.0',path.read_text(encoding='utf-8-sig'))
            def save_source():
                path.write_text(editor.get('1.0','end-1c'),encoding='utf8')
                self._dirty=True
                self.stat.set('Updated C script '+path.name+' • Export GBA to compile')
                sub.destroy()
            ttk.Button(sub,text='Save C source',command=save_source).pack(pady=5)
        def detach():
            i=choose()
            if i is not None:
                paths.pop(i);self._dirty=True;refresh()
        row=ttk.Frame(frame);row.pack(fill='x')
        for label,callback in [('New .c',create),('Attach .c',attach),('Edit code',edit_source),('Detach',detach)]:
            ttk.Button(row,text=label,command=callback).pack(side='left',padx=3)
        ttk.Label(frame,text='Custom numeric properties (JSON object; 256 internal units = 1.0):').pack(anchor='w',pady=(18,4))
        properties=tk.Text(frame,height=10,font=('Consolas',11),bg='#243344',fg='#f3f7fc',insertbackground='white')
        properties.pack(fill='both',expand=True)
        properties.insert('1.0',json.dumps(obj.get('properties',{}),indent=2))
        def save_properties():
            import re,math
            try:
                value=json.loads(properties.get('1.0','end-1c'))
                if not isinstance(value,dict) or len(value)>16:raise ValueError('Expected an object with up to 16 properties')
                for k,v in value.items():
                    if not re.fullmatch('[A-Za-z_][A-Za-z_0-9]*',k):raise ValueError('Invalid property name: '+str(k))
                    if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or abs(v)>=8388608:
                        raise ValueError('Property values must be finite numbers fitting 24.8 fixed point')
                obj['properties']=value;self._dirty=True
                self.stat.set('Saved properties for '+obj.get('name','object'))
                win.destroy()
            except (ValueError,TypeError) as e:
                messagebox.showerror('Properties error',str(e),parent=win)
        ttk.Button(frame,text='Apply properties and close',command=save_properties).pack(fill='x',pady=10)
        ttk.Label(frame,text='Note: custom C scripts run in exported GBA ROMs, not desktop Play.',wraplength=540).pack(anchor='w')
        refresh()

    def browse_texture(self):
        path=filedialog.askopenfilename(filetypes=[('PNG images','*.png')])
        if path:
            self.vars['texture'].set(os.path.relpath(path,self._scene_base()))
            self.apply_inspector()

    def duplicate(self):
        idx=self.selected_index()
        if idx is None:return
        o=copy.deepcopy(self.doc['objects'][idx]);o['name']+=' Copy';o['position'][0]+=1.0
        self._dirty=True
        self.doc['objects'].append(o);self.populate(len(self.doc['objects'])-1)

    def delete(self):
        idx=self.selected_index()
        if idx is None:return
        del self.doc['objects'][idx];self._dirty=True;self.populate(min(idx,len(self.doc['objects'])-1) if self.doc['objects'] else None)

    def _confirm_discard(self):
        if not self._dirty:return True
        answer=messagebox.askyesnocancel('Unsaved changes',
                   'Save your changes before switching projects?',parent=self)
        if answer is None:return False
        if answer:return self.save_scene()
        return True

    def new_scene(self):
        if not self._confirm_discard():return
        self.stop()
        self.path=None
        self._dirty=True
        self.doc={'name':'Untitled SG3D Project','camera':{'position':[0,0,0],'rotation':[0,0]},'objects':[]}
        self.asset_base=ROOT/'examples'
        self._prepare_scenes()
        self.cache.clear();self.texcache.clear();self._selected=None;self.populate()

    def open_scene(self):
        if not self._confirm_discard():return
        self.stop()
        path=filedialog.askopenfilename(filetypes=[('SG3D scene','*.json'),('JSON','*.json')])
        if not path:return
        try:self.doc,self.asset_base=load_project(path)
        except Exception as e:messagebox.showerror('Invalid project',str(e));return
        self.path=Path(path).resolve();self._prepare_scenes();self._dirty=False;self.cache.clear();self.texcache.clear();self._selected=None;self.populate()
        self.stat.set('Opened '+self.path.name)

    def _scene_base(self):
        """Where relative asset paths currently belong, even for an unsaved scene."""
        return self.asset_base if self.doc.get('embedded_assets') else (self.path.parent if self.path is not None else ROOT/'examples')

    def _write_project(self, dest):
        """Write exactly once, atomically, and only switch paths after success."""
        import tempfile
        dest=Path(dest).resolve()
        src_base=self._scene_base()
        snapshot=copy.deepcopy(self.doc)
        if snapshot.get('embedded_assets'):
            from project_pack import save_embedded_document
            packed=save_embedded_document(snapshot,src_base,dest)
            self.doc,self.asset_base=load_project(dest)
            self._bind_scene(self.doc['active_scene'])
            self.path=dest;self._dirty=False
            self.stat.set('Saved self-contained project '+str(dest))
            # A successful save MUST return True; build_rom()/export() gate
            # their work on this result. Returning None silently disabled the
            # Export GBA button for projects with embedded assets (RC2 bug).
            return True
        for sfx in snapshot.get('sounds',[]):
            if sfx.get('file'):
                sfx['file']=os.path.relpath(resolve(src_base,sfx['file']),dest.parent)
        for scene in snapshot['scenes']:
            if (scene.get('skybox') or {}).get('file'):
                scene['skybox']['file']=os.path.relpath(resolve(src_base,scene['skybox']['file']),dest.parent)
            for item in scene.get('hud',[]):
                if item.get('file'):
                    item['file']=os.path.relpath(resolve(src_base,item['file']),dest.parent)
            for obj in scene.get('objects',[]):
                obj['c_scripts']=[os.path.relpath(resolve(src_base,v),dest.parent) for v in obj.get('c_scripts',[])]
                for key in ('mesh','texture'):
                    if obj.get(key):
                        asset=resolve(src_base,obj[key])
                        obj[key]=os.path.relpath(asset,dest.parent)
        for k in ('objects','scripts','camera','physics','animations','hud','skybox'):
            snapshot[k]=snapshot['scenes'][snapshot['active_scene']].get(k,{} if k=='skybox' else [])
        dest.parent.mkdir(parents=True,exist_ok=True)
        tmp=None
        try:
            with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=dest.parent,
                                             prefix='.sg3d_',suffix='.tmp',delete=False) as f:
                tmp=Path(f.name)
                json.dump(snapshot,f,indent=2,ensure_ascii=False,allow_nan=False)
                f.write('\n')
                f.flush();os.fsync(f.fileno())
            # Windows supports os.replace on files in the same directory.
            os.replace(tmp,dest)
            tmp=None
        finally:
            if tmp is not None:tmp.unlink(missing_ok=True)
        self.doc=snapshot
        self._bind_scene(snapshot['active_scene'])
        self.path=dest
        self.asset_base=dest.parent
        self._dirty=False
        self.stat.set('Saved '+str(dest))
        return True

    def save_scene(self):
        if self.path is None:return self.save_as()
        try:return self._write_project(self.path)
        except (OSError,ValueError,TypeError) as exc:
            messagebox.showerror('Save failed',str(exc),parent=self)
            return False

    def save_as(self):
        path=filedialog.asksaveasfilename(defaultextension='.json',
                filetypes=[('SG3D scene','*.sg3d.json'),('JSON','*.json')],
                initialfile=self.path.name if self.path else 'My Game.sg3d.json',parent=self)
        if not path:return False
        try:return self._write_project(path)
        except (OSError,ValueError,TypeError) as exc:
            messagebox.showerror('Save failed',str(exc),parent=self)
            return False

    def export(self):
        if not self.save_scene():
            self.stat.set('Export cancelled: project was not saved')
            return False
        if not self._preflight():
            self.stat.set('Export cancelled by project validation')
            return False
        try:
            info=export_project(self.path)
            self.stat.set(f'Exported {info["objects"]} objects across {info.get("scenes",1)} scenes')
            if info['warnings']:messagebox.showwarning('Export warnings','\n'.join(info['warnings']))
            else:messagebox.showinfo('Exported C project','Generated C files are in generated/.\nBuild using: python build.py --main generated/main.c')
            return True
        except Exception as e:
            messagebox.showerror('Export failed',str(e));return False

    def _preflight(self):
        from project_check import check_project
        issues=check_project(document=self.doc,base=self._scene_base())
        errors=[f'{place}: {message}' for severity,place,message in issues if severity=='ERROR']
        warnings=[f'{place}: {message}' for severity,place,message in issues if severity=='WARN']
        if errors:
            messagebox.showerror('Project check failed', '\n'.join(errors[:12]),parent=self)
            return False
        if warnings:
            return messagebox.askyesno('Project warnings',
                '\n'.join(warnings[:10])+'\n\nContinue with export?',parent=self)
        return True

    def check_project(self):
        from project_check import check_project
        issues=check_project(document=self.doc,base=self._scene_base())
        if not issues:
            self.stat.set('Project check passed • no issues found')
            messagebox.showinfo('Project check', 'No missing assets or obvious project issues found.\n\nThis does not guarantee gameplay or on-hardware rendering.', parent=self)
        else:
            report='\n'.join(f'{level} • {place}: {message}' for level,place,message in issues)
            self.stat.set(f'Project check • {len(issues)} warnings/errors')
            if any(level=='ERROR' for level,_,_ in issues):
                messagebox.showerror('Project check',report[:5000],parent=self)
            else:
                messagebox.showwarning('Project check',report[:5000],parent=self)
        return issues

    def package_project(self):
        from project_pack import package_project
        dst=filedialog.asksaveasfilename(title='Package editable SG3D project',
            defaultextension='.zip',filetypes=[('ZIP archive','*.zip')],
            initialfile='SG3D_Portable_Project.zip',parent=self)
        if not dst:return False
        try:
            result=package_project(self.path,dst,document=self.doc,source_base=self._scene_base())
            self.stat.set(f'Packaged {result["assets"]} assets to {result["path"].name}')
            messagebox.showinfo('Portable project ready',
                f'{result["path"]}\n\nExtract this ZIP and open the included .sg3d.json file in SG3D Studio. All referenced assets are included.',parent=self)
            return True
        except (OSError,ValueError,TypeError,KeyError) as exc:
            messagebox.showerror('Project package failed',str(exc),parent=self)
            return False

    def build_rom(self):
        if not self.save_scene():
            self.stat.set('GBA build cancelled: project was not saved')
            return False
        if not self._preflight():
            self.stat.set('GBA build cancelled by project validation')
            return False
        path=filedialog.asksaveasfilename(title='Build GBA ROM',
            defaultextension='.gba',filetypes=[('Game Boy Advance ROM','*.gba')],
            initialfile=(self.path.stem.replace('.sg3d','') if self.path else 'SG3D_Game')+'.gba',parent=self)
        if not path:return False
        try:
            info=export_project(self.path)
            rom=Path(path).resolve()
            self.stat.set('Building GBA ROM...')
            self.update_idletasks()
            run=subprocess.run([sys.executable,str(ROOT/'build.py'),'--main','generated/main.c',
                                '--output',str(rom)],cwd=ROOT,stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT,text=True)
            log=ROOT/'build'/'last_build.log'
            log.parent.mkdir(parents=True,exist_ok=True)
            log.write_text(run.stdout,encoding='utf8')
            if run.returncode:
                raise RuntimeError(run.stdout[-4000:])
            if not rom.is_file() or rom.stat().st_size<0xC0:
                raise RuntimeError('Build finished but the GBA ROM was not created.')
            self.stat.set(f'Built ROM: {rom} • {info["objects"]} objects')
            messagebox.showinfo('GBA ROM built!',f'ROM: {rom}\n\nBuild log: {log}\nOpen the ROM in mGBA or on a flashcart.',parent=self)
            return True
        except Exception as e:
            messagebox.showerror('Build failed',str(e),parent=self)
            return False

    def show_help(self):
        messagebox.showinfo('SG3D Studio 1.0',
            'Create and edit scenes, node graphs, HUD, animations and WAV sounds.\n'
            'Save .sg3d.json projects, Check Project for obvious errors, and Package Portable Project to bundle external OBJ/MTL/PNG/WAV assets.\n\n'
            'The editor uses a 120×80 PC approximation; GBA rendering uses the original ARM rasterizer.\n'
            'Physics uses axis-aligned boxes; rotated/sloped colliders are not supported.\n'
            'The included source contains code derived from a third-party project: verify license/permission before redistributing.',parent=self)

    def show_quick_start(self):
        guide=ROOT/'QUICK_START.md'
        text=guide.read_text(encoding='utf8') if guide.exists() else 'See README.md.'
        window=tk.Toplevel(self)
        window.title('SG3D Studio • Quick start')
        window.geometry('740x540')
        panel=tk.Text(window,wrap='word',font=('Consolas',10),padx=14,pady=14)
        panel.pack(fill='both',expand=True)
        panel.insert('1.0',text)
        panel.config(state='disabled')

    def save_self_contained(self):
        """Write a shareable single JSON: OBJ/MTL/PNG/WAV data embedded."""
        from project_pack import save_embedded_document
        destination=filedialog.asksaveasfilename(title='Save single-file SG3D project',
            defaultextension='.json',filetypes=[('SG3D project','*.sg3d.json'),('JSON','*.json')])
        if not destination:return False
        try:
            save_embedded_document(self.doc,self._scene_base(),destination)
            self.doc,self.asset_base=load_project(destination)
            self.path=Path(destination).resolve();self._bind_scene(self.doc['active_scene'])
            self._dirty=False;self.stat.set('Embedded project saved: '+destination)
            return True
        except Exception as exc:
            messagebox.showerror('Cannot embed assets',str(exc),parent=self);return False

    def edit_camera_sky(self):
        from tkinter import simpledialog
        camera=self.doc.setdefault('camera',{})
        orbit=camera.setdefault('orbit',{})
        win=tk.Toplevel(self);win.title('Camera orbit and panoramic sky');win.geometry('440x590')
        panel=ttk.Frame(win,padding=15);panel.pack(fill='both',expand=True)
        enabled=tk.BooleanVar(value=bool(orbit.get('enabled',False)))
        move=tk.BooleanVar(value=bool(orbit.get('auto_move',True)))
        sync=tk.BooleanVar(value=bool(orbit.get('sync_yaw',False)))
        ttk.Checkbutton(panel,text='Enable camera orbit around selected player',variable=enabled).pack(anchor='w')
        ttk.Checkbutton(panel,text='D-pad moves player relative to camera',variable=move).pack(anchor='w')
        ttk.Label(panel,text='If existing D-pad movement nodes control this player, those\n'
                  'nodes become camera-relative and take priority over auto-move.',
                  wraplength=405,foreground='#637b90').pack(anchor='w',pady=(2,4))
        ttk.Checkbutton(panel,text='Match camera yaw to object (racing)',variable=sync).pack(anchor='w')
        settings={};defaults={'target':orbit.get('target',camera.get('follow',0)),
            'distance':orbit.get('distance',6),'height':orbit.get('height',1.5),
            'pitch':orbit.get('pitch',-10),'turn_speed':orbit.get('turn_speed',2),
            'move_speed':orbit.get('move_speed',.09)}
        for key,value in defaults.items():
            ttk.Label(panel,text=key.replace('_',' ').capitalize()).pack(anchor='w',pady=(5,0))
            var=tk.StringVar(value=str(value));ttk.Entry(panel,textvariable=var).pack(fill='x')
            settings[key]=var
        ttk.Label(panel,text='Skybox PNG (horizontal panorama; wraps with camera yaw)').pack(anchor='w',pady=(8,0))
        sky=tk.StringVar(value=(self.doc.get('skybox') or {}).get('file',''))
        row=ttk.Frame(panel);row.pack(fill='x');ttk.Entry(row,textvariable=sky).pack(side='left',expand=True,fill='x')
        def browse():
            file=filedialog.askopenfilename(parent=win,filetypes=[('PNG image','*.png')])
            if file:sky.set(os.path.relpath(file,self._scene_base()))
        ttk.Button(row,text='Browse',command=browse).pack(side='left')
        def apply():
            try:
                vals={k:(int(v.get()) if k=='target' else float(v.get())) for k,v in settings.items()}
                if not 0<=vals['target']<len(self.doc['objects']):raise ValueError('Choose an existing object index')
                if not .5<=vals['distance']<=64 or not -32<=vals['height']<=32:raise ValueError('Invalid orbit distance or height')
                orbit.update(vals);orbit.update(enabled=enabled.get(),auto_move=move.get(),sync_yaw=sync.get())
                self.doc.setdefault('skybox',{}).clear()
                if sky.get().strip():self.doc['skybox']['file']=sky.get().strip()
                self._dirty=True;self.draw_scene();win.destroy()
            except ValueError as exc:messagebox.showerror('Camera settings',str(exc),parent=win)
        ttk.Button(panel,text='Apply to scene',command=apply).pack(fill='x',pady=12)

    def make_racer(self):
        """Add a usable OnUpdate -> DriveVehicle graph to the selected object."""
        i=self.selected_index()
        if i is None:messagebox.showwarning('Select vehicle','Select a vehicle mesh first.',parent=self);return
        graph=self.doc.setdefault('scripts',{'nodes':[],'links':[],'data_links':[]})
        ids={str(n['id']) for n in graph.get('nodes',[])};n=0
        while f'racer_event_{n}' in ids or f'racer_drive_{n}' in ids:n+=1
        from node_scripts import default_node
        event=default_node('OnUpdate',f'racer_event_{n}',45,300)
        drive=default_node('DriveVehicle',f'racer_drive_{n}',310,300)
        drive['params']['object']=str(i)
        self.doc['objects'][i]['face_movement']=False
        graph.setdefault('nodes',[]).extend([event,drive])
        graph.setdefault('links',[]).append({'from':event['id'],'to':drive['id'],'port':'next'})
        orbit=self.doc.setdefault('camera',{}).setdefault('orbit',{})
        orbit.update(enabled=True,target=i,auto_move=False,sync_yaw=True,
                     distance=7,height=1.5,pitch=-10,turn_speed=2,move_speed=.08)
        self._dirty=True;self.stat.set('Racing nodes and following camera added. D-pad drives and steers.')
        messagebox.showinfo('Racing preset','Vehicle control nodes created! D-pad accelerates, brakes, and steers.\nCamera follows vehicle heading. Edit the DriveVehicle node for acceleration and drag.',parent=self)

    def edit_hud(self):
        from ui_editor import HUDEditor
        HUDEditor(self)

    def edit_settings(self):
        from ui_editor import ProjectSettings
        ProjectSettings(self)

    def set_follow(self):
        i=self.selected_index()
        if i is not None:
            self.doc.setdefault('camera',{})['follow']=i
            self.doc['camera'].setdefault('follow_offset',[0,2,-7])
            self._dirty=True;self.stat.set('Camera will follow '+self.doc['objects'][i]['name']+' on export')

    def clear_follow(self):
        self.doc.get('camera',{}).pop('follow',None)
        self._dirty=True;self.stat.set('Camera follow disabled')

    def play(self):
        if self.sim is not None:return
        try:
            from game_preview import PreviewGame
            self.sim=PreviewGame(self.doc,self._scene_base())
        except Exception as e:
            messagebox.showerror('Cannot preview',str(e),parent=self);return
        self.play_keys.clear();self._played_event_count=0;self.canvas.focus_set()
        self.stat.set('PLAY • arrows = D-pad • Z/A = GBA A • X = B • Q/E = L/R • Stop restores editor scene')
        self._play_tick()

    def _play_tick(self):
        if self.sim is None:return
        try:
            self.sim.tick(self.play_keys)
            # Optional Windows-only asynchronous WAV preview. The GBA ROM uses
            # Direct Sound DMA; on Linux we only record the sound event.
            for _,sound in self.sim.sound_events[getattr(self,'_played_event_count',0):]:
                try:
                    import winsound
                    if sound=='<stop>':winsound.PlaySound(None,winsound.SND_PURGE)
                    else:
                        asset=next((s for s in self.doc.get('sounds',[]) if s['name']==sound),None)
                        if asset:
                            winsound.PlaySound(str(resolve(self._scene_base(),asset['file'])),
                                     winsound.SND_FILENAME|winsound.SND_ASYNC|winsound.SND_NODEFAULT)
                except (ImportError,OSError,RuntimeError):pass
            self._played_event_count=len(self.sim.sound_events)
            if getattr(self.sim,'requested_scene',None) is not None:
                # Switching scenes only affects the temporary play copy.
                target=self.sim.requested_scene
                if not 0<=target<len(self.doc['scenes']):raise ValueError('Invalid scene target')
                self.sim=PreviewGame(self.doc,self._scene_base(),scene_index=target,
                                     shared_variables=self.sim.variables)
                self._played_event_count=0
            self.draw_scene()
        except Exception as e:
            self.stop();messagebox.showerror('Play preview failed',str(e),parent=self);return
        self._play_after=self.after(33,self._play_tick)

    def stop(self):
        if getattr(self,'_play_after',None) is not None:
            self.after_cancel(self._play_after);self._play_after=None
        if getattr(self,'sim',None) is not None:
            try:
                import winsound
                winsound.PlaySound(None,winsound.SND_PURGE)
            except (ImportError,OSError,RuntimeError):pass
            self.sim=None;self.play_keys.clear()
            self.stat.set('Stopped • play-test edits were discarded; project unchanged')
            self.draw_scene()

    def _gba_key(self,keysym):
        return {'Up':'UP','Down':'DOWN','Left':'LEFT','Right':'RIGHT',
                'z':'A','a':'A','x':'B','b':'B','q':'L','e':'R',
                'Return':'START','Shift_L':'SELECT','Shift_R':'SELECT'}.get(keysym)

    def _on_keypress(self,e):
        if self.sim is not None:
            k=self._gba_key(e.keysym)
            if k:self.play_keys.add(k)

    def _on_keyrelease(self,e):
        if self.sim is not None:
            k=self._gba_key(e.keysym)
            if k:self.play_keys.discard(k)

    def edit_animations(self):
        from assets_editor import AnimationEditor
        AnimationEditor(self)

    def edit_sounds(self):
        from assets_editor import SoundEditor
        SoundEditor(self)

    def edit_scripts(self):
        from node_editor import NodeEditor
        NodeEditor(self)

    def drag_start(self,e):
        self.canvas.focus_set()
        if self.sim is not None:return
        # Shift-drag the selected object to translate in the editing view plane.
        if (e.state & 0x0001) and self.selected_index() is not None and getattr(self,'_gizmo_screen',None):
            gx,gy=self._gizmo_screen
            if abs(e.x-gx)<45 and abs(e.y-gy)<45:
                self._gizmo_drag=(e.x,e.y,self.selected_index());return
        self.drag=(e.x,e.y)
    def drag_camera(self,e):
        if self.sim is not None:return
        if self._gizmo_drag is not None:
            x,y,i=self._gizmo_drag
            obj=self.doc['objects'][i]
            z=max(1.,obj['position'][2]-self.doc['camera']['position'][2])
            # Approximate horizontal/vertical screen-space move, scaled by depth.
            obj['position'][0]+=(e.x-x)*z/500
            obj['position'][1]-=(e.y-y)*z/500
            self._gizmo_drag=(e.x,e.y,i)
            self._dirty=True;self.on_tree_select();self.stat.set('Object translated • Save to keep')
            return
        if self.drag is None:return
        dx,dy=e.x-self.drag[0],e.y-self.drag[1];self.drag=(e.x,e.y)
        rot=self.doc['camera']['rotation'];rot[0]=(rot[0]+dx*0.36)%360
        rot[1]=max(-75,min(75,rot[1]-dy*0.36))
        self._dirty=True
        self.draw_scene()
    def zoom_step(self,d):
        self.doc['camera']['position'][2]+=0.6*d;self._dirty=True;self.draw_scene()
    def zoom(self,e):self.zoom_step(1 if e.delta>0 else -1)
    def move_key(self,e):
        if self.sim is not None:return
        if e.keysym.lower() in ('w','s','a','d','q','e'):
            p=self.doc['camera']['position'];k=e.keysym.lower()
            if k=='w':p[2]+=0.3
            if k=='s':p[2]-=0.3
            if k=='a':p[0]-=0.3
            if k=='d':p[0]+=0.3
            if k=='q':p[1]+=0.3
            if k=='e':p[1]-=0.3
            self._dirty=True;self.draw_scene()

    def color_for(self,mesh,matidx,obj):
        material=mesh['mtl'].get(mesh['materials'][matidx],{})
        rgb=material.get('diffuse',(.75,.85,.92))
        tex=obj.get('texture') or material.get('texture')
        if tex:
            path=resolve(self._scene_base(),tex) if obj.get('texture') else Path(tex)
            try:
                from PIL import Image
                color=Image.open(path).convert('RGB').resize((1,1)).getpixel((0,0))
                return color
            except Exception:pass
        return tuple(round(255*c) for c in rgb)

    def draw_scene(self):
        if not hasattr(self,'canvas'):return
        source_doc=self.sim.doc if getattr(self,'sim',None) is not None else self.doc
        self._gizmo_screen=None
        if self.preview_gba.get():
            try:
                from PIL import Image, ImageTk
                from gba_preview import render_scene
                img,tris=render_scene(source_doc,self._scene_base(),self.cache,self.texcache,self.preview_tex.get())
                c=self.canvas;c.delete('all')
                w=max(c.winfo_width(),10);h=max(c.winfo_height(),10)
                c.create_rectangle(0,0,w,h,fill='#0e1a27',outline='')
                scale=max(1,min(5,int(min(w/240,h/160))))
                img=img.resize((240*scale,160*scale),Image.Resampling.NEAREST)
                self._preview_photo=ImageTk.PhotoImage(img,master=self)
                c.create_image(w//2,h//2,image=self._preview_photo,anchor='center')
                c.create_rectangle((w-img.width)//2-1,(h-img.height)//2-1,
                    (w+img.width)//2+1,(h+img.height)//2+1,outline='#678092')
                c.create_text(12,12,anchor='nw',fill='#e6eefa',font=('Segoe UI',10,'bold'),
                    text=f'{"PLAY" if self.sim is not None else "EDIT"} • GBA 240×160 • 120×80 internal • {tris} triangles')
                c.create_text(w-11,h-10,anchor='se',fill='#afc4cf',font=('Segoe UI',9),
                    text='PC approximation • original renderer runs on GBA')
                # Selection translation handles are purely in the editor, not the ROM.
                index=self.selected_index()
                if self.sim is None and index is not None:
                    x,y,z=view_transform(self.doc['objects'][index]['position'],source_doc['camera'])
                    if z>1:
                        gx=(w-img.width)/2 + (60+90*x/z)*2*scale
                        gy=(h-img.height)/2 + (40-90*y/z)*2*scale
                        if 0<gx<w and 0<gy<h:
                            self._gizmo_screen=(gx,gy)
                            c.create_line(gx-24,gy,gx+24,gy,fill='#ff6e78',width=2,arrow='last')
                            c.create_line(gx,gy+24,gx,gy-24,fill='#75d8ff',width=2,arrow='last')
                            c.create_oval(gx-4,gy-4,gx+4,gy+4,fill='white',outline='#182935')
                            c.create_text(gx+12,gy+30,text='Shift+drag',anchor='nw',
                                          fill='#e3eefa',font=('Segoe UI',9))
                return
            except (ImportError,ValueError,OSError,IndexError,ZeroDivisionError) as exc:
                self.stat.set('GBA preview unavailable ('+str(exc)+'); falling back to flat preview')
        c=self.canvas;c.delete('all')
        w=max(c.winfo_width(),10);h=max(c.winfo_height(),10)
        c.create_rectangle(0,0,w,h//2,fill='#1a344e',outline='')
        c.create_rectangle(0,h//2,w,h,fill='#183239',outline='')
        cam=source_doc.get('camera',{'position':[0,0,0],'rotation':[0,0]})
        def project(p):
            x,y,z=view_transform(p,cam)
            if z<=0.25:return None
            k=min(w,h)*0.75/z
            return (w/2+x*k,h/2-y*k,z)
        # Editor reference grid; deliberately outside GBA export.
        for z in range(2,30,2):
            a=project((-12,-2.3,z));b=project((12,-2.3,z))
            if a and b:c.create_line(a[0],a[1],b[0],b[1],fill='#294954')
        for x in range(-10,11,2):
            a=project((x,-2.3,2));b=project((x,-2.3,28))
            if a and b:c.create_line(a[0],a[1],b[0],b[1],fill='#294954')
        polys=[];tris=0
        for i,obj in enumerate(source_doc.get('objects',[])):
            if not obj.get('mesh'):continue
            path=resolve(self._scene_base(),obj['mesh'])
            try:
                if path not in self.cache:self.cache[path]=parse_obj(path)
                mesh=self.cache[path]
            except Exception as e:
                self.stat.set('Preview load error: '+str(e));continue
            positions=[project(transform(v,obj)) for v in mesh['vertices']]
            colors={}
            for corners,mi in mesh['faces']:
                vs=[positions[idx] for idx,uv in corners]
                if any(p is None for p in vs):continue
                if mi not in colors:colors[mi]=self.color_for(mesh,mi,obj)
                pts=[value for v in vs for value in v[:2]]
                depth=sum(v[2] for v in vs)/3
                ax,ay=vs[1][0]-vs[0][0],vs[1][1]-vs[0][1]
                bx,by=vs[2][0]-vs[0][0],vs[2][1]-vs[0][1]
                shade=0.65 if ax*by-bx*ay<0 else 0.9
                col=tuple(min(255,max(0,int(ch*shade))) for ch in colors[mi])
                polys.append((depth,pts,'#%02x%02x%02x'%col,i))
                tris+=1
        polys.sort(key=lambda v:v[0],reverse=True)
        selected=self.selected_index()
        for _,pts,fill,i in polys:
            line=ACCENT if selected==i else '#293d4b'
            width=2 if selected==i else 1
            if self.preview_wire.get():fill=''
            c.create_polygon(*pts,fill=fill,outline=line,width=width)
        c.create_text(18,17,anchor='nw',fill='#cce9eb',font=('Segoe UI',12,'bold'),
                      text='SG3D  •  SCENE VIEW')
        c.create_text(18,42,anchor='nw',fill='#a6cbd3',font=('Segoe UI',10),
                      text=f'{len(source_doc.get("objects",[]))} objects  •  {tris} visible preview triangles')
        c.create_text(w-14,h-12,anchor='se',fill='#9ab4c1',font=('Segoe UI',9),
                      text='Preview only — GBA: 120×80 / RGB332 / ARM assembly')

if __name__=='__main__':Studio().mainloop()
