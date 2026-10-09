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
        self.assertLessEqual(self.stats[b'view'],330)  # One brief opening burst.
        self.assertLessEqual(self.stats[b'credit'],30)
        self.assertLessEqual(self.stats[b'box'],30)
        self.assertLessEqual(self.stats[b'mission'],30)
        self.assertEqual(self.stats[b'medal'],0)
        self.assertEqual(self.stats[b'project'],1)
        self.assertEqual(self.api[b'stats'][b'drawn'],8)
        self.assertEqual(self.api[b'stats'][b'destroyed'],0)

    def test_all_queries_finish_in_first_display_and_no_catchup_after_stall(self):
        self.at(0)
        for key in (b'credit',b'box',b'mission'):self.assertEqual(self.stats[key],1)
        self.assertEqual(self.stats[b'medal'],0)
        self.assertEqual(len(self.state[b'ids']),8)
        for t in (.21,.42,.63):self.at(t)
        self.at(100)
        for key in (b'credit',b'box',b'mission'):self.assertEqual(self.stats[key],2)
        self.at(100.001)
        self.assertEqual(self.stats[b'view'],5)

    def test_f7_has_no_effect_and_keyboard_is_never_polled(self):
        self.at(0)
        self.api[b'keys'][7]=True
        for t in (.034,.068,.51):self.at(t)
        self.assertEqual(len(self.state[b'ids']),8)
        self.assertEqual(list(self.api[b'stats'][b'queried'].values()),[])
        self.assertIsNone(self.state[b'enabled'])

    def test_map_close_clears_between_slow_display_updates(self):
        for t in (0,.21,.42,.63):self.at(t)
        self.assertEqual(len(self.state[b'ids']),8)
        reads=self.stats[b'view']
        self.setval(self.refresh,b'read',self.fixture.fixture.map_fixture(opened=False))
        self.at(.74)  # Visibility check is due; full display is not due until .83.
        self.assertEqual(len(self.state[b'ids']),0)
        self.assertEqual(self.stats[b'view'],reads+1)
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

    def test_option_and_world_changes_query_new_context_immediately(self):
        self.at(0)
        self.state[b'options'][b'credits']=False
        self.at(.21)
        self.assertIsNone(self.state[b'query'])
        self.assertEqual(self.stats[b'credit'],1)
        self.api[b'Application'][b'main_world']=self.lua.eval(b'function()return 2 end')
        self.api[b'Application'][b'worlds']=self.lua.eval(b'function()return {2}end')
        self.at(.42)
        self.assertEqual(self.state[b'query_world'],2)
        self.assertIsNone(self.state[b'query'])
        self.assertEqual(len(self.state[b'rows']),1)
        self.assertEqual(self.stats[b'mission'],3)

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

    def test_close_discards_rows_and_reopen_queries_and_draws_in_one_update(self):
        self.at(0)
        self.assertIsNone(self.state[b'query'])
        self.setval(self.refresh,b'read',self.fixture.fixture.map_fixture(opened=False))
        self.at(.21)
        self.assertIsNone(self.state[b'query'])
        self.assertIsNone(self.state[b'rows'])
        self.setval(self.refresh,b'read',self.fixture.fixture.map_fixture())
        self.at(.42)
        self.assertIsNone(self.state[b'query'])
        self.assertEqual(self.stats[b'credit'],2)

        self.assertEqual(len(self.state[b'ids']),8)

    def test_open_between_idle_ticks_queries_and_draws_immediately(self):
        self.setval(self.refresh,b'read',self.fixture.fixture.map_fixture(opened=False))
        self.at(0)
        self.setval(self.refresh,b'read',self.fixture.fixture.map_fixture())
        self.at(.101)
        self.assertEqual(len(self.state[b'ids']),8)
        for key in (b'credit',b'box',b'mission'):self.assertEqual(self.stats[key],1)
        self.assertAlmostEqual(self.state[b'next_display']-.101,1/60)

    def test_zoom_in_and_out_trigger_burst_then_return_to_low_frequency(self):
        for t in (0,.034,.068,.102,.51):self.at(t)
        for start,scale in ((.611,3),(1.223,1)):
            with self.subTest(scale=scale):
                self.setval(self.refresh,b'read',self.fixture.fixture.map_fixture(scale=scale))
                projects=self.stats[b'project'];views=self.stats[b'view']
                self.at(start)
                self.assertEqual(self.stats[b'view'],views+1)
                self.assertEqual(self.stats[b'project'],projects+1)
                self.assertAlmostEqual(self.state[b'next_display']-start,1/60)
                self.at(start+.034)
                self.assertEqual(self.stats[b'view'],views+2)
                self.at(start+.511)
                self.assertAlmostEqual(self.state[b'next_display']-(start+.511),.2)
                views=self.stats[b'view'];self.at(start+.55)
                self.assertEqual(self.stats[b'view'],views)
        self.assertEqual(self.stats[b'credit'],1)

    def test_continuous_zoom_extends_burst_but_pan_does_not(self):
        self.at(0)
        self.setval(self.refresh,b'read',self.fixture.fixture.map_fixture(scale=3))
        self.at(.4)
        self.assertAlmostEqual(self.state[b'fast_until'],.9)
        self.setval(self.refresh,b'read',self.fixture.fixture.map_fixture(scale=4))
        self.at(.8)
        self.assertAlmostEqual(self.state[b'fast_until'],1.3)
        original=self.core[b'map_view']
        self.core[b'map_view']=self.lua.eval(b'function(fn)return function(...)local v=fn(...);v.pan_x=v.pan_x+1;return v end end')(original)
        self.at(1.2)
        self.assertAlmostEqual(self.state[b'fast_until'],1.3)
        self.at(1.4)
        self.assertAlmostEqual(self.state[b'next_display'],1.6)

    def test_close_during_burst_extends_it_and_reopen_draws_fresh(self):
        self.at(0)
        self.setval(self.refresh,b'read',self.fixture.fixture.map_fixture(opened=False))
        self.at(.034)
        self.assertAlmostEqual(self.state[b'fast_until'],.534)
        self.assertIsNone(self.state[b'rows'])
        self.setval(self.refresh,b'read',self.fixture.fixture.map_fixture())
        self.at(.135)
        self.assertEqual(self.stats[b'credit'],2)
        self.assertEqual(len(self.state[b'ids']),8)

    def test_burst_does_not_repeat_resource_queries(self):
        self.at(0)
        for i in range(1,15):self.at(i*.034)
        for key in (b'credit',b'box',b'mission'):self.assertEqual(self.stats[key],1)
        self.assertEqual(self.stats[b'project'],1)
        self.at(2.1)
        for key in (b'credit',b'box',b'mission'):self.assertEqual(self.stats[key],2)

    def test_enabled_medals_query_in_same_display_update(self):
        self.state[b'options'][b'medals']=True
        self.at(0)
        for key in (b'credit',b'medal',b'box',b'mission'):self.assertEqual(self.stats[key],1)
        self.assertEqual(len(self.state[b'ids']),8)

    def test_configurable_regular_refresh_at_both_range_limits(self):
        for hz in (1,60):
            with self.subTest(hz=hz):
                self.setUp();self.state[b'options'][b'refresh_hz']=hz
                self.at(0);self.at(.51)
                self.assertAlmostEqual(self.state[b'next_display']-.51,1/hz)
                views=self.stats[b'view']
                self.at(.51+1/hz-.001)
                self.assertEqual(self.stats[b'view'],views)
                self.at(.51+1/hz+.001)
                self.assertEqual(self.stats[b'view'],views+1)
                self.assertEqual(self.stats[b'credit'],1)

    def test_configurable_boost_and_expiration_at_both_range_limits(self):
        for hz in (1,120):
            with self.subTest(hz=hz):
                self.setUp();self.state[b'options'][b'boost_hz']=hz
                self.at(0)
                self.assertAlmostEqual(self.state[b'next_display'],min(1/hz,.5))
                self.at(.5)
                self.assertAlmostEqual(self.state[b'next_display'],.7)
                self.assertEqual(self.stats[b'credit'],1)

    def test_close_triggers_selected_boost_and_does_not_query_models(self):
        self.state[b'options'][b'refresh_hz']=1
        self.state[b'options'][b'boost_hz']=60
        self.at(0);self.at(.51)
        self.setval(self.refresh,b'read',self.fixture.fixture.map_fixture(opened=False))
        self.at(.611)
        self.assertEqual(len(self.state[b'ids']),0)
        self.assertAlmostEqual(self.state[b'fast_until'],1.111)
        self.assertAlmostEqual(self.state[b'next_display']-.611,1/60)
        self.at(.628)
        self.assertAlmostEqual(self.state[b'fast_until'],1.111)  # Remaining closed cannot prolong the burst.
        self.assertEqual(self.stats[b'credit'],1)

    def test_rate_changes_do_not_change_target_query_context(self):
        self.at(0)
        key=self.state[b'query_options']
        self.state[b'options'][b'refresh_hz']=60
        self.state[b'options'][b'boost_hz']=60
        self.at(.034)
        self.assertEqual(self.state[b'query_options'],key)
        self.assertEqual(self.stats[b'credit'],1)
        self.assertAlmostEqual(self.state[b'next_display']-.034,1/60)

    def test_closing_animation_hides_on_first_frame_before_any_deadline(self):
        self.at(0)
        self.assertEqual(len(self.state[b'ids']),8)
        self.setval(self.refresh,b'read',self.fixture.fixture.map_fixture(closing=True))
        self.at(.001)  # The widget remains visible; only native open intent changed.
        self.assertEqual(len(self.state[b'ids']),0)
        self.assertIsNone(self.state[b'rows'])
        drawn=self.api[b'stats'][b'drawn']
        for t in (.002,.02,.04,.1,.2):self.at(t)
        self.assertEqual(self.api[b'stats'][b'drawn'],drawn)
        self.assertEqual(self.stats[b'credit'],1)

    def test_close_is_immediate_even_with_both_rates_set_to_one(self):
        self.state[b'options'][b'refresh_hz']=1;self.state[b'options'][b'boost_hz']=1
        self.at(0)
        self.setval(self.refresh,b'read',self.fixture.fixture.map_fixture(closing=True))
        self.at(.001)
        self.assertEqual(len(self.state[b'ids']),0)

    def test_idle_frame_only_reads_owner_and_open_flag(self):
        self.at(0)
        self.lua.globals()[b'fast_reads']=self.lua.table()
        self.setval(self.refresh,b'read',self.lua.eval(b"""function(fn)return function(a,n)
            fast_reads[#fast_reads+1]={a,n};return fn(a,n)
        end end""")(self.fixture.fixture.map_fixture()))
        self.at(.001)
        reads=self.lua.globals()[b'fast_reads']
        self.assertEqual(len(reads),2)
        self.assertEqual([r[2] for r in reads.values()],[8,1])
        self.assertEqual(reads[2][1],self.state[b'query_map']+0x195)
        self.assertEqual(self.stats[b'view'],1)
        self.assertEqual(self.stats[b'credit'],1)


if __name__=='__main__':unittest.main()
