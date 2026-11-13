"""Small Tkinter animation timeline and sound import UI for SG3D v0.11."""
import copy
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
from pathlib import Path
from animation_assets import validated_clips,pose_at
from audio_assets import convert_wav

class AnimationEditor(tk.Toplevel):
    def __init__(self,owner):
        super().__init__(owner)
        self.owner=owner;self.doc=owner.doc
        self.title('SG3D Studio 1.0 — Keyframe animations')
        self.geometry('720x480');self.minsize(600,390)
        self._preview_object=None;self._preview_original=None
        top=ttk.Frame(self,padding=10);top.pack(fill='both',expand=True)
        ttk.Label(top,text='ANIMATIONS • position / rotation / scale',font=('Segoe UI',11,'bold')).pack(anchor='w')
        ttk.Label(top,text='Pose an object in the main Inspector, then Capture pose here. GBA interpolation is baked at export.').pack(anchor='w',pady=6)
        body=ttk.Frame(top);body.pack(fill='both',expand=True)
        left=ttk.Frame(body);left.pack(side='left',fill='both',expand=True,padx=(0,10))
        ttk.Label(left,text='Clips').pack(anchor='w')
        self.clips=tk.Listbox(left,height=9,exportselection=False)
        self.clips.pack(fill='both',expand=True)
        self.clips.bind('<<ListboxSelect>>',lambda e:self.select())
        bar=ttk.Frame(left);bar.pack(fill='x')
        ttk.Button(bar,text='+ Clip',command=self.add_clip).pack(side='left')
        ttk.Button(bar,text='Delete clip',command=self.delete_clip).pack(side='left')
        ttk.Label(left,text='Keyframes (frame number)').pack(anchor='w',pady=(10,2))
        self.keys=tk.Listbox(left,height=8,exportselection=False)
        self.keys.pack(fill='both',expand=True)
        row=ttk.Frame(left);row.pack(fill='x')
        ttk.Button(row,text='Capture pose',command=self.capture).pack(side='left')
        ttk.Button(row,text='Delete key',command=self.delete_key).pack(side='left')
        right=ttk.Frame(body);right.pack(side='left',fill='both',expand=True)
        self.name=tk.StringVar();self.object=tk.StringVar();self.duration=tk.StringVar();self.loop=tk.BooleanVar();self.autoplay=tk.BooleanVar()
        ttk.Label(right,text='Clip name').pack(anchor='w')
        ttk.Entry(right,textvariable=self.name).pack(fill='x')
        ttk.Label(right,text='Target object').pack(anchor='w',pady=(8,2))
        self.object_combo=ttk.Combobox(right,textvariable=self.object,state='readonly')
        self.object_combo.pack(fill='x')
        ttk.Label(right,text='Duration (2..240 frames)').pack(anchor='w',pady=(8,2))
        ttk.Entry(right,textvariable=self.duration).pack(fill='x')
        ttk.Checkbutton(right,text='Loop animation',variable=self.loop).pack(anchor='w',pady=4)
        ttk.Checkbutton(right,text='Autoplay on scene start',variable=self.autoplay).pack(anchor='w')
        ttk.Button(right,text='Apply clip settings',command=self.apply).pack(fill='x',pady=(10,8))
        ttk.Label(right,text='Scrub animation frame').pack(anchor='w')
        self.slider=tk.Scale(right,from_=0,to=59,orient='horizontal',command=self.scrub,showvalue=True)
        self.slider.pack(fill='x')
        ttk.Label(right,text='Scrubbing previews the pose temporarily.\nClosing restores the original editor pose.\n\nNo skeletal skinning yet; only rigid transforms.',wraplength=270,justify='left').pack(anchor='w',pady=7)
        self.protocol('WM_DELETE_WINDOW',self.close)
        self.refresh()

    def clips_data(self):return self.doc.setdefault('animations',[])
    def idx(self):
        selection=self.clips.curselection()
        return selection[0] if selection else None
    def restore(self):
        if self._preview_object is not None and self._preview_original is not None:
            obj=self.doc['objects'][self._preview_object]
            for k,value in self._preview_original.items():obj[k]=value
            self._preview_object=None;self._preview_original=None
            self.owner.on_tree_select()
    def refresh(self,selected=None):
        i=selected if selected is not None else self.idx()
        self.clips.delete(0,tk.END)
        for clip in self.clips_data():self.clips.insert(tk.END,clip['name'])
        if i is None and self.clips_data():i=0
        if i is not None and 0<=i<len(self.clips_data()):self.clips.selection_set(i)
        self.select()
    def select(self):
        self.restore()
        i=self.idx();self.keys.delete(0,tk.END)
        if i is None:return
        c=self.clips_data()[i]
        self.name.set(c['name']);self.duration.set(str(c['duration']))
        values=[f'{j}: {obj.get("name","Object")}' for j,obj in enumerate(self.doc['objects'])]
        self.object_combo.configure(values=values)
        self.object.set(values[int(c['object'])])
        self.loop.set(bool(c.get('loop',True)));self.autoplay.set(bool(c.get('autoplay',False)))
        self.slider.configure(to=int(c['duration'])-1)
        for key in c['keys']:self.keys.insert(tk.END,f'Frame {key["frame"]:3d}  •  {key["position"]}')
    def add_clip(self):
        obj_idx=self.owner.selected_index()
        if obj_idx is None:
            messagebox.showwarning('Select object','Select an object in the scene hierarchy first.',parent=self);return
        obj=self.doc['objects'][obj_idx]
        if (obj.get('physics') or {}).get('dynamic'):
            messagebox.showwarning('Dynamic object','Rigid animations cannot target dynamic physics objects.',parent=self);return
        base={k:copy.deepcopy(obj[k]) for k in ('position','rotation','scale')}
        raised=copy.deepcopy(base);raised['position'][1]+=1.0
        number=len(self.clips_data())+1
        names={c['name'] for c in self.clips_data()}
        name=f'Clip{number}'
        while name in names:number+=1;name=f'Clip{number}'
        self.clips_data().append({'name':name,'object':obj_idx,'duration':60,'loop':True,'autoplay':False,
                                  'keys':[{'frame':0,**base},{'frame':30,**raised},{'frame':59,**copy.deepcopy(base)}]})
        self.owner._dirty=True;self.refresh(len(self.clips_data())-1)
    def apply(self):
        i=self.idx()
        if i is None:return
        clip=self.clips_data()[i]
        try:
            name=self.name.get().strip()
            if not name or any(c['name']==name for j,c in enumerate(self.clips_data()) if i!=j):raise ValueError('Clip name must be nonempty and unique')
            obj=int(self.object.get().split(':')[0]);duration=int(self.duration.get())
            if not 2<=duration<=240:raise ValueError('Duration must be 2..240')
            if any(k['frame']>=duration for k in clip['keys']):raise ValueError('Delete/move keyframes beyond new duration first')
            if (self.doc['objects'][obj].get('physics') or {}).get('dynamic'):raise ValueError('Disable Dynamic on the target object')
            clip.update(name=name,object=obj,duration=duration,loop=self.loop.get(),autoplay=self.autoplay.get())
            validated_clips(self.doc)
        except Exception as e:
            messagebox.showerror('Bad animation',str(e),parent=self);return
        self.owner._dirty=True;self.refresh(i)
    def delete_clip(self):
        i=self.idx()
        if i is None:return
        self.restore();del self.clips_data()[i]
        # Never let an existing node silently target a different clip.
        for n in self.doc.get('scripts',{}).get('nodes',[]):
            if n.get('type') not in ('PlayAnimation','StopAnimation'):continue
            try:old=int(n.get('params',{}).get('animation','0'))
            except (TypeError,ValueError):continue
            if old==i:n['params']['animation']='-1'
            elif old>i:n['params']['animation']=str(old-1)
        self.owner._dirty=True;self.refresh()
    def capture(self):
        i=self.idx()
        if i is None:return
        c=self.clips_data()[i];idx=c['object']
        if self._preview_object is not None:self.restore()
        frame=simpledialog.askinteger('Capture pose','Frame (0..duration-1):',initialvalue=int(self.slider.get()),minvalue=0,maxvalue=c['duration']-1,parent=self)
        if frame is None:return
        obj=self.doc['objects'][idx]
        key={'frame':frame,'position':list(obj['position']),'rotation':list(obj['rotation']),'scale':float(obj.get('scale',1))}
        c['keys']=[k for k in c['keys'] if k['frame']!=frame]+[key]
        c['keys'].sort(key=lambda k:k['frame'])
        self.owner._dirty=True;self.refresh(i)
    def delete_key(self):
        i=self.idx();sel=self.keys.curselection()
        if i is None or not sel:return
        keys=self.clips_data()[i]['keys']
        if len(keys)<=2 or keys[sel[0]]['frame']==0:
            messagebox.showwarning('Required keys','Keep frame 0 and at least two keyframes.',parent=self);return
        del keys[sel[0]];self.owner._dirty=True;self.refresh(i)
    def scrub(self,value):
        i=self.idx()
        if i is None:return
        clip=self.clips_data()[i];obj_idx=clip['object']
        if self._preview_object != obj_idx:
            self.restore();self._preview_object=obj_idx
            self._preview_original={k:copy.deepcopy(self.doc['objects'][obj_idx][k]) for k in ('position','rotation','scale')}
        pose=pose_at(clip,int(float(value)))
        self.doc['objects'][obj_idx].update(pose)
        self.owner.draw_scene()
    def close(self):
        self.restore();self.destroy()

class SoundEditor(tk.Toplevel):
    def __init__(self,owner):
        super().__init__(owner)
        self.owner=owner;self.title('SG3D Studio 1.0 — WAV sound effects');self.geometry('500x330')
        panel=ttk.Frame(self,padding=12);panel.pack(fill='both',expand=True)
        ttk.Label(panel,text='PCM sound effects (one voice, 8192 Hz)',font=('Segoe UI',11,'bold')).pack(anchor='w')
        ttk.Label(panel,text='Import uncompressed 8/16-bit mono or stereo WAV files (up to 2 seconds).').pack(anchor='w',pady=7)
        self.list=tk.Listbox(panel,exportselection=False);self.list.pack(fill='both',expand=True)
        row=ttk.Frame(panel);row.pack(fill='x',pady=8)
        ttk.Button(row,text='＋ Import WAV',command=self.import_wav).pack(side='left')
        ttk.Button(row,text='Remove selected',command=self.remove).pack(side='left')
        ttk.Label(panel,text='Use PlaySound/StopSound nodes. Playing another effect interrupts the previous one.',wraplength=455).pack(anchor='w')
        self.refresh()
    def refresh(self):
        self.list.delete(0,tk.END)
        for s in self.owner.doc.setdefault('sounds',[]):self.list.insert(tk.END,s['name']+' — '+s['file'])
    def import_wav(self):
        path=filedialog.askopenfilename(parent=self,filetypes=[('WAV audio','*.wav')])
        if not path:return
        try:samples=convert_wav(path)
        except Exception as e:messagebox.showerror('Unsupported WAV',str(e),parent=self);return
        name=Path(path).stem;existing={s['name'] for s in self.owner.doc['sounds']}
        base=name;i=2
        while name in existing:name=f'{base}_{i}';i+=1
        from os.path import relpath
        self.owner.doc['sounds'].append({'name':name,'file':relpath(path,self.owner._scene_base())})
        self.owner._dirty=True;self.refresh()
        messagebox.showinfo('Sound imported',f'{name}: {len(samples)} samples at 8192 Hz.\nAdd a PlaySound node to hear it in the ROM.',parent=self)
    def remove(self):
        sel=self.list.curselection()
        if not sel:return
        removed=sel[0];del self.owner.doc['sounds'][removed]
        for scene in self.owner.doc.get('scenes',[self.owner.doc]):
            for n in scene.get('scripts',{}).get('nodes',[]):
                if n.get('type')!='PlaySound':continue
                try:old=int(n.get('params',{}).get('sound','0'))
                except (TypeError,ValueError):continue
                if old==removed:n['params']['sound']='-1'
                elif old>removed:n['params']['sound']=str(old-1)
        self.owner._dirty=True;self.refresh()
