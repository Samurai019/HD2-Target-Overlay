import struct,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))
import test_overlay

class StalkerLairTests(unittest.TestCase):
    def setUp(self):
        self.fixture=test_overlay.OverlayTests();self.fixture.setUp()
        self.lua=self.fixture.lua;self.core=self.fixture.core

    def classify(self,resource=bytes.fromhex('a9f3b1f33e691db5'),handle=0x40000,race=False):
        head=bytearray(112)
        struct.pack_into('<I',head,36,1)
        struct.pack_into('<Q',head,80,0x30000)
        struct.pack_into('<Q',head,96,0x50000)
        memory={0x3326da0:struct.pack('<Q',0x20000),0x20000:bytes(head),
                0x30000:struct.pack('<Q',handle),0x40000:resource,
                0x50000+0x1038:struct.pack('<I',3)}
        calls={}
        def read(a,n):
            calls[a]=calls.get(a,0)+1
            if race and a==0x20000 and calls[a]>1:return bytes(112)
            return memory.get(a)
        rows=self.lua.execute(b"return {{kind='objective',index=0,importance=3,x=120,y=230,completed=false,discovered=false}}")
        reader=self.lua.eval(b'function(f)return function(...)return f(...)end end')(read)
        return self.core[b'classify_objectives'](reader,0,rows)

    def filtered(self,rows,posts=None,options=None):
        return self.core[b'filter'](rows,self.lua.table(),posts or self.lua.table(),options)

    def test_exact_resource_identity_and_empty_handle_fallback(self):
        for resource,handle,expected in [(bytes.fromhex('a9f3b1f33e691db5'),0x40000,True),
                                          (bytes.fromhex('a8f3b1f33e691db5'),0x40000,False),
                                          (b'otherone',0x40000,False),
                                          (None,0x40000,False),(b'otherone',0,False)]:
            rows=self.classify(resource,handle)
            self.assertEqual(rows[1][b'stalker_lair'],expected)
            self.assertEqual(rows[1][b'importance'],3)
            self.assertEqual(len(self.filtered(rows)),1)
            self.assertEqual(self.filtered(rows)[1][b'kind'],b'stalker_lair' if expected else b'objective')

    def test_discovery_keeps_red_completion_removes_red(self):
        rows=self.classify()
        markers=self.filtered(rows)
        self.assertEqual([r[b'kind'] for r in markers.values()],[b'stalker_lair'])
        self.assertEqual((markers[1][b'x'],markers[1][b'y']),(120,230))
        rows[1][b'discovered']=True
        self.assertEqual(self.filtered(rows)[1][b'kind'],b'stalker_lair')
        rows[1][b'completed']=True
        self.assertEqual(len(self.filtered(rows)),0)
        rows[1][b'discovered']=False
        self.assertEqual(len(self.filtered(rows)),0)

    def test_star_is_hollow_with_separate_tips_and_concave_gaps(self):
        parts=self.core[b'glyph'](b'stalker_lair',28,2,0.25)
        rects=[tuple(parts[i][j] for j in range(1,5)) for i in range(1,len(parts)+1)]
        def painted(px,py):
            return any(x<=px<x+w and y<=py<y+h for x,y,w,h in rects)
        self.assertFalse(painted(0,0))
        self.assertFalse(painted(4,9.5))  # Gap between upper and diagonal tips.
        for x,y in [(0,13.5),(0,-13.5),(13.5,0),(-13.5,0),
                    (9.5,9.5),(-9.5,9.5),(9.5,-9.5),(-9.5,-9.5)]:
            self.assertTrue(painted(x,y),(x,y))
        for x,y,w,h in rects:
            self.assertGreater(w,0)
            self.assertGreaterEqual(x,-14.001)
            self.assertLessEqual(x+w,14.001)
            self.assertGreaterEqual(y,-14.001)
            self.assertLessEqual(y+h,14.001)
        color=self.core[b'marker_color'](self.lua.table_from({b'kind':b'stalker_lair'}))
        self.assertEqual(list(color.values()),[255,255,45,55])

    def test_toggles_independent_and_wild_holes_still_filtered(self):
        rows=self.classify()
        posts=self.lua.execute(b"return {{kind='outpost',x=121,y=231,counts_as_outpost=false}}")
        for outposts,objectives,expected in [(True,False,[b'stalker_lair']),
                                            (False,True,[b'objective']),(False,False,[])]:
            opts=self.lua.table_from({b'outposts':outposts,b'objectives':objectives,b'credits':False})
            result=self.filtered(rows,posts,opts)
            self.assertEqual([r[b'kind'] for r in result.values()],expected)
        rows[1][b'stalker_lair']=False
        self.assertEqual(len(self.filtered(rows,posts)),1)

    def test_changed_objective_scene_is_rejected(self):
        with self.assertRaises(Exception):self.classify(race=True)

if __name__=='__main__':unittest.main()
