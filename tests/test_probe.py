import json
from pathlib import Path
import struct
import unittest
from lupa.luajit21 import LuaRuntime

ROOT=Path(__file__).resolve().parents[1]
SOURCE=(ROOT/'src/map_reveal_probe.lua').read_bytes()

def core(source=SOURCE):
    runtime=LuaRuntime(encoding=None,unpack_returned_tuples=True)
    runtime.globals()[b'HD2MapProbeTest']=True
    return runtime,runtime.execute(source)

class ProbeTests(unittest.TestCase):
    def run_scan(self, blocks, regions=None, excluded=None, source=SOURCE, fail=None):
        lua,mod=core(source)
        emitted=[]
        def read(address,n):
            if fail and address==fail: raise RuntimeError('unreadable')
            for base,blob in blocks:
                if base<=address and address+n<=base+len(blob):return blob[address-base:address-base+n]
            return None
        def emit(name,address,n):
            data=read(address,n)
            if data is None:return False
            emitted.append((name,address,data));return True
        wrap=lua.eval(b'function(f) return function(...) return f(...) end end')
        regs=lua.table_from([lua.table_from({b'base':a,b'size':n}) for a,n in (regions or [(a,len(b)) for a,b in blocks])])
        ex=lua.table_from([lua.table_from(x) for x in (excluded or [])])
        found,reason=mod[b'scan'](wrap(read),regs,wrap(emit),wrap(lambda:None),ex)
        return emitted,reason

    def test_real_offline_tables(self):
        a=(ROOT/'research/ShowOnMapComponentData.bin').read_bytes()
        b=(ROOT/'research/ObjectiveComponentData.bin').read_bytes()
        rows,reason=self.run_scan([(0x10000,a),(0x20000,b)])
        self.assertEqual(reason,b'found_pair')
        self.assertEqual([r[2] for r in rows],[a,b])

    def test_boundary_overlap_and_mutation(self):
        a=(ROOT/'research/ShowOnMapComponentData.bin').read_bytes()
        blob=b'x'*(262144-5)+a+b'x'*20
        rows,_=self.run_scan([(0x10000,blob)])
        self.assertEqual(len(rows),1)
        broken=SOURCE.replace(b"tail=combined:sub(-11)",b"tail='' ")
        self.assertEqual(len(self.run_scan([(0x10000,blob)],source=broken)[0]),0)

    def test_own_signature_excluded_and_mutation(self):
        a=(ROOT/'research/ShowOnMapComponentData.bin').read_bytes()
        blocks=[(0x10000,a),(0x20000,a)]
        rows,_=self.run_scan(blocks,excluded=[[0x10000,0x11000]])
        self.assertEqual(rows[0][1],0x20000)
        broken=SOURCE.replace(b'if not own then',b'if true then')
        self.assertEqual(self.run_scan(blocks,excluded=[[0x10000,0x11000]],source=broken)[0][0][1],0x10000)

    def test_region_failure_does_not_abort(self):
        a=(ROOT/'research/ShowOnMapComponentData.bin').read_bytes()
        rows,_=self.run_scan([(0x10000,a),(0x20000,a)],fail=0x10000)
        self.assertEqual(rows[0][1],0x20000)

    def test_truncated_table_not_reported(self):
        a=(ROOT/'research/ShowOnMapComponentData.bin').read_bytes()
        self.assertEqual(self.run_scan([(0x10000,a[:100])])[0],[])

    def test_bad_size_rejected(self):
        a=bytearray((ROOT/'research/ShowOnMapComponentData.bin').read_bytes())
        struct.pack_into('<I',a,12,0xffffffff)
        self.assertEqual(self.run_scan([(0x10000,bytes(a))])[0],[])

    def test_luajit_syntax_and_no_memory_write_api(self):
        lua,_=core()
        with self.assertRaises(Exception):core(SOURCE+b'\nlocal invalid = 7 // 2')
        for forbidden in [b'WriteProcessMemory',b'VirtualProtect',b'OpenProcess(',b'ffi.copy(',b'ffi.fill(']:
            self.assertNotIn(forbidden,SOURCE)

    def test_native_reader_current_process_only(self):
        # Real Windows FFI test in this test process, never attaches to the game.
        lua=LuaRuntime(encoding=None)
        result=lua.execute(b'''local f=require('ffi')
          f.cdef[[void *GetCurrentProcess(void); int ReadProcessMemory(void *,const void *,void *,size_t,size_t *);]]
          local k=f.load('kernel32'); local s=f.new('char[8]','fixture')
          local out=f.new('char[8]'); local n=f.new('size_t[1]')
          assert(k.ReadProcessMemory(k.GetCurrentProcess(),f.cast('const void *',s),out,8,n)~=0)
          assert(tonumber(n[0])==8); return f.string(out,7)''')
        self.assertEqual(result,b'fixture')

if __name__=='__main__':unittest.main(verbosity=2)
