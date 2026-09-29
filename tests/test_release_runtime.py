import sys,unittest,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tests'))
from build_overlay import source_bytes
import test_overlay

class ReleaseRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.fixture=test_overlay.OverlayTests();self.fixture.setUp()
        self.lua=self.fixture.lua;self.core=self.fixture.core

    def runtime(self):
        lua=self.lua;lua.globals()[b'HD2OverlayTest']=False
        lua.execute(b'update=function()end');lua.execute(source_bytes())
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
        state=lua.globals()[b'HD2TargetOverlay'];state[b'key']=7
        return tick,api,state,refresh,setval

    def test_formal_build_ignores_f8_f9_and_writes_no_diagnostic_files(self):
        source=source_bytes()
        for removed in [b'OUTPOST_DIAGNOSTIC',b'capture_outposts',b'calibration_points',b'calibration_rects',b"button_id('f8')",b"button_id('f9')",b"io.open(path,'wb')"]:
            self.assertNotIn(removed,source)
        tick,api,state,_,_=self.runtime()
        api[b'keys'][8]=True;api[b'keys'][9]=True
        with tempfile.TemporaryDirectory() as directory:
            self.lua.globals()[b'CowboyBingusModLoader']=self.lua.table_from({b'log_directory':directory.encode()})
            tick();tick()
            self.assertEqual(list(api[b'stats'][b'queried'].values()),[7,7])
            self.assertIsNone(state[b'calibration'])
            self.assertIsNone(state[b'capture_path'])
            self.assertEqual(list(Path(directory).iterdir()),[])


if __name__=='__main__':unittest.main()
