import unittest
import test_release_runtime


class SchedulingTests(unittest.TestCase):
    def setUp(self):
        self.fixture=test_release_runtime.ReleaseRuntimeTests();self.fixture.setUp()
        self.lua=self.fixture.lua
        self.tick,self.api,self.state,self.refresh,self.setval=self.fixture.runtime()
        self.lua.globals()[b'test_time']=0
        self.setval(self.tick,b'clock',self.lua.eval(b'function()return test_time end'))
        self.core=self.lua.eval(b"""function(fn)
            for i=1,100 do local n,v=debug.getupvalue(fn,i);if n=='Core' then return v end end
        end""")(self.refresh)
        self.stats=self.lua.execute(b'return {view=0,project=0,credit=0,medal=0,box=0,mission=0}')
        wrap=self.lua.eval(b'function(stats,key,fn)return function(...)stats[key]=stats[key]+1;return fn(...)end end')
        for name,key in ((b'map_view',b'view'),(b'map_project',b'project')):
            self.core[name]=wrap(self.stats,key,self.core[name])
        for name,key in ((b'credit_positions',b'credit'),(b'medal_positions',b'medal'),(b'black_box_positions',b'box')):
            self.core[name]=wrap(self.stats,key,self.lua.eval(b'function()return {}end'))
        self.core[b'mission_rows']=wrap(self.stats,b'mission',self.lua.eval(b"function()return {{x=90,y=220,kind='objective'}},'' end"))

    def at(self, time):
        self.lua.globals()[b'test_time']=time;self.tick()

    def test_static_map_has_bounded_reads_and_only_one_projection_over_a_minute(self):
        for frame in range(112*60):self.at(frame/112)
        self.assertLessEqual(self.stats[b'view'],300)
        self.assertLessEqual(self.stats[b'credit'],30)
        self.assertLessEqual(self.stats[b'box'],30)
        self.assertLessEqual(self.stats[b'mission'],30)
        self.assertEqual(self.stats[b'medal'],0)
        self.assertEqual(self.stats[b'project'],1)
        self.assertEqual(self.api[b'stats'][b'drawn'],8)
        self.assertEqual(self.api[b'stats'][b'destroyed'],0)

    def test_queries_are_separate_and_no_catchup_after_stall(self):
        for time,key in ((0,b'credit'),(.21,b'medal'),(.42,b'box'),(.63,b'mission')):
            self.at(time)
            if key!=b'medal':self.assertEqual(self.stats[key],1)
        self.at(100)
        self.assertEqual(self.stats[b'credit'],2)
        self.assertEqual(self.stats[b'box'],1)
        self.assertEqual(self.stats[b'mission'],1)
        self.at(100.001)
        self.assertEqual(self.stats[b'view'],5)

    def test_f7_clears_immediately_between_display_ticks(self):
        for t in (0,.21,.42,.63):self.at(t)
        self.assertEqual(len(self.state[b'ids']),8)
        self.api[b'keys'][7]=True;self.at(.631)
        self.assertEqual(len(self.state[b'ids']),0)
        reads=self.stats[b'view']
        for i in range(100):self.at(.7+i*.01)
        self.assertEqual(self.stats[b'view'],reads)
        self.api[b'keys'][7]=False;self.at(2)
        self.api[b'keys'][7]=True;self.at(2.001)
        self.assertTrue(self.state[b'enabled'])
        self.assertEqual(self.stats[b'view'],reads+1)

    def test_map_close_clears_between_slow_display_updates(self):
        for t in (0,.21,.42,.63):self.at(t)
        self.assertEqual(len(self.state[b'ids']),8)
        reads=self.stats[b'view']
        self.setval(self.refresh,b'read',self.fixture.fixture.map_fixture(opened=False))
        self.at(.74)  # Visibility check is due; full display is not due until .83.
        self.assertEqual(len(self.state[b'ids']),0)
        self.assertEqual(self.stats[b'view'],reads)
        self.assertIsNone(self.state[b'query'])

    def test_snapshot_failure_waits_for_next_deadline(self):
        self.core[b'mission_rows']=self.lua.eval(b"function()error('scene unavailable')end")
        for t in (0,.21,.42,.63):self.at(t)
        self.assertIn(b'scene unavailable',self.state[b'snapshot_error'])
        self.assertEqual(len(self.state[b'rows']),0)
        for t in (.84,1.05,1.26,1.47,1.68,1.89):self.at(t)
        self.assertEqual(self.stats[b'credit'],1)
        self.assertIsNone(self.state[b'query'])
        self.at(2.1)
        self.assertEqual(self.stats[b'credit'],2)

    def test_option_and_world_changes_discard_partial_query(self):
        self.at(0)
        self.state[b'options'][b'credits']=False
        self.at(.21)
        self.assertEqual(self.state[b'query'][b'stage'],2)
        self.assertEqual(self.stats[b'credit'],1)
        self.api[b'Application'][b'main_world']=self.lua.eval(b'function()return 2 end')
        self.api[b'Application'][b'worlds']=self.lua.eval(b'function()return {2}end')
        self.at(.42)
        self.assertEqual(self.state[b'query_world'],2)
        self.assertEqual(self.state[b'query'][b'stage'],2)
        self.assertIsNone(self.state[b'rows'])

    def test_pan_curve_and_resize_invalidate_idle_projection(self):
        for t in (0,.21,.42,.63):self.at(t)
        original=self.core[b'map_view']
        self.core[b'map_view']=self.lua.eval(b'function(fn)return function(...)local v=fn(...);v.pan_x=v.pan_x+1;return v end end')(original)
        self.at(.84)
        self.assertEqual(self.stats[b'project'],2)
        self.at(1.05)
        self.assertEqual(self.stats[b'project'],2)
        self.api[b'Gui'][b'resolution']=self.lua.eval(b'function()return 3840,2160 end')
        self.at(1.26)
        self.assertEqual(self.stats[b'project'],3)
        self.core[b'map_view']=self.lua.eval(b'function(fn)return function(...)local v=fn(...);v.hud_curve=.5;return v end end')(original)
        self.at(1.47)
        self.assertEqual(self.stats[b'project'],4)

    def test_objective_snapshot_does_not_read_unused_poi_manager(self):
        fixture=self.fixture.fixture
        original=fixture.fixture()
        read=self.lua.eval(b"function(fn)return function(a,n)assert(a~=0x3326590,'unused POI read');return fn(a,n)end end")(original)
        rows,identity=self.core[b'snapshot'](read,0,True)
        self.assertEqual(len(rows),2)
        self.assertEqual(len(identity),16)

    def test_removed_target_clears_even_when_view_is_unchanged(self):
        for t in (0,.21,.42,.63):self.at(t)
        self.assertEqual(len(self.state[b'ids']),8)
        self.core[b'mission_rows']=self.lua.eval(b"function()return {},'' end")
        for t in (2.1,2.31,2.52,2.73):self.at(t)
        self.assertEqual(len(self.state[b'ids']),0)

    def test_close_discards_partial_batch_and_reopen_starts_fresh(self):
        self.at(0)
        self.assertEqual(self.state[b'query'][b'stage'],2)
        self.setval(self.refresh,b'read',self.fixture.fixture.map_fixture(opened=False))
        self.at(.21)
        self.assertIsNone(self.state[b'query'])
        self.assertIsNone(self.state[b'rows'])
        self.setval(self.refresh,b'read',self.fixture.fixture.map_fixture())
        self.at(.42)
        self.assertEqual(self.state[b'query'][b'stage'],2)
        self.assertEqual(self.stats[b'credit'],2)


if __name__=='__main__':unittest.main()
