"""Scene HUD authoring plus global Game Pak metadata settings."""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import os

TYPES=('text','bar','rect','sprite','dialogue')
FIELDS=('name','type','x','y','w','h','text','fg','bg','value','maximum','file')
DEFAULT={'name':'HUD text','type':'text','x':3,'y':3,'w':60,'h':9,'text':'HELLO GBA!','fg':255,'bg':0,
         'value':0,'maximum':0,'file':'','visible':True}

class HUDEditor(tk.Toplevel):
    def __init__(self,owner):
        super().__init__(owner)
        self.owner=owner;self.doc=owner.doc
        self.title('SG3D HUD Editor — native 240 x 160 text & images')
        self.geometry(f'735x530+{owner.winfo_rootx()+130}+{owner.winfo_rooty()+75}');self.minsize(650,440)
        self.selected=None;self.vars={};self.visible=tk.BooleanVar(value=True)
        pane=ttk.Frame(self,padding=12);pane.pack(fill='both',expand=True)
        left=ttk.Frame(pane);left.pack(side='left',fill='y',padx=(0,12))
        ttk.Label(left,text='HUD ELEMENTS  (draw order)').pack(anchor='w')
        self.items=tk.Listbox(left,width=24,height=18,exportselection=False,
                              bg="#243344",fg="#e2eef7",selectbackground="#288c89",
                              selectforeground="white",highlightthickness=0,borderwidth=1)
        self.items.pack(fill='both',expand=True,pady=7)
        self.items.bind('<<ListboxSelect>>',self.select)
        ttk.Button(left,text='+ Add element',command=self.add).pack(fill='x',pady=2)
        ttk.Button(left,text='Delete selected',command=self.delete).pack(fill='x',pady=2)
        ttk.Button(left,text='▲ Move up',command=lambda:self.shift(-1)).pack(fill='x',pady=2)
        ttk.Button(left,text='▼ Move down',command=lambda:self.shift(1)).pack(fill='x',pady=2)
        right=ttk.Frame(pane);right.pack(side='left',fill='both',expand=True)
        ttk.Label(right,text='ELEMENT PROPERTIES — logical positions 120 x 80').pack(anchor='w',pady=(0,6))
        fields=ttk.Frame(right);fields.pack(fill='x')
        for n,key in enumerate(FIELDS):
            r=n//2;c=n%2
            frame=ttk.Frame(fields);frame.grid(row=r,column=c,sticky='ew',padx=4,pady=4)
            fields.columnconfigure(c,weight=1)
            ttk.Label(frame,text=key.upper()).pack(anchor='w')
            val=tk.StringVar();self.vars[key]=val
            if key=='type':
                entry=ttk.Combobox(frame,textvariable=val,values=TYPES,state='readonly')
                entry.bind('<<ComboboxSelected>>',lambda e:self.apply())
            else:entry=ttk.Entry(frame,textvariable=val)
            entry.pack(fill='x');entry.bind('<Return>',lambda e:self.apply())
        ttk.Checkbutton(right,text='Visible at start',variable=self.visible,command=self.apply).pack(anchor='w',pady=4)
        ttk.Button(right,text='Browse sprite PNG...',command=self.browse).pack(fill='x',pady=3)
        ttk.Button(right,text='Apply HUD element',command=self.apply).pack(fill='x',pady=8)
        ttk.Label(right,text='Color indices use RGB332 (0 transparent for sprites).\n'
                  'Coordinates use the existing 120x80 layout; text and\n'
                  'PNG images render at native 240x160 via hardware sprites.\n'
                  'Text is max 27 ASCII characters per element.\n'
                  'characters, dialogue max one line for now.\n'
                  'Set maximum > 0 on text to append numeric value.\n'
                  'UI scripting indices follow the left-hand list.',wraplength=390).pack(anchor='w')
        self.refresh(0 if self.doc.setdefault("hud",[]) else None)
    def refresh(self,sel=None):
        self.items.delete(0,tk.END)
        for i,e in enumerate(self.doc.setdefault('hud',[])):
            self.items.insert(tk.END,f'{i}  {e.get("name","Item")} [{e.get("type","text")}]')
        if sel is not None and 0<=sel<len(self.doc['hud']):
            self.items.selection_set(sel);self.items.activate(sel);self.selected=sel;self.fill(self.doc['hud'][sel])
    def fill(self,item):
        for key in FIELDS:self.vars[key].set(str(item.get(key,DEFAULT[key])))
        self.visible.set(bool(item.get('visible',True)))
    def select(self,event=None):
        values=self.items.curselection()
        if not values:return
        self.selected=values[0];self.fill(self.doc['hud'][self.selected])
    def add(self):
        if len(self.doc.setdefault('hud',[]))>=16:
            messagebox.showerror('HUD limit','Maximum 16 HUD elements',parent=self);return
        item=dict(DEFAULT);item['name']=f'Item {len(self.doc["hud"])+1}'
        self.doc['hud'].append(item);self.owner._dirty=True;self.refresh(len(self.doc['hud'])-1);self.owner.draw_scene()
    def delete(self):
        if self.selected is None:return
        del self.doc['hud'][self.selected];self.owner._dirty=True
        self.selected=None;self.refresh();self.owner.draw_scene()
    def shift(self,offset):
        i=self.selected
        if i is None or not 0<=i+offset<len(self.doc['hud']):return
        arr=self.doc['hud'];arr[i],arr[i+offset]=arr[i+offset],arr[i]
        self.owner._dirty=True;self.refresh(i+offset);self.owner.draw_scene()
    def browse(self):
        path=filedialog.askopenfilename(parent=self,filetypes=[('PNG image','*.png')])
        if path:self.vars['file'].set(os.path.relpath(path,self.owner._scene_base()));self.apply()
    def apply(self):
        if self.selected is None:return
        try:
            data={key:self.vars[key].get() for key in FIELDS}
            for key in ('x','y','w','h','fg','bg','value','maximum'):data[key]=int(data[key])
            if data['type'] not in TYPES:raise ValueError('Invalid type')
            if not 1<=data['w']<=120 or not 1<=data['h']<=80:raise ValueError('Invalid dimensions')
            if not -120<=data['x']<=120 or not -80<=data['y']<=80:raise ValueError('Invalid position')
            if not 0<=data['fg']<=255 or not 0<=data['bg']<=255:raise ValueError('RGB332 color range is 0..255')
            if not -32768<=data['value']<=32767 or not 0<=data['maximum']<=32767:raise ValueError('Value out of range')
            data['visible']=self.visible.get()
            self.doc['hud'][self.selected]=data;self.owner._dirty=True
            self.refresh(self.selected);self.owner.draw_scene()
        except ValueError as e:messagebox.showerror('Invalid HUD element',str(e),parent=self)

class ProjectSettings(tk.Toplevel):
    def __init__(self,owner):
        super().__init__(owner)
        self.owner=owner;self.title('SG3D Project Settings');self.geometry(f'440x330+{owner.winfo_rootx()+240}+{owner.winfo_rooty()+130}')
        data=owner.doc.setdefault('settings',{})
        self.inputs={}
        root=ttk.Frame(self,padding=15);root.pack(fill='both',expand=True)
        for key,label,default in (('title','Game Pak title (12 ASCII chars)','SG3D GAME'),
                                  ('code','Game code (4 chars)','SG12'),
                                  ('maker','Maker code (2 chars)','00')):
            ttk.Label(root,text=label).pack(anchor='w',pady=(8,2))
            var=tk.StringVar(value=str(data.get(key,default)));self.inputs[key]=var
            ttk.Entry(root,textvariable=var).pack(fill='x')
        self.profiler=tk.BooleanVar(value=bool(data.get('profiler',False)))
        ttk.Checkbutton(root,text='Show F/T/O performance overlay on GBA',variable=self.profiler).pack(anchor='w',pady=12)
        ttk.Label(root,text='GBA game code/title are embedded into the exported ROM header.').pack(anchor='w')
        ttk.Button(root,text='Save project settings',command=self.apply).pack(fill='x',pady=8)
    def apply(self):
        try:
            title=self.inputs['title'].get().strip();code=self.inputs['code'].get().strip().upper();maker=self.inputs['maker'].get().strip().upper()
            if not title or len(title)>12 or not title.isascii():raise ValueError('Title must be 1–12 ASCII chars')
            if len(code)!=4 or not code.isalnum() or not code.isascii():raise ValueError('Code must have exactly 4 ASCII letters/numbers')
            if len(maker)!=2 or not maker.isalnum() or not maker.isascii():raise ValueError('Maker must be 2 ASCII letters/numbers')
            self.owner.doc['settings']={'title':title,'code':code,'maker':maker,'profiler':bool(self.profiler.get())}
            self.owner._dirty=True;self.destroy()
        except ValueError as e:messagebox.showerror('Bad ROM settings',str(e),parent=self)
