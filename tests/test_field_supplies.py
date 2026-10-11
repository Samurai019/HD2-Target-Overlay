import itertools
import json
import unittest
from pathlib import Path
import test_overlay
import test_release_runtime


class FieldSupplyTests(unittest.TestCase):
    def setUp(self):
        fixture = test_overlay.OverlayTests(); fixture.setUp()
        self.lua, self.core = fixture.lua, fixture.core
        self.worlds = self.lua.table_from([1, 2])
        self.api = self.lua.execute(b'''local alive={true,true,true};local calls={}
            return {calls=calls,alive=alive,
                IdString64={from_hex=function(v)return v end},
                IdString32={from_hex=function(v)assert(v=='4a182741');return v end},
                World={units_by_resource=function(w,m)
                    assert(w==1);calls[#calls+1]=m
                    local ids={['79ccffd281e3f3a9']=1,['97af34fbf093409c']=2,['b4ca4c5b922f7965']=3}
                    local i=assert(ids[m],'unexpected resource queried');return {i,i} end},
                Unit={alive=function(i)return alive[i] end,
                    has_node=function()return true end,node=function()return 0 end,
                    world_position=function(i,node)assert(node==0);return {i*100,200,10} end},
                Vector3={x=function(v)return v[1] end,y=function(v)return v[2] end,z=function(v)return v[3] end}}
        ''')
        self.state = self.lua.execute(b'return {options={ammo=true,grenades=true,stims=true}}')

    def collect(self):
        return self.core[b'collect_supplies'](self.state, self.api, self.worlds, 1)

    def test_resource_ids_match_extracted_entity_evidence(self):
        evidence = json.loads((Path(__file__).resolve().parents[1] / 'research/field-supplies.json').read_text())
        for spec, source in zip(self.core[b'supply_specs'].values(), evidence['supplies']):
            self.assertEqual(spec[b'key'].decode(), source['category'])
            self.assertEqual(spec[b'model'].decode(), source['model'])
            self.assertEqual(source['node_hash'], '4a182741')
            self.assertTrue(source['delete_after_interact'])

    def test_live_boxes_dedup_and_root_node_zero_is_valid(self):
        supplies = self.collect()
        for i, key in enumerate((b'ammo', b'grenades', b'stims'), 1):
            self.assertEqual(len(supplies[key]), 1)
            self.assertEqual(supplies[key][1][b'x'], i*100)
            self.assertEqual(self.state[key+b'_count'], 1)
        self.assertEqual(len(self.api[b'calls']), 3)

    def test_pickup_destroy_and_unload_remove_only_affected_markers(self):
        self.collect()
        self.api[b'alive'][2] = False  # another player can also destroy this unit
        supplies = self.collect()
        self.assertEqual([len(supplies[k]) for k in (b'ammo',b'grenades',b'stims')], [1,0,1])
        self.api[b'World'][b'units_by_resource'] = self.lua.eval(b'function()return {} end')
        supplies = self.collect()
        self.assertTrue(all(len(v)==0 for v in supplies.values()))

    def test_off_means_no_queries_and_clears_stale_error(self):
        keys = [b'ammo',b'grenades',b'stims']
        for values in itertools.product([False,True], repeat=3):
            before = len(self.api[b'calls'])
            for key,value in zip(keys,values):
                self.state[b'options'][key] = value
                self.state[key+b'_error'] = b'previous failure'
            supplies = self.collect()
            self.assertEqual(len(self.api[b'calls'])-before, sum(values))
            self.assertEqual([len(supplies[k]) for k in keys], list(map(int,values)))
            self.assertTrue(all(self.state[k+b'_error'] is None for k in keys))

    def test_query_failure_isolated_and_recovers(self):
        self.lua.globals()[b'api'] = self.api
        restore = self.lua.execute(b'''local old=api.World.units_by_resource
            api.World.units_by_resource=function(w,m)
                if m=='97af34fbf093409c' then error('unavailable') end;return old(w,m) end
            return function()api.World.units_by_resource=old end''')
        supplies = self.collect()
        self.assertEqual([len(supplies[k]) for k in (b'ammo',b'grenades',b'stims')], [1,0,1])
        self.assertIn(b'unavailable', self.state[b'grenades_error'])
        restore();self.assertEqual(len(self.collect()[b'grenades']), 1)
        self.assertIsNone(self.state[b'grenades_error'])

    def test_no_gameplay_world_no_query(self):
        self.core[b'collect_supplies'](self.state,self.api,self.worlds,None)
        self.assertEqual(len(self.api[b'calls']), 0)

    def test_named_root_resolves_zero_root_and_invalid_origin_is_rejected(self):
        self.api[b'Unit'][b'node'] = self.lua.eval(b'function()return 7 end')
        self.api[b'Unit'][b'world_position'] = self.lua.eval(b'''function(i,n)
            if n==0 then return {0,0,0} end
            if i==1 then return {120,230,10} end
            if i==2 then return {.06,-.08,.09} end
            return {0/0,200,10} end''')
        supplies = self.collect()
        self.assertEqual([len(supplies[k]) for k in (b'ammo',b'grenades',b'stims')], [1,0,0])

    def test_enumeration_bound(self):
        self.api[b'World'][b'units_by_resource'] = self.lua.eval(b'function()local t={} for i=1,513 do t[i]=1 end return t end')
        supplies = self.collect()
        self.assertTrue(all(len(v)==0 for v in supplies.values()))
        self.assertIn(b'too many model units', self.state[b'ammo_error'])

    def test_supplies_only_without_mission_table_access(self):
        supplies = self.collect()
        read = self.lua.eval(b'function()error("must not read mission tables")end')
        empty = self.lua.table()
        rows, errors = self.core[b'mission_rows'](read,0,empty,self.state[b'options'],empty,empty,supplies)
        self.assertEqual([r[b'kind'] for r in rows.values()], [b'ammo',b'grenades',b'stims'])
        self.assertEqual(errors,b'')

    def test_icons_distinct_positive_and_cached_at_multiple_scales(self):
        glyphs = []
        for key in (b'ammo',b'grenades',b'stims'):
            glyphs.append([tuple(r.values()) for r in self.core[b'glyph'](key,16,2,1).values()])
            for scale in (.5,1,2):
                cache = self.lua.table()
                point = self.lua.table_from({b'kind':key,b'size':16*scale})
                parts = self.core[b'marker_parts'](cache,point,scale)
                again = self.core[b'marker_parts'](cache,point,scale)
                self.assertTrue(self.lua.eval(b'function(a,b)return rawequal(a,b)end')(parts,again))
                self.assertTrue(all(r[3]>0 and r[4]>0 for r in parts.values()))
        self.assertEqual(len({str(g) for g in glyphs}),3)

    def test_runtime_default_on_independent_of_mission_failure_and_two_second_poll(self):
        fixture = test_release_runtime.ReleaseRuntimeTests();fixture.setUp()
        tick,api,state,refresh,setval = fixture.runtime()
        lua = fixture.lua
        lua.execute(b'field_clock=0;field_queries=0')
        setval(tick,b'clock',lua.eval(b'function()return field_clock end'))
        core = lua.eval(b'''function(fn)
            for i=1,100 do local n,v=debug.getupvalue(fn,i);if n=='Core' then return v end end end''')(refresh)
        core[b'supply_positions'] = lua.eval(b'function()field_queries=field_queries+1;return {{x=100,y=200}} end')
        core[b'mission_rows'] = lua.eval(b'function()error("mission unavailable")end')
        tick();self.assertEqual(lua.globals()[b'field_queries'],3)
        self.assertEqual(sorted(r[b'kind'] for r in state[b'rows'].values()),[b'ammo',b'grenades',b'stims'])
        lua.globals()[b'field_clock']=1;tick()
        self.assertEqual(lua.globals()[b'field_queries'],3)
        lua.globals()[b'field_clock']=2.1;tick()
        self.assertEqual(lua.globals()[b'field_queries'],6)
        state[b'options'][b'ammo']=False
        lua.globals()[b'field_clock']=2.4;tick()
        self.assertEqual(lua.globals()[b'field_queries'],8)
        self.assertEqual(sorted(r[b'kind'] for r in state[b'rows'].values()),[b'grenades',b'stims'])


if __name__ == '__main__':
    unittest.main()
