import unittest
from test_release_runtime import ReleaseRuntimeTests


class OverlayPerformanceTests(ReleaseRuntimeTests):
    def test_cached_shapes_and_exact_raster_coverage(self):
        cache = self.lua.table()
        for scale in (1, 1.25, 2):
            for kind in (b'objective', b'outpost', b'credit_poi', b'black_box', b'medal', b'stalker_lair'):
                for size, thickness in ((22*scale, 2*scale), (30*scale, 8*scale)):
                    raw = self.core[b'glyph'](kind, size, thickness, scale)
                    merged = self.core[b'compact_glyph'](raw)
                    # Independent scanline coverage comparison, including medal colors.
                    def coverage(parts):
                        spans = []
                        for p in parts.values():
                            color = tuple(p[5].values()) if p[5] else None
                            for i in range(round(p[4]/scale)):
                                spans.append((p[1], p[2]+i*scale, p[3], color))
                        return sorted(spans, key=repr)
                    self.assertEqual(coverage(raw), coverage(merged))
                p = self.lua.table_from({b'kind':kind, b'size':22*scale})
                a = self.core[b'marker_parts'](cache, p, scale)
                b = self.core[b'marker_parts'](cache, p, scale)
                self.assertTrue(self.lua.eval(b'function(a,b)return rawequal(a,b)end')(a,b))
            self.assertEqual(len(list(cache[b'shapes'].keys())), 6)
        raw = self.core[b'glyph'](b'objective', 22, 2, 1)
        self.assertEqual(len(self.core[b'compact_glyph'](raw)), 4)

    def configured_runtime(self, update=True):
        tick, api, state, refresh, setval = self.runtime()
        setval(tick, b'clock', self.lua.eval(b'function()local t=0;return function()t=t+0.21;return t end end')())
        if update:
            api[b'Gui'][b'update_rect'] = self.lua.eval(b'function(stats)return function()stats.updated=(stats.updated or 0)+1 end end')(api[b'stats'])
        state[b'rows'] = self.lua.execute(b"return {{kind='objective',x=90,y=220},{kind='outpost',x=100,y=220}}")
        state[b'query_world']=1
        state[b'query_map']=self.core[b'map_view'](self.fixture.map_fixture(),0,1920,1080)[b'map_address']
        state[b'query_options']=self.core[b'options_key'](state[b'options'])
        state[b'next_query']=1e30
        return tick, api, state, refresh, setval

    def replace_rows(self, state):
        state[b'rows']=self.lua.eval(b'function(rows)local copy={};for i,p in ipairs(rows)do copy[i]=p end;return copy end')(state[b'rows'])

    def test_stationary_and_pan_reuse_then_pickup_removes_tail(self):
        tick, api, state, _, _ = self.configured_runtime()
        tick()
        stats = api[b'stats']; initial = stats[b'drawn']
        self.assertGreater(initial, 0)
        tick()
        self.assertEqual(stats[b'drawn'], initial)
        self.assertIsNone(stats[b'updated'])
        state[b'rows'][1][b'x'] += 1
        self.replace_rows(state)
        tick()
        self.assertGreater(stats[b'updated'], 0)
        self.assertLess(stats[b'updated'], initial)  # Other marker is untouched.
        self.assertEqual(stats[b'drawn'], initial)
        self.assertEqual(stats[b'destroyed'], 0)
        state[b'rows'][2] = None
        self.replace_rows(state)
        tick()
        self.assertEqual(len(state[b'ids']), 8)  # Hollow square + outline.
        self.assertEqual(stats[b'destroyed'], initial-8)

    def test_missing_or_throwing_update_falls_back_without_leaking(self):
        for throwing in (False, True):
            self.setUp()
            tick, api, state, _, _ = self.configured_runtime(update=False)
            if throwing:
                api[b'Gui'][b'update_rect'] = self.lua.eval(b"function(stats)return function()stats.failures=(stats.failures or 0)+1;error('unsupported')end end")(api[b'stats'])
            tick()
            for _ in range(3):
                state[b'rows'][1][b'x'] += 1
                self.replace_rows(state)
                tick()
            stats = api[b'stats']
            self.assertEqual(stats[b'drawn']-stats[b'destroyed'], len(state[b'ids']))
            self.assertEqual(stats[b'destroyed'], 24)
            if throwing: self.assertEqual(stats[b'failures'], 1)

    def test_close_and_reopen_and_resolution_invalidate_shapes(self):
        tick, api, state, refresh, setval = self.configured_runtime()
        rows = state[b'rows']; tick()
        api[b'Gui'][b'resolution'] = self.lua.eval(b'function()return 3840,2160 end')
        tick()
        self.assertEqual(state[b'glyph_cache'][b'scale'], 2)
        setval(refresh, b'read', self.fixture.map_fixture(opened=False))
        tick()
        self.assertEqual(len(state[b'ids']), 0)
        self.assertEqual(len(list(state[b'rects'].keys())), 0)
        count = api[b'stats'][b'destroyed']; tick()
        self.assertEqual(api[b'stats'][b'destroyed'], count)
        setval(refresh, b'read', self.fixture.map_fixture())
        tick()  # Establish the new query context after reopening.
        state[b'query']=None;state[b'next_query']=1e30
        state[b'rows'] = rows; tick()
        self.assertGreater(len(state[b'ids']), 0)

    def test_world_switch_does_not_touch_dead_world_gui(self):
        tick, api, state, _, _ = self.configured_runtime()
        tick()
        rows=state[b'rows']
        api[b'Application'][b'worlds'] = self.lua.eval(b'function()return {2}end')
        api[b'Application'][b'main_world'] = self.lua.eval(b'function()return 2 end')
        tick()
        self.assertIsNone(state[b'rows'])  # Never display previous-world targets.
        state[b'query']=None;state[b'next_query']=1e30;state[b'rows']=rows
        tick()
        self.assertEqual(state[b'world'], 2)
        self.assertEqual(api[b'stats'][b'destroyed'], 0)
        self.assertEqual(api[b'stats'][b'created'], 2)

    def test_only_main_world_is_queried(self):
        api = self.lua.execute(b"""return {
            IdString64={from_hex=function(v)return v end},
            World={units_by_resource=function(w)assert(w==2,'non-gameplay query');return {}end}}
        """)
        self.core[b'credit_positions'](api, self.lua.table_from([1,2,3]), 2)

    def test_disabled_mission_categories_skip_memory_reads(self):
        options = self.lua.execute(b'return {credits=true}')
        read = self.lua.eval(b"function()error('unnecessary read')end")
        rows, error = self.core[b'mission_rows'](read, 0, self.lua.execute(b'return {{x=1,y=2}}'), options)
        self.assertEqual(len(rows), 1)
        self.assertEqual(error, b'')


if __name__ == '__main__':
    unittest.main()
