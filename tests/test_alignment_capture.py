import re,struct,unittest
from pathlib import Path
from lupa.luajit21 import LuaRuntime
from build_overlay import source_bytes

class AlignmentCaptureTests(unittest.TestCase):
    def test_real_native_outpost_centers_match_projection(self):
        report=(Path(__file__).parent/'fixtures/alignment-1.1.6-capture.txt').read_text(encoding='utf-8')
        view={k.encode():float(v) for k,v in re.findall(r'view_(\w+)=([^\n]+)',report)}
        view[b'icon_scale']=2
        lua=LuaRuntime(encoding=None);lua.globals()[b'HD2OverlayTest']=True
        core=lua.execute(source_bytes())
        f=lambda b,o:struct.unpack_from('<f',b,o)[0]
        points=[]
        for _,h in re.findall(r'record=(\d+) position_hex=(\w+)',report):
            b=bytes.fromhex(h)
            if b[0x2ab] and b[0x2a0]:
                points.append(lua.table_from({b'x':f(b,0),b'y':f(b,4),b'kind':b'outpost'}))
        projected=core[b'map_project'](lua.table_from(points),lua.table_from(view))
        native=[]
        for _,h in re.findall(r'native_outpost_widget=(\d+) hex=(\w+)',report):
            b=bytes.fromhex(h)
            if f(b,0x24)<=1:continue
            x=f(b,0x94)+f(b,0x24)*f(b,0x64)/2+f(b,0x28)*f(b,0x84)/2
            y=f(b,0x9c)+f(b,0x24)*f(b,0x6c)/2+f(b,0x28)*f(b,0x8c)/2
            native.append((x,y))
        self.assertEqual(len(native),6);self.assertEqual(len(projected),6)
        for x,y in native:
            delta=min(max(abs(p[b'x']-x),abs(p[b'y']-y)) for p in projected.values())
            self.assertLess(delta,.001)

if __name__=='__main__':unittest.main()
