"""SG3D GUI layout regression test. Run on a desktop with Python + Pillow installed.

On headless Linux, use: xvfb-run -a python tests_gui_layout.py
"""
import unittest
from editor.visual_editor import Studio

class LayoutTests(unittest.TestCase):
    def test_viewport_never_disappears_during_resize(self):
        app=Studio()
        try:
            for width,height in ((1230,780),(1551,899),(940,560)):
                app.geometry(f'{width}x{height}')
                app.update()
                self.assertGreaterEqual(app.canvas.winfo_width(),240)
                self.assertGreaterEqual(app.tree.winfo_width(),175)
                self.assertGreaterEqual(app.inspector_scroll.winfo_width(),250)
                self.assertGreater(len(app.canvas.find_all()),0)
        finally:
            app.destroy()

if __name__=='__main__':unittest.main(verbosity=2)
