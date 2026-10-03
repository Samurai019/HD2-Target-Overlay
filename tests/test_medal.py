import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_overlay
import test_release_runtime


class MedalTests(unittest.TestCase):
    def setUp(self):
        fixture = test_overlay.OverlayTests(); fixture.setUp()
        self.lua, self.core = fixture.lua, fixture.core

    def test_model_interaction_position_pickup_and_default_off(self):
        api = self.lua.execute(b"""local alive=true;return {
            IdString64={from_hex=function(v)assert(v=='773c4184e4bad0df');return v end},
            IdString32={from_hex=function(v)assert(v=='e4a4586d');return v end},
            World={units_by_resource=function()return {1,1,2} end},
            Unit={alive=function(u)return alive and u==1 end,
                has_node=function()return true end,node=function()return 7 end,
                world_position=function(u,n)if n==0 then return {0,0,0} end return {120,230,10} end},
            Vector3={x=function(p)return p[1] end,y=function(p)return p[2] end,z=function(p)return p[3] end},
            pickup=function()alive=false end}""")
        worlds=self.lua.table_from([1]); empty=self.lua.table_from([])
        points=self.core[b'medal_positions'](api,worlds,1)
        self.assertEqual(len(points),1)
        self.assertEqual(points[1][b'x'],120)
        self.assertEqual(len(self.core[b'filter'](empty,empty,empty,None,empty,points)),0)
        options=self.lua.table_from({b'medals':True})
        rows=self.core[b'filter'](empty,empty,empty,options,empty,points)
        self.assertEqual(rows[1][b'kind'],b'medal')
        api[b'pickup']()
        self.assertEqual(len(self.core[b'medal_positions'](api,worlds,1)),0)

    def test_runtime_skips_disabled_query_and_isolates_failure(self):
        fixture=test_release_runtime.ReleaseRuntimeTests(); fixture.setUp()
        tick,api,state,refresh,setval=fixture.runtime()
        core=fixture.lua.eval(b"""function(fn)
            for i=1,100 do local n,v=debug.getupvalue(fn,i);if n=='Core' then return v end end
        end""")(refresh)
        fixture.lua.globals()[b'query_calls']=0
        core[b'medal_positions']=fixture.lua.eval(b"function() query_calls=query_calls+1;error('query failed') end")
        core[b'mission_rows']=fixture.lua.eval(b"function(r,b,c,o,boxes,medals) assert(#medals==0);return {{kind='objective',x=0,y=0}},'' end")
        self.assertFalse(state[b'options'][b'medals'])
        tick()
        self.assertEqual(fixture.lua.globals()[b'query_calls'],0)
        state[b'options'][b'medals']=True;state[b'rows']=None
        tick()
        self.assertEqual(fixture.lua.globals()[b'query_calls'],1)
        self.assertIn(b'query failed',state[b'medal_error'])
        self.assertEqual(state[b'rows'][1][b'kind'],b'objective')


if __name__=='__main__': unittest.main()
