import tempfile,unittest
from pathlib import Path
from lupa.luajit21 import LuaRuntime
ROOT=Path(__file__).resolve().parents[1]
class FogProbeTests(unittest.TestCase):
    def test_probe_off_sampling_lifecycle_world_limit_and_map_close(self):
        lua=LuaRuntime(encoding=None,unpack_returned_tuples=True)
        probe=lua.execute((ROOT/'src/fog_probe.lua').read_text(encoding='utf-8-sig').encode())
        api=lua.execute(b'''local stats={created=0,destroyed=0,rects=0,down=false}
            return {stats=stats,Keyboard={button_id=function()return 8 end,button=function()return stats.down end},
            Application={main_world=function()return 1 end},
            World={create_screen_gui=function(w)stats.created=stats.created+1;return w end,
                   destroy_gui=function(w,g)stats.destroyed=stats.destroyed+1 end},
            Gui={rect=function(...)stats.rects=stats.rects+1;return stats.rects end},
            Vector3=function(...)return {...}end,Vector2=function(...)return {...}end,Color=function(...)return {...}end}''')
        read=lua.eval(b"function(a,n) if n==8 then return string.char(0,0,1,0,0,0,0,0) end return string.rep(string.char(0),n) end")
        worlds=lua.table_from(list(range(1,11)))
        view=lua.table_from({b'cx':1000,b'cy':500})
        overlay=lua.table_from({b'world':2})
        with tempfile.TemporaryDirectory() as temp:
            state=probe[b'new'](api,read,0,temp.encode())
            state[b'draw'](state,worlds,view,1920,1080,overlay)
            self.assertEqual(api[b'stats'][b'created'],0)
            api[b'stats'][b'down']=True;state[b'key_tick'](state,worlds)
            state[b'draw'](state,worlds,view,1920,1080,overlay)
            self.assertEqual(api[b'stats'][b'created'],8)
            self.assertEqual(api[b'stats'][b'rects'],192)
            state[b'draw'](state,worlds,view,1920,1080,overlay)
            self.assertEqual(api[b'stats'][b'created'],8)
            self.assertTrue((Path(temp)/'FOG_SUMMARY.txt').exists())
            self.assertEqual((Path(temp)/'FOG_presenter.bin').stat().st_size,200)
            state[b'draw'](state,worlds,None,1920,1080,overlay)
            self.assertEqual(api[b'stats'][b'destroyed'],8)
            api[b'stats'][b'down']=False;state[b'key_tick'](state,worlds)
            api[b'stats'][b'down']=True;state[b'key_tick'](state,worlds)
            self.assertFalse(state[b'enabled'])
    def test_native_widget_kind_bucket_order_capture(self):
        import struct
        lua=LuaRuntime(encoding=None)
        probe=lua.execute((ROOT/'src/fog_probe.lua').read_bytes())
        api=lua.execute(b'return {Keyboard={button_id=function()return 8 end}}')
        data=bytearray(0x1160)
        struct.pack_into('<I',data,0,(6<<29)|(3<<18))
        struct.pack_into('<H',data,0xbc,271)
        read=lua.eval(b'function(f)return function(a,n)return f(a,n)end end')(lambda a,n:bytes(data) if n==0x1160 else None)
        with tempfile.TemporaryDirectory() as temp:
            state=probe[b'new'](api,read,0,temp.encode())
            lines=lua.table_from([])
            state[b'native_widgets'](state,0x100000,lines)
            self.assertEqual(len(lines),4)
            self.assertIn(b'kind:3 bucket:6 order:271',lines[1])
            self.assertEqual((Path(temp)/'FOG_spore_bitmap.bin').stat().st_size,0x1160)
    def test_matched_layout_positions_and_colors_within_screen(self):
        lua=LuaRuntime(encoding=None);probe=lua.execute((ROOT/'src/fog_probe.lua').read_text(encoding='utf-8-sig').encode())
        view=lua.table_from({b'cx':1000,b'cy':500})
        for index in range(1,9):
            row=probe[b'layout'](view,index,1920,1080)
            self.assertTrue(0<row[1]<1920 and 0<row[2]<1080)
            self.assertTrue(0<row[3]<1920 and 0<row[4]<1080)
if __name__=='__main__':unittest.main()
