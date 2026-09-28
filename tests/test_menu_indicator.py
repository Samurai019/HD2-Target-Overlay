import sys,tempfile,unittest
from pathlib import Path
from lupa.luajit21 import LuaRuntime
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
MENU=ROOT/'research/ModOptionsMenu/src/mod_options_menu.lua'

class MenuIndicatorTests(unittest.TestCase):
    def test_new_entry_refreshes_stale_indicator_for_every_selected_index(self):
        with tempfile.TemporaryDirectory(prefix='hd2_indicator_') as folder:
            lua=LuaRuntime(encoding=None)
            lua.globals()[b'CowboyBingusModLoader']=lua.table_from({b'log_directory':folder.encode()})
            lua.execute(MENU.read_bytes())
            lua.execute(b"""
                local function upvalue(fn,wanted)
                    for i=1,100 do
                        local n,v=debug.getupvalue(fn,i);if not n then break end
                        if n==wanted then return v end
                    end
                    error('missing '..wanted)
                end
                local menu=ModOptionsMenu
                local state=upvalue(menu.set,'state')
                local apply=upvalue(menu.set,'apply_value')
                local ffi=require('ffi')
                local memory=ffi.new('uint8_t[32000]')
                local row=tonumber(ffi.cast('uintptr_t',memory))
                local current=ffi.cast('uint32_t *',memory+29068)
                local visual,calls
                state.native={set_choice=function(selector,index)
                    assert(selector==row+16016)
                    calls=calls+1
                    -- Native 17fe811..17fe824 returns without refreshing if
                    -- the selection equals the cached index.
                    if current[0]==index then return end
                    current[0]=index;visual=index
                end}
                for _,kind in ipairs({'toggle','choice'}) do
                    local count=kind=='toggle' and 2 or 4
                    local labels={};for i=1,count do labels[i]=i end
                    local choices={'LOW','HIGH','ON','OFF'}
                    for wanted=0,count-1 do
                        local option={kind=kind,labels=labels,choices=choices}
                        local value
                        if kind=='toggle' then value=wanted==1 else value=wanted+1 end
                        local entry={row=row,option=option}
                        current[0]=wanted;visual=nil;calls=0
                        apply(entry,value)
                        assert(visual==wanted,'new row has stale indicator')
                        assert(current[0]==wanted and entry.raw==wanted,'changed selection')
                        assert(calls==2,'initialization must refresh once')
                        calls=0;apply(entry,value)
                        assert(calls==1,'existing entry unnecessarily force-refreshed')
                    end
                end
                assert(state.pending_count==0 and not state.dirty,'widget refresh changed saved values')
            """)

if __name__=='__main__':unittest.main()
