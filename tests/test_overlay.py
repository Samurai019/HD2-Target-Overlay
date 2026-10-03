import sys,struct,unittest,json
from pathlib import Path
from lupa.luajit21 import LuaRuntime
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from build_overlay import source_bytes
class OverlayTests(unittest.TestCase):
    def setUp(self):
        self.lua=LuaRuntime(encoding=None,unpack_returned_tuples=True)
        self.lua.globals()[b'HD2OverlayTest']=True
        self.core=self.lua.execute(source_bytes())
    def fixture(self,count=2,nan=False,race=False,objective_states=(0,0),reveal_states=(1,1)):
        memory={};heads=[]
        for root,addr,offset,stride,data in [(0x3326590,0x10000,12,20,0x30000),(0x3326da0,0x20000,36,100,0x40000)]:
            memory[root]=struct.pack('<Q',addr)
            head=bytearray(112);struct.pack_into('<I',head,offset,count)
            struct.pack_into('<Q',head,72 if stride==20 else 104,data)
            memory[addr]=bytes(head);heads.append(addr)
            rows=bytearray(stride*2)
            for i in range(2):struct.pack_into('<fff',rows,i*stride,float('nan') if nan else i*100.0,i*50.0,4)
            if stride==100:
                for i,value in enumerate(objective_states):struct.pack_into('<I',rows,i*stride+0x20,value)
                for i,value in enumerate(reveal_states):struct.pack_into('<I',rows,i*stride+0x44,value)
            memory[data]=bytes(rows)
        calls={}
        def read(addr,n):
            calls[addr]=calls.get(addr,0)+1
            if race and addr in heads and calls[addr]>1:return b'\0'*n
            blob=memory.get(addr)
            return blob[:n] if blob and len(blob)>=n else None
        return self.lua.eval(b'function(f)return function(...)return f(...)end end')(read)
    def test_two_record_layouts(self):
        rows,identity=self.core[b'snapshot'](self.fixture(),0)
        self.assertEqual(len(rows),4);self.assertEqual(rows[2][b'x'],100);self.assertEqual(rows[4][b'y'],50)
        self.assertEqual(rows[1][b'kind'],b'marker');self.assertEqual(rows[4][b'kind'],b'objective')
    def test_invalid_count_refused(self):
        with self.assertRaises(Exception):self.core[b'snapshot'](self.fixture(count=513),0)
    def test_scene_race_refused(self):
        with self.assertRaises(Exception):self.core[b'snapshot'](self.fixture(race=True),0)
    def test_nan_filtered(self):
        rows,_=self.core[b'snapshot'](self.fixture(nan=True),0);self.assertEqual(len(rows),0)
    def test_no_patch_or_discovery_apis(self):
        s=source_bytes()
        for forbidden in [b'WriteProcessMemory',b'VirtualProtect',b'OpenProcess(',b'FlushInstructionCache',b'ffi.copy(',b'set_game_object_field',b'game_object_set_field']:
            self.assertNotIn(forbidden,s)
    def test_filter_categories_and_direct_credit_positions(self):
        rows=self.lua.table_from([self.lua.table_from({b'kind':kind,b'x':x,b'y':0,b'importance':importance,b'small_poi':small})
            for kind,x,importance,small in [(b'objective',0,0,False),(b'objective',1,1,False),
            (b'objective',2,2,False),(b'objective',3,3,False),(b'marker',100,0,True),(b'marker',200,0,True)]])
        credits=self.lua.table_from([self.lua.table_from({b'x':105,b'y':0})])
        posts=self.lua.table_from([self.lua.table_from({b'kind':b'outpost',b'x':300,b'y':0})])
        result=self.core[b'filter'](rows,credits,posts)
        self.assertEqual([result[i][b'kind'] for i in range(1,len(result)+1)],
                         [b'objective',b'credit_poi',b'outpost'])
        self.assertEqual(result[2][b'x'],105)
        empty=self.lua.table_from([])
        self.assertEqual(len(self.core[b'filter'](rows,empty,posts)),2)
    def test_credit_independent_of_poi_distance_and_ambiguity(self):
        def row(x):return self.lua.table_from({b'kind':b'marker',b'x':x,b'y':0,b'small_poi':True})
        def check(xs,x):
            return self.core[b'filter'](self.lua.table_from([row(v) for v in xs]),
                self.lua.table_from([self.lua.table_from({b'x':x,b'y':0})]),self.lua.table_from([]))
        self.assertEqual(len(check([0],36)),1)
        self.assertEqual(len(check([0,10],5)),1)
        self.assertEqual(len(check([0,100],2)),1)
    def test_credit_query_alive_deduplicated_and_bounded(self):
        api=self.lua.execute(b"""local units={1,2,3};return {
            IdString64={from_hex=function(v)assert(v=='bd6f4de16b9aedcd');return v end},
            World={units_by_resource=function()return units end},
            Unit={alive=function(u)return u~=2 end,world_position=function(u,n)assert(n==0);return {u,0} end},
            Vector3={x=function(p)return p[1] end,y=function(p)return p[2] end}}""")
        result=self.core[b'credit_positions'](api,self.lua.table_from([1,2]))
        self.assertEqual(len(result),2)
        api[b'World'][b'units_by_resource']=self.lua.eval(b'function()return nil end')
        with self.assertRaises(Exception):self.core[b'credit_positions'](api,self.lua.table_from([1]))
        api[b'World'][b'units_by_resource']=self.lua.eval(b'function()local t={} for i=1,129 do t[i]=i end return t end')
        with self.assertRaises(Exception):self.core[b'credit_positions'](api,self.lua.table_from([1]))
    def test_credit_interaction_node_resolves_zero_root(self):
        api=self.lua.execute(b"""return {
            IdString64={from_hex=function(v)return v end},
            IdString32={from_hex=function(v)assert(v=='e4a4586d');return v end},
            World={units_by_resource=function()return {1,2} end},
            Unit={alive=function()return true end,
                has_node=function()return true end,node=function()return 7 end,
                world_position=function(u,n)if n==0 then return {0,0,0} end
                    if u==1 then return {120,230,10} else return {.06,-.08,.09} end end},
            Vector3={x=function(p)return p[1] end,y=function(p)return p[2] end,z=function(p)return p[3] end}}
        """)
        points=self.core[b'credit_positions'](api,self.lua.table_from([1]),1)
        self.assertEqual(len(points),1)
        self.assertEqual(points[1][b'x'],120)
        self.assertEqual(points[1][b'y'],230)

    def test_credit_excludes_auxiliary_world_models(self):
        api=self.lua.execute(b"""return {
            IdString64={from_hex=function(v)return v end},
            World={units_by_resource=function(w)return {w} end},
            Unit={alive=function()return true end,world_position=function(u)return {u*10,20} end},
            Vector3={x=function(p)return p[1] end,y=function(p)return p[2] end}}""")
        points=self.core[b'credit_positions'](api,self.lua.table_from([1,2]),2)
        self.assertEqual(len(points),1)
        self.assertEqual(points[1][b'x'],20)

    def test_credit_marker_removed_when_unit_picked_up(self):
        api=self.lua.execute(b"""local alive=true;return {
            IdString64={from_hex=function(v)return v end},
            World={units_by_resource=function()return {1} end},
            Unit={alive=function()return alive end,world_position=function()return {12,34} end},
            Vector3={x=function(p)return p[1] end,y=function(p)return p[2] end},
            pickup=function()alive=false end}""")
        empty=self.lua.table_from([])
        worlds=self.lua.table_from([1])
        points=self.core[b'credit_positions'](api,worlds)
        marked=self.core[b'filter'](empty,points,empty)
        self.assertEqual(len(marked),1)
        self.assertEqual(marked[1][b'x'],12)
        api[b'pickup']()
        points=self.core[b'credit_positions'](api,worlds)
        self.assertEqual(len(self.core[b'filter'](empty,points,empty)),0)

    def outpost_fixture(self,categories=(3,),discovered=(),missing=(),race=False,completed=(),uncounted=()):
        head=bytearray(112);struct.pack_into('<I',head,12,len(categories))
        struct.pack_into('<QQ',head,72,0x20000,0x30000)
        memory={0x33265c0:struct.pack('<Q',0x10000),0x10000:bytes(head),
                0x32fcde0:bytes.fromhex(json.loads((ROOT/'tests/fixtures/outpost-types-supported-build.json').read_text())['settings_hex']).ljust(256*32,b'\0')}
        for i,category in enumerate(categories):
            position=bytearray(0x2b8);struct.pack_into('<fff',position,0,11+i*100,22,3)
            position[0x2a0]=category
            position[0x2ab]=int(i not in uncounted)
            net=bytearray(64);net[0x39]=int(i in completed);net[0x3b]=int(i in discovered)
            if i not in missing:memory[0x20000+i*0x2b8]=bytes(position)
            memory[0x30000+i*64]=bytes(net)
        calls={}
        def read(a,n):
            calls[a]=calls.get(a,0)+1
            if race and a==0x33265c0 and calls[a]>1:return struct.pack('<Q',0x10008)
            b=memory.get(a);return b[:n] if b and len(b)>=n else None
        return self.lua.eval(b'function(f)return function(...)return f(...)end end')(read)

    def test_all_outposts_survive_discovery_until_cleared(self):
        empty=self.lua.table_from([])
        # Real settings cover hidden types 1,9,15,20 and ordinary types.
        categories=tuple(range(1,21))
        hidden=[1,9,15,20]
        for discovered in ((),tuple(range(len(categories)))):
            for completed in ((),tuple(range(len(categories))),tuple(range(0,len(categories),2))):
                posts,error=self.core[b'outposts'](self.outpost_fixture(categories,discovered=discovered,completed=completed),0)
                self.assertEqual(error,b'')
                for i,category in enumerate(categories,1):
                    self.assertEqual(posts[i][b'native_hidden'],category in hidden)
                    self.assertEqual(posts[i][b'completed'],i-1 in completed)
                selected=self.core[b'filter'](empty,empty,posts)
                expected=[category for i,category in enumerate(categories) if i not in completed]
                self.assertEqual([selected[i][b'category'] for i in range(1,len(selected)+1)],expected)

    def test_outpost_bad_record_does_not_hide_other_nests(self):
        result,error=self.core[b'outposts'](self.outpost_fixture((3,255,20),missing=(0,)),0)
        self.assertEqual(len(result),1);self.assertEqual(result[1][b'category'],20)
        self.assertIn(b'record 0:',error);self.assertIn(b'record 1:',error)
        with self.assertRaises(Exception):
            self.core[b'outposts'](self.outpost_fixture(race=True),0)

    def test_dual_role_nest_keeps_independent_markers(self):
        posts,_=self.core[b'outposts'](self.outpost_fixture((1,)),0)
        objectives=self.lua.execute(b"return {{kind='objective',importance=3,x=11,y=22,discovered=false}}")
        empty=self.lua.table_from([])
        result=self.core[b'filter'](objectives,empty,posts)
        self.assertEqual([result[i][b'kind'] for i in range(1,len(result)+1)],[b'objective',b'outpost'])
        objectives[1][b'discovered']=True
        self.assertEqual(self.core[b'filter'](objectives,empty,posts)[1][b'kind'],b'outpost')
        objectives[1][b'discovered']=False;posts[1][b'discovered']=True
        self.assertEqual(len(self.core[b'filter'](objectives,empty,posts)),2)
        posts[1][b'completed']=True
        self.assertEqual(self.core[b'filter'](objectives,empty,posts)[1][b'kind'],b'objective')

    def test_native_classification_metadata(self):
        rows,identity=self.core[b'snapshot'](self.fixture(),0)
        oh=bytearray(112);struct.pack_into('<I',oh,36,2);struct.pack_into('<Q',oh,96,0x70000)
        mh=bytearray(112);struct.pack_into('<I',mh,12,2);struct.pack_into('<Q',mh,56,0x80000);struct.pack_into('<Q',mh,80,0xc0000)
        settings=bytearray(2080)
        # Empty hash slots must not accidentally become eligible records.
        for i in range(52):struct.pack_into('<I',settings,i*16+8,0xffffffff)
        resource=b'credits!';settings[:8]=resource;struct.pack_into('<I',settings,8,0)
        struct.pack_into('<ff',settings,832+24,32,32);settings[832+40]=1
        memory={0x3326da0:struct.pack('<Q',0x20000),0x20000:bytes(oh),
            0x3326590:struct.pack('<Q',0x10000),0x10000:bytes(mh),
            0x80000:struct.pack('<QQ',0x90000,0x90008),0x90000:resource,0x90008:b'notapoi!',
            0x346bf98:struct.pack('<Q',0xa0000),0xa0000+0xf128c8:struct.pack('<Q',0xb0000),
            0xb0000:bytes(settings),0xc0000:bytes(48),0x70000+0x1038:struct.pack('<I',3),
            0x70000+0x1078+0x1038:struct.pack('<I',0)}
        read=self.lua.eval(b'function(f)return function(...)return f(...)end end')(lambda a,n:memory.get(a))
        classified=self.core[b'classify'](read,0,rows,identity)
        self.assertTrue(classified[1][b'small_poi']);self.assertFalse(classified[2][b'small_poi'])
        self.assertEqual(classified[3][b'importance'],3);self.assertEqual(classified[4][b'importance'],0)
        # Live registry tables may be four-byte aligned, unlike most managers.
        memory[0xa0000+0xf128c8]=struct.pack('<Q',0xb0004)
        memory[0xb0004]=memory[0xb0000]
        self.core[b'classify'](read,0,rows,identity)

        # Runtime managers retain empty entity slots: never reject the entire list.
        memory[0x80000]=struct.pack('<QQ',0x90000,0)
        classified=self.core[b'classify'](read,0,rows,identity)
        self.assertFalse(classified[2][b'small_poi'])
        # A POI registry failure must preserve independently classified side tasks.
        memory[0x346bf98]=struct.pack('<Q',0)
        original_snapshot=self.core[b'snapshot']
        original_outposts=self.core[b'outposts']
        self.core[b'snapshot']=self.lua.eval(b'function(rows,id)return function()return rows,id end end')(rows,identity)
        self.core[b'outposts']=self.lua.eval(b'function()return {} end')
        filtered,error=self.core[b'mission_rows'](read,0,self.lua.table_from([]))
        self.assertEqual(len(filtered),1)
        self.assertEqual(filtered[1][b'kind'],b'objective')
        self.assertEqual(error,b'')
        self.core[b'snapshot']=original_snapshot;self.core[b'outposts']=original_outposts

    def test_side_discovery_and_outpost_clear_rules_are_independent(self):
        rows=self.lua.execute(b"return {{kind='objective',importance=3,x=0,y=0,discovered=true},{kind='objective',importance=3,x=1,y=1,completed=true},{kind='marker',small_poi=true,x=100,y=100,discovered=true}}")
        credits=self.lua.execute(b'return {{x=102,y=101}}')
        posts=self.lua.execute(b"return {{kind='outpost',x=200,y=200,discovered=true},{kind='outpost',x=300,y=300},{kind='outpost',x=400,y=400,completed=true}}")
        result=self.core[b'filter'](rows,credits,posts)
        self.assertEqual(len(result),4)
        self.assertEqual(result[1][b'x'],1)
        self.assertEqual(result[2][b'x'],102)
        self.assertEqual(result[3][b'x'],200)
        self.assertEqual(result[4][b'x'],300)
    def test_polygon_glyphs_bounded_and_distinct(self):
        glyphs=[]
        for kind in [b'objective',b'outpost',b'credit_poi',b'black_box',b'medal']:
            parts=self.core[b'glyph'](kind,24,2,1)
            result=[[parts[i][j] for j in range(1,5)] for i in range(1,len(parts)+1)]
            self.assertTrue(result)
            for x,y,w,h in result:
                self.assertGreaterEqual(w,0);self.assertGreaterEqual(x,-12)
                self.assertLessEqual(x+w,12.001);self.assertLessEqual(y+h,12)
                if kind==b'black_box':
                    self.assertFalse(x<0<x+w and y<0<y+h)
            glyphs.append(result)
        for i,glyph in enumerate(glyphs):
            for other in glyphs[i+1:]:self.assertNotEqual(glyph,other)
    def test_overlay_runs_after_original_and_preserves_nil_results(self):
        previous,after,log=self.lua.execute(b"local log={} return function(a,b)log[#log+1]='game';assert(a==4 and b==nil);return 1,nil,3,nil end,function()log[#log+1]='overlay' end,log")
        result=self.core[b'after_update'](previous,after,4,None)
        self.assertEqual(result,(1,None,3,None))
        self.assertEqual(list(log.values()),[b'game',b'overlay'])
        layers=self.core[b'layers']
        self.assertGreater(layers[b'outline'],103)
        self.assertGreater(layers[b'symbol'],layers[b'outline'])
    def test_native_objective_reveal_enum(self):
        for value in (0,1,2,9):
            rows,_=self.core[b'snapshot'](self.fixture(reveal_states=(value,value)),0)
            self.assertEqual(rows[3][b'discovered'],value==0)
            self.assertEqual(rows[3][b'reveal_state'],value)
    def test_last_rendered_world_selected_only_while_alive(self):
        worlds=self.lua.table_from([1,2,3])
        self.assertEqual(self.core[b'choose_world'](worlds,1,3),3)
        self.assertEqual(self.core[b'choose_world'](worlds,1,1),1)
        self.assertEqual(self.core[b'choose_world'](worlds,1,4),2)
    def map_fixture(self,opened=True,modal=False,nan=False,race=False):
        owner=0x100000;hud=owner+0x24e340;address=hud+0x1a0e28
        memory={0x346d538:struct.pack('<Q',owner),hud+0x58:b'\1',hud+0x21f5b0:b'\1',
                0x3326340:struct.pack('<Q',0x200000),0x200000+0xac21c:struct.pack('<I',4),
                0x347ce28:struct.pack('<Q',0x300000),0x300000+0x4294:struct.pack('<II',int(modal),0)}
        head=bytearray(0xc8)
        for at,v in [(0,100),(4,200),(0x10,10),(0x14,-20),(0x28,2),(0x9c,800),(0xa0,500),(0xa4,200)]:
            struct.pack_into('<f',head,at,float('nan') if nan and at==0x28 else v)
        struct.pack_into('<I',head,0x70,400);head[0x74]=1;head[0x75]=int(opened)
        memory[address+0x120]=bytes(head)
        matrix=bytearray(0xa0)
        # Parent matrix origin is the lower-left; native markers anchor at
        # the map center. Keep these different to expose the 0.2.0 regression.
        for at,v in [(0x64,1.5),(0x84,0),(0x6c,0),(0x8c,1.5),(0x94,600),(0x9c,300)]:struct.pack_into('<f',matrix,at,v)
        memory[address+0x4bf50]=bytes(matrix)
        calls={}
        def read(at,n):
            calls[at]=calls.get(at,0)+1
            if race and at==0x346d538 and calls[at]>1:return struct.pack('<Q',owner+8)
            blob=memory.get(at);return blob[:n] if blob and len(blob)>=n else None
        return self.lua.eval(b'function(f)return function(...)return f(...)end end')(read)
    def test_native_close_and_modal_hide(self):
        for fixture in [self.map_fixture(opened=False),self.map_fixture(modal=True)]:
            self.assertIsNone(self.core[b'map_view'](fixture,0,1920,1080))
    def test_native_projection_pan_scale_and_clip(self):
        view=self.core[b'map_view'](self.map_fixture(),0,1920,1080)
        rows=self.lua.table_from([self.lua.table_from({b'x':100,b'y':200,b'kind':b'marker'}),
                                  self.lua.table_from({b'x':1000,b'y':200,b'kind':b'objective'})])
        result=self.core[b'map_project'](rows,view)
        self.assertEqual(len(result),1)
        self.assertEqual(result[1][b'x'],830);self.assertEqual(result[1][b'y'],440)
    def test_circular_boundary_rejects_square_corners(self):
        view=self.core[b'map_view'](self.map_fixture(),0,1920,1080)
        # Projection becomes (950,650), inside the old square but outside
        # the circular minimap once the complete marker border is included.
        rows=self.lua.table_from([self.lua.table_from({b'x':140,b'y':270,b'kind':b'marker'})])
        self.assertEqual(len(self.core[b'map_project'](rows,view)),0)
    def test_marker_size_scales_with_resolution(self):
        view=self.core[b'map_view'](self.map_fixture(),0,3840,2160)
        rows=self.lua.table_from([self.lua.table_from({b'x':90,b'y':220,b'kind':b'marker'}),
                                  self.lua.table_from({b'x':90,b'y':220,b'kind':b'objective'})])
        result=self.core[b'map_project'](rows,view)
        self.assertEqual(result[1][b'size'],32)
        self.assertEqual(result[2][b'size'],44)
    def test_only_success_state_marks_objective_completed(self):
        for value in [0,1,2,3,99]:
            rows,_=self.core[b'snapshot'](self.fixture(objective_states=(value,value)),0)
            self.assertFalse(rows[1][b'completed'])
            self.assertEqual(rows[3][b'completed'],value==2)
            self.assertEqual(rows[3][b'objective_state'],value)
    def test_completion_changes_color_and_draw_key_without_moving(self):
        view=self.core[b'map_view'](self.map_fixture(),0,1920,1080)
        row=self.lua.table_from({b'x':90,b'y':220,b'kind':b'objective',b'completed':False})
        rows=self.lua.table_from([row])
        before=self.core[b'map_project'](rows,view)
        key=self.core[b'draw_key'](before)
        amber=self.core[b'marker_color'](before[1])
        self.assertEqual(amber[2],255);self.assertEqual(amber[3],255)
        row[b'completed']=True
        after=self.core[b'map_project'](rows,view)
        self.assertEqual(after[1][b'x'],before[1][b'x'])
        self.assertEqual(after[1][b'y'],before[1][b'y'])
        self.assertNotEqual(key,self.core[b'draw_key'](after))
        gray=self.core[b'marker_color'](after[1])
        self.assertEqual(list(gray.values()),[255,255,255,255])
    def test_native_bad_transform_and_scene_race(self):
        for fixture in [self.map_fixture(nan=True),self.map_fixture(race=True)]:
            with self.assertRaises(Exception):self.core[b'map_view'](fixture,0,1920,1080)
if __name__=='__main__':unittest.main(verbosity=2)
