import sys,unittest,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tests'))
from build_overlay import source_bytes
import test_overlay

class HudCalibrationTests(unittest.TestCase):
    def setUp(self):
        self.fixture=test_overlay.OverlayTests();self.fixture.setUp()
        self.lua=self.fixture.lua;self.core=self.fixture.core

    def test_nine_fixed_numbered_points_and_bounded_reference_graphics(self):
        view=self.core[b'map_view'](self.fixture.map_fixture(),0,1920,1080)
        points=self.core[b'calibration_points'](view)
        self.assertEqual(len(points),9)
        self.assertEqual([p[b'id'] for p in points.values()],list(range(1,10)))
        self.assertEqual((points[5][b'x'],points[5][b'y']),(800,500))
        self.assertGreater(points[1][b'y'],points[7][b'y'])
        self.assertLess(points[1][b'x'],points[3][b'x'])
        view[b'hud_curve']=1
        curved=self.core[b'calibration_points'](view)
        for i in range(1,10):
            self.assertEqual((points[i][b'x'],points[i][b'y']),(curved[i][b'x'],curved[i][b'y']))
        rects=self.core[b'calibration_rects'](view)
        self.assertGreater(len(rects),192);self.assertLess(len(rects),600)
        for p in rects.values():
            self.assertGreater(p[b'w'],0);self.assertGreater(p[b'h'],0)
            self.assertTrue(0<=p[b'x']<1920);self.assertTrue(0<=p[b'y']<1080)

    def runtime(self,diagnostic=True):
        lua=self.lua;lua.globals()[b'HD2OverlayTest']=False
        lua.execute(b'update=function()end');lua.execute(source_bytes(diagnostic))
        find=lua.eval(b"""function(fn,wanted)
            local seen={}
            local function visit(f)
                if seen[f] then return end;seen[f]=true
                local children={}
                for i=1,100 do local n,v=debug.getupvalue(f,i);if not n then break end
                    if n==wanted then return v end
                    if type(v)=='function' then children[#children+1]=v end
                end
                for _,child in ipairs(children) do local v=visit(child);if v~=nil then return v end end
            end
            local result=visit(fn);assert(result,'missing '..wanted);return result
        end""")
        setval=lua.eval(b"""function(fn,wanted,value)
            for i=1,100 do local n=debug.getupvalue(fn,i);if not n then break end
                if n==wanted then debug.setupvalue(fn,i,value);return end end
            error('missing '..wanted)
        end""")
        tick=find(lua.globals()[b'update'],b'tick')
        api=lua.execute(b"""local keys={};local stats={created=0,drawn=0,destroyed=0,queried={}}
            return {stats=stats,Keyboard={button=function(k)stats.queried[#stats.queried+1]=k;return keys[k] or false end},
                keys=keys,Application={worlds=function()return {1} end,main_world=function()return 1 end},
                World={create_screen_gui=function()stats.created=stats.created+1;return 1 end,destroy_gui=function()end},
                Gui={resolution=function()return 1920,1080 end,
                    rect=function()stats.drawn=stats.drawn+1;return stats.drawn end,
                    destroy_rect=function()stats.destroyed=stats.destroyed+1 end},
                Vector3=function(...)return {...}end,Vector2=function(...)return {...}end,Color=function(...)return {...}end}
        """)
        setval(tick,b'worker',None);setval(tick,b'sr',api)
        refresh=find(tick,b'refresh');setval(refresh,b'read',self.fixture.map_fixture());setval(refresh,b'base',0)
        state=lua.globals()[b'HD2TargetOverlay'];state[b'key']=7;state[b'capture_key']=8;state[b'calibration_key']=9
        return tick,api,state,refresh,setval

    def test_f9_edge_toggle_render_cache_map_close_and_cleanup(self):
        tick,api,state,refresh,setval=self.runtime()
        api[b'keys'][9]=True;tick()
        self.assertTrue(state[b'calibration'])
        count=api[b'stats'][b'drawn'];self.assertGreater(count,192)
        tick();self.assertTrue(state[b'calibration']);self.assertEqual(api[b'stats'][b'drawn'],count)
        api[b'keys'][9]=False;tick();api[b'keys'][9]=True;tick()
        self.assertFalse(state[b'calibration']);self.assertEqual(api[b'stats'][b'destroyed'],count)
        api[b'keys'][9]=False;tick();api[b'keys'][9]=True;tick()
        self.assertTrue(state[b'calibration'])
        setval(refresh,b'read',self.fixture.map_fixture(opened=False));tick()
        self.assertEqual(len(state[b'ids']),0)
        setval(refresh,b'read',self.fixture.map_fixture());tick()
        self.assertGreater(len(state[b'ids']),192)
        api[b'keys'][7]=True;tick()
        self.assertFalse(state[b'enabled']);self.assertEqual(len(state[b'ids']),0)

    def test_f8_preserves_separate_captures_with_numbered_coordinates(self):
        tick,api,state,_,_=self.runtime()
        api[b'keys'][9]=True
        with tempfile.TemporaryDirectory() as directory:
            self.lua.globals()[b'CowboyBingusModLoader']=self.lua.table_from({b'log_directory':directory.encode()})
            api[b'keys'][8]=True;tick()
            files=list(Path(directory).glob('TargetOverlay_HUD_*.txt'));self.assertEqual(len(files),1)
            report=files[0].read_text()
            self.assertIn('calibration_enabled=true',report)
            self.assertIn('calibration_point=9 flat=',report)
            tick();self.assertEqual(len(list(Path(directory).glob('TargetOverlay_HUD_*.txt'))),1)
            api[b'keys'][8]=False;tick();api[b'keys'][8]=True;tick()
            self.assertEqual(len(list(Path(directory).glob('TargetOverlay_HUD_*.txt'))),2)
            self.assertEqual(files[0].read_text(),report)

    def test_formal_build_ignores_f8_f9_and_writes_no_diagnostic_files(self):
        tick,api,state,_,_=self.runtime(diagnostic=False)
        api[b'keys'][8]=True;api[b'keys'][9]=True
        with tempfile.TemporaryDirectory() as directory:
            self.lua.globals()[b'CowboyBingusModLoader']=self.lua.table_from({b'log_directory':directory.encode()})
            tick();tick()
            self.assertEqual(list(api[b'stats'][b'queried'].values()),[7,7])
            self.assertIsNone(state[b'calibration'])
            self.assertIsNone(state[b'capture_path'])
            self.assertEqual(list(Path(directory).iterdir()),[])

if __name__=='__main__':unittest.main()
