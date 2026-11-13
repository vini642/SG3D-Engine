"""RC2 orbit hotfix: prove camera-relative directions and legacy node ownership."""
import copy
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'editor')]
from orbit_controller import orbit_script_controls
from game_preview import PreviewGame
from project_export import export_project

SAMPLE=ROOT/'examples/orbit_sky_demo.sg3d.json'

def make_legacy(doc):
    nodes=[];links=[]
    for key, x, z in [('LEFT',-0.11,0),('RIGHT',0.11,0),('UP',0,0.11),('DOWN',0,-0.11)]:
        ev='press_'+key.lower();act='move_'+key.lower()
        nodes.extend([{'id':ev,'type':'OnKeyHeld','params':{'key':key}},
                      {'id':act,'type':'MovePlayer','params':{'object':'0','x':str(x),'z':str(z)}}])
        links.append({'from':ev,'to':act,'port':'next'})
    doc['scripts']={'nodes':nodes,'links':links,'data_links':[]}
    return doc

class OrbitHotfixTests(unittest.TestCase):
    def load(self):return json.loads(SAMPLE.read_text())

    def test_no_legacy_script_auto_move(self):
        d=self.load()
        self.assertEqual(set(),orbit_script_controls(d))
        sim=PreviewGame(d,SAMPLE.parent)
        sim.tick(['UP'])
        self.assertAlmostEqual(sim.doc['objects'][0]['position'][2]-8,.11,delta=.01)

    def test_legacy_not_doubled_at_yaw_zero(self):
        d=make_legacy(self.load())
        self.assertEqual(4,len(orbit_script_controls(d)))
        sim=PreviewGame(d,SAMPLE.parent)
        before=sim.doc['objects'][0]['position'][:]
        sim.tick(['UP'])
        after=sim.doc['objects'][0]['position']
        self.assertAlmostEqual(after[2]-before[2],.11,delta=.015)
        self.assertAlmostEqual(after[0]-before[0],0,delta=.015)

    def test_up_follows_rotated_camera_both_modes(self):
        for legacy in (False, True):
            with self.subTest(legacy=legacy):
                d=self.load()
                if legacy:make_legacy(d)
                # yaw at 90deg, so forward is +X, even though the original
                # world-coordinate MovePlayer requested positive Z.
                d['camera']['rotation'][0]=90
                sim=PreviewGame(d,SAMPLE.parent)
                before=sim.doc['objects'][0]['position'][:]
                sim.tick(['UP'])
                after=sim.doc['objects'][0]['position']
                self.assertGreater(after[0]-before[0],.08)
                self.assertAlmostEqual(after[2]-before[2],0,delta=.015)
                # Camera placed behind player and looking in travel direction.
                cam=sim.doc['camera']['position']
                self.assertGreater(after[0]-cam[0],0)

    def test_preview_turn_speed_matches_exported_angle_units(self):
        d=self.load()
        d['camera']['orbit']['turn_speed']=2 # user-facing degrees/frame
        sim=PreviewGame(d,SAMPLE.parent)
        sim.tick(['R'])
        # GBA exporter rounds 2*256/360 to 1 unit = 360/256 degrees.
        self.assertAlmostEqual(sim.doc['camera']['rotation'][0],360/256,delta=1e-6)

    def test_one_frame_turn_applies_before_script(self):
        d=make_legacy(self.load())
        # Set the camera turn speed to 64 angle units per frame (=90 deg).
        d['camera']['orbit']['turn_speed']=90
        sim=PreviewGame(d,SAMPLE.parent)
        before=sim.doc['objects'][0]['position'][:]
        sim.tick(['UP','R'])
        after=sim.doc['objects'][0]['position']
        self.assertGreater(after[0]-before[0],.08)
        self.assertAlmostEqual(after[2]-before[2],0,delta=.02)

    def test_legacy_gba_export_uses_one_relative_controller(self):
        d=make_legacy(self.load())
        for obj in d['objects']:obj['mesh']=str((SAMPLE.parent/obj['mesh']).resolve())
        if d.get('skybox',{}).get('file'):
            d['skybox']['file']=str((SAMPLE.parent/d['skybox']['file']).resolve())
        with tempfile.TemporaryDirectory() as tmp:
            project=Path(tmp)/'legacy.sg3d.json';project.write_text(json.dumps(d))
            export_project(project,Path(tmp)/'out')
            src=(Path(tmp)/'out'/'main.c').read_text()
            self.assertIn('sg3d_orbit_input(',src)
            self.assertIn('sg3d_orbit_place(',src)
            self.assertEqual(src.count('sg3d_move_relative('),4)
            self.assertLess(src.index('sg3d_orbit_input('),src.index('sg3d_move_relative('))
            # Explicit auto-input path is excluded in favor of scripted input.
            self.assertNotIn('input_x',src)

    def test_original_world_move_preserved_when_orbit_off(self):
        d=make_legacy(self.load());d['camera']['orbit']['enabled']=False
        self.assertFalse(orbit_script_controls(d))
        sim=PreviewGame(d,SAMPLE.parent)
        sim.doc['camera']['rotation'][0]=90
        before=sim.doc['objects'][0]['position'][:]
        sim.tick(['UP'])
        after=sim.doc['objects'][0]['position']
        self.assertAlmostEqual(after[0]-before[0],0,delta=.01)
        self.assertGreater(after[2]-before[2],.08)

    def test_sine_table_cardinal_math_actual_C(self):
        """Compile real orbit math on host, check all four cardinal directions."""
        code=r'''
#include <stdint.h>
#include "sg3d_controls.h"
static int32_t xx,zz;
void sg3d_physics_move(SG3DPhysicsBody *b,unsigned n,unsigned who,int32_t dx,int32_t dy,int32_t dz){
 (void)b;(void)n;(void)who;(void)dy;xx=dx;zz=dz;
}
int main(void){
 SG3DTransform tr={0};SG3DPhysicsBody bd={&tr,0};
 int target_x[]={0,256,0,-256};int target_z[]={256,0,-256,0};
 for(int i=0;i<4;i++){
   uint8_t yaw=(uint8_t)(i*64);
   sg3d_move_relative(&bd,1,0,yaw,0,256);
   if(xx!=target_x[i]||zz!=target_z[i])return 10+i;
   SG3DCamera c={0};sg3d_orbit_place(&c,&tr,yaw,0,7*256,0);
   if(c.yaw!=yaw) return 20+i;
   // Forward from camera to target aligns with the input displacement.
   if((tr.x-c.x)*xx+(tr.z-c.z)*zz<=0)return 30+i;
 }
 // Rotate by one quarter turn and apply input on SAME frame.
 uint8_t yaw=0;int8_t pitch=0;sg3d_orbit_input(256,&yaw,&pitch,64);
 if(yaw!=64)return 99;
 sg3d_move_relative(&bd,1,0,yaw,0,256);
 if(xx!=256||zz!=0)return 98;
 return 0;
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            c=Path(tmp)/'harness.c';exe=Path(tmp)/'check';c.write_text(code)
            cmd=['gcc','-std=c11','-O2','-I',str(ROOT/'engine'),str(c),str(ROOT/'engine/sg3d_controls.c'),'-o',str(exe)]
            subprocess.run(cmd,check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            subprocess.run([str(exe)],check=True)

if __name__=='__main__':unittest.main()
