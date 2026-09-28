import sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tests'))
from build_overlay import source_bytes
import test_overlay

class OutpostDiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.fixture=test_overlay.OverlayTests();self.fixture.setUp()
        self.core=self.fixture.core

    def report(self,read):
        options=self.fixture.lua.table_from({b'outposts':True})
        return self.core[b'outpost_diagnostic'](read,0,options,None)

    def test_raw_records_preserved_and_clear_decisions_reported(self):
        report=self.report(self.fixture.outpost_fixture((3,15,255,0),discovered=(0,),completed=(1,)))
        self.assertIn(b'count=4',report)
        self.assertIn(b'parsed_count=2',report)
        self.assertIn(b'type=3 xy=(11.000,22.000) discovered=true cleared=false',report)
        self.assertIn(b'type=15 xy=(111.000,22.000) discovered=false cleared=true',report)
        self.assertIn(b'keep=true',report);self.assertIn(b'keep=false',report)
        for i in range(4):self.assertIn(('record=%d position_hex='%i).encode(),report)
        self.assertIn(b'PARSE_ERRORS=',report)
        self.assertIn(b'unexpected outpost type',report)
        self.assertIn(b'scene_consistent=true',report)

    def test_unreadable_record_and_changed_scene_leave_report(self):
        report=self.report(self.fixture.outpost_fixture((3,15),missing=(0,)))
        self.assertIn(b'record=0 position_hex=UNREADABLE',report)
        self.assertIn(b'parsed_count=1',report)
        report=self.report(self.fixture.outpost_fixture(race=True))
        self.assertIn(b'scene_consistent=false',report)
        self.assertIn(b'PARSE_ERROR=',report)

    def test_missing_root_and_empty_list_leave_report(self):
        read=self.fixture.lua.eval(b'function()return nil end')
        report=self.report(read)
        self.assertIn(b'CAPTURE_ERROR=',report);self.assertIn(b'PARSE_ERROR=',report)
        report=self.report(self.fixture.outpost_fixture(()))
        self.assertIn(b'count=0',report);self.assertIn(b'parsed_count=0',report)

    def test_capture_is_bounded_even_for_rejected_count(self):
        report=self.report(self.fixture.outpost_fixture((3,)*129))
        self.assertIn(b'count=129',report)
        self.assertIn(b'record=127 ',report)
        self.assertNotIn(b'record=128 ',report)
        self.assertIn(b'unexpected outpost count',report)

    def test_normal_build_disables_diagnostic_and_both_compile(self):
        for enabled in (False,True):
            source=source_bytes(enabled)
            self.assertIn(b'local OUTPOST_DIAGNOSTIC='+str(enabled).lower().encode(),source)
            self.fixture.lua.execute(b'assert(loadstring(...))',source)

    def test_alignment_capture_has_view_containers_and_32_widget_bound(self):
        map_read=self.fixture.map_fixture()
        post_read=self.fixture.outpost_fixture()
        read=self.fixture.lua.eval(b'function(a,b)return function(p,n)return a(p,n) or b(p,n) end end')(map_read,post_read)
        view=self.core[b'map_view'](read,0,1920,1080)
        report=self.core[b'outpost_diagnostic'](read,0,self.fixture.lua.table_from({b'outposts':True}),view)
        self.assertIn(b'view_width=1920',report)
        self.assertIn(b'view_tx=800',report)
        self.assertIn(b'container_outposts_hex=UNREADABLE',report)
        self.assertIn(b'native_outpost_widget=31 hex=',report)
        self.assertNotIn(b'native_outpost_widget=32 ',report)
        self.assertIn(b'OBJECTIVE_CAPTURE_ERROR=',report)
        self.assertIn(b'parsed_count=1',report)

    def test_f8_saves_once_per_press_without_repeating_while_held(self):
        lua=self.fixture.lua
        lua.globals()[b'HD2OverlayTest']=False
        lua.execute(b'update=function()end')
        lua.execute(source_bytes(True))
        find=lua.eval(b"""function(fn,wanted)
            local seen={}
            local function visit(f)
                if seen[f] then return end;seen[f]=true
                local children={}
                for i=1,100 do
                    local n,v=debug.getupvalue(f,i);if not n then break end
                    if n==wanted then return v end
                    if type(v)=='function' then children[#children+1]=v end
                end
                for _,child in ipairs(children) do local v=visit(child);if v~=nil then return v end end
            end
            local result=visit(fn);assert(result,'missing '..wanted);return result
        end""")
        set_upvalue=lua.eval(b"""function(fn,wanted,value)
            for i=1,100 do local n=debug.getupvalue(fn,i);if not n then break end
                if n==wanted then debug.setupvalue(fn,i,value);return end end
            error('missing '..wanted)
        end""")
        tick=find(lua.globals()[b'update'],b'tick')
        capture=find(tick,b'capture_outposts')
        state=lua.globals()[b'HD2TargetOverlay']
        api=lua.execute(b"""local down=true;return {
            Gui={resolution=function()return 1920,1080 end},
            Keyboard={button=function(key)return key==8 and down or false end},
            set_down=function(value)down=value end}
        """)
        set_upvalue(tick,b'worker',None)
        set_upvalue(tick,b'refresh',lua.eval(b'function()end'))
        set_upvalue(tick,b'sr',api)
        set_upvalue(capture,b'read',self.fixture.outpost_fixture((3,15)))
        set_upvalue(capture,b'base',0)
        state[b'key']=7;state[b'capture_key']=8
        with tempfile.TemporaryDirectory(prefix='hd2_outpost_') as directory:
            lua.globals()[b'CowboyBingusModLoader']=lua.table_from({b'log_directory':directory.encode()})
            tick()
            path=Path(directory)/'TargetOverlay_OUTPOST_DIAGNOSTIC.txt'
            self.assertIn(b'parsed_count=2',path.read_bytes())
            self.assertIsNone(state[b'capture_error'])
            path.unlink();tick();self.assertFalse(path.exists())
            api[b'set_down'](False);tick()
            api[b'set_down'](True);tick();self.assertTrue(path.exists())

if __name__=='__main__':unittest.main()
