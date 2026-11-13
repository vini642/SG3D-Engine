"""Run the native host audio tests if a C compiler is installed."""
import shutil, subprocess, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).parent
class AudioTimerTests(unittest.TestCase):
    def test_hardware_timer_and_irq_registers(self):
        cc=shutil.which('cc') or shutil.which('clang') or shutil.which('gcc')
        if cc is None:self.skipTest('No native C compiler available')
        with tempfile.TemporaryDirectory() as d:
            exe=Path(d)/'audio_test'
            subprocess.run([cc,'-DSG3D_AUDIO_HOST_TEST','-std=c11','-O2',str(ROOT/'tests/audio_host.c'),str(ROOT/'engine/sg3d_audio.c'),'-o',str(exe)],check=True)
            run=subprocess.run([str(exe)],capture_output=True,text=True,check=True)
            self.assertIn('PASS:',run.stdout)
if __name__=='__main__':unittest.main()
