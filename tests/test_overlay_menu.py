import itertools,sys,tempfile,unittest
from pathlib import Path
from lupa.luajit21 import LuaRuntime
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from build_overlay import source_bytes
MENU=ROOT/'research/ModOptionsMenu/src/mod_options_menu.lua'

class OverlayMenuTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='hd2_menu_')
        self.addCleanup(self.temp.cleanup)
        self.lua=LuaRuntime(encoding=None,unpack_returned_tuples=True)
        self.lua.globals()[b'HD2OverlayTest']=True
        self.core=self.lua.execute(source_bytes())
        self.state=self.lua.execute(b"return {options={outposts=true,objectives=true,credits=true,black_boxes=true,medals=false},rows={}}")
        self.lua.globals()[b'CowboyBingusModLoader']=self.lua.table_from({b'log_directory':self.temp.name.encode()})
        self.find=self.lua.eval(b"""function(fn,wanted)
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
            local result=visit(fn);assert(result,'missing upvalue '..wanted);return result
        end""")

    def load_menu(self):
        self.lua.globals()[b'ModOptionsMenu']=None
        self.lua.execute(MENU.read_bytes())
        return self.lua.globals()[b'ModOptionsMenu']

    def test_real_api_registration_chinese_labels_saved_values_and_apply(self):
        saved=Path(self.temp.name)/'ModOptionsMenu.values'
        saved.write_text('astla.target_overlay.outposts\tfalse\n',encoding='utf-8')
        menu=self.load_menu()
        self.core[b'menu_step'](self.state,menu)
        self.assertFalse(self.state[b'options'][b'outposts'])
        self.assertFalse(self.state[b'options'][b'medals'])
        self.assertTrue(self.state[b'options'][b'objectives'])
        self.assertIsNone(self.state[b'rows'])
        native=self.find(menu[b'register_option'],b'state')
        self.assertEqual(native[b'option_count'],5)
        for i,label in enumerate(['标记虫巢','标记支线','标记蓝币','标记黑匣子','标记勋章'],1):
            spec=self.core[b'option_specs'][i]
            self.assertEqual(native[b'options'][spec[b'id']][b'label'],label.encode())
            self.assertEqual(len(native[b'callbacks'][spec[b'id']]),1)
        for _ in range(120):self.core[b'menu_step'](self.state,menu)
        self.assertEqual(native[b'option_count'],5)
        self.assertEqual(len(native[b'callbacks'][b'astla.target_overlay.outposts']),1)
        pending=self.find(menu[b'set'],b'set_pending')
        apply=self.find(self.lua.globals()[b'update'],b'apply_pending')
        self.state[b'rows']=self.lua.table_from([])
        pending(b'astla.target_overlay.objectives',False)
        self.core[b'menu_step'](self.state,menu)
        self.assertTrue(self.state[b'options'][b'objectives'])
        self.assertIsNotNone(self.state[b'rows'])
        self.assertEqual(apply(),1)
        self.assertFalse(self.state[b'options'][b'objectives'])
        self.assertIsNone(self.state[b'rows'])
        self.assertIn('astla.target_overlay.objectives\tfalse',saved.read_text())
        pending(b'astla.target_overlay.medals',True)
        self.assertEqual(apply(),1)
        self.assertTrue(self.state[b'options'][b'medals'])
        self.assertIn('astla.target_overlay.medals\ttrue',saved.read_text())
        restarted=self.lua.execute(b"return {options={outposts=true,objectives=true,credits=true,black_boxes=true,medals=false}}")
        self.core[b'menu_step'](restarted,self.load_menu())
        self.assertFalse(restarted[b'options'][b'outposts'])
        self.assertFalse(restarted[b'options'][b'objectives'])
        self.assertTrue(restarted[b'options'][b'credits'])
        self.assertTrue(restarted[b'options'][b'medals'])

    def test_all_thirty_two_combinations_with_real_programmatic_set(self):
        menu=self.load_menu();self.core[b'menu_step'](self.state,menu)
        rows=self.lua.execute(b"return {{kind='objective',importance=3,x=11,y=22}}")
        posts=self.lua.execute(b"return {{kind='outpost',x=11,y=22}}")
        credits=self.lua.execute(b"return {{x=33,y=44}}")
        boxes=self.lua.execute(b'return {{x=55,y=66}}')
        keys=[b'outposts',b'objectives',b'credits',b'black_boxes',b'medals']
        kinds=[b'outpost',b'objective',b'credit_poi',b'black_box',b'medal']
        for values in itertools.product([False,True],repeat=5):
            for key,value in zip(keys,values):self.assertTrue(menu[b'set'](b'astla.target_overlay.'+key,value))
            self.core[b'menu_step'](self.state,menu)
            result=self.core[b'filter'](rows,credits,posts,self.state[b'options'],boxes,credits)
            self.assertEqual(sorted(result[i][b'kind'] for i in range(1,len(result)+1)),
                             sorted(kind for kind,value in zip(kinds,values) if value))

    def test_absent_incompatible_and_late_menu(self):
        for menu in (None,self.lua.table_from({b'api':2}),self.lua.table_from({b'api':1})):
            self.core[b'menu_step'](self.state,menu)
        self.assertTrue(all(self.state[b'options'][key] for key in [b'outposts',b'objectives',b'credits',b'black_boxes']))
        self.core[b'menu_step'](self.state,self.load_menu())
        self.assertEqual(len(list(self.state[b'option_links'].keys())),5)

    def test_registration_rejection_or_exception_is_bounded(self):
        for body in (b"return false,'capacity'",b"error('menu failure')"):
            menu=self.lua.execute(b"local calls=0;return {api=1,register_option=function()calls=calls+1;"+body+b" end,get=function()error('unregistered')end,on_change=function()error('unregistered')end,calls=function()return calls end}")
            for _ in range(100):self.core[b'menu_step'](self.state,menu)
            self.assertEqual(menu[b'calls'](),5)
            self.assertTrue(all(self.state[b'options'][key] for key in [b'outposts',b'objectives',b'credits',b'black_boxes']))
            self.assertIsNotNone(self.state[b'options_error'])

if __name__=='__main__':unittest.main()
