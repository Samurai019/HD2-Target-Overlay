import sys,json,hashlib,re
from pathlib import Path
import unittest
from lupa.luajit21 import LuaRuntime
from unicorn import Uc,UC_ARCH_X86,UC_MODE_64,UC_HOOK_MEM_WRITE
from unicorn.x86_const import *
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from build_render import source_bytes

class RenderTests(unittest.TestCase):
    def setup_core(self,fail_at=None,corrupt=None,backup_fail=False):
        lua=LuaRuntime(encoding=None,unpack_returned_tuples=True)
        lua.globals()[b'HD2MapIconsTest']=True
        core=lua.execute(source_bytes())
        rows=json.loads((ROOT/'research/render-patches.json').read_text())
        memory={s['rva']:bytearray.fromhex(s['original']) for s in rows}
        if corrupt is not None:memory[rows[corrupt]['rva']][0]^=1
        writes=[]; backed=[]
        def read(addr,n):
            for a,b in memory.items():
                if a<=addr and addr+n<=a+len(b):return bytes(b[addr-a:addr-a+n])
        def write(addr,data):
            self.assertEqual(len(data),1)
            self.assertTrue(backed)
            if fail_at is not None and len(writes)==fail_at:
                writes.append(('fail',addr));raise RuntimeError('simulated write failure')
            for a,b in memory.items():
                if a<=addr<a+len(b):b[addr-a]=data[0];writes.append((addr,data));return
            raise AssertionError('unexpected write address')
        def backup(text):
            if backup_fail:raise RuntimeError('disk full')
            backed.append(text)
        wrap=lua.eval(b'function(f)return function(...)return f(...)end end')
        api=lua.table_from({b'read':wrap(read),b'write':wrap(write),b'backup':wrap(backup)})
        return core,api,memory,writes,rows

    def test_exact_five_byte_change_and_idempotence(self):
        core,api,mem,writes,rows=self.setup_core()
        self.assertEqual(core[b'apply'](api,0),5)
        for s in rows:
            old=bytes.fromhex(s['original']);new=bytes(mem[s['rva']])
            self.assertEqual([i for i,(a,b) in enumerate(zip(old,new)) if a!=b],[s['offset']])
        self.assertEqual(core[b'apply'](api,0),0)
        self.assertEqual(len(writes),5)

    def test_mismatch_any_site_means_no_writes(self):
        for i in range(5):
            core,api,mem,writes,rows=self.setup_core(corrupt=i)
            with self.assertRaises(Exception):core[b'apply'](api,0)
            self.assertEqual(writes,[])

    def test_backup_failure_means_no_writes(self):
        core,api,mem,writes,rows=self.setup_core(backup_fail=True)
        with self.assertRaises(Exception):core[b'apply'](api,0)
        self.assertEqual(writes,[])

    def test_partial_failure_rolls_back(self):
        core,api,mem,writes,rows=self.setup_core(fail_at=2)
        with self.assertRaises(Exception):core[b'apply'](api,0)
        for s in rows:self.assertEqual(bytes(mem[s['rva']]),bytes.fromhex(s['original']))

    def test_actual_x64_comparisons_never_write_state(self):
        rows=json.loads((ROOT/'research/render-patches.json').read_text())
        for s in rows:
            instruction=bytes.fromhex(s['original'])[8:s['offset']+1]
            for value in [0,1,2,3]:
                for patch in [False,True]:
                    uc=Uc(UC_ARCH_X86,UC_MODE_64);uc.mem_map(0x1000,4096);uc.mem_map(0x4000,4096)
                    # Set effective address of each real comparison to data+field.
                    for reg in [UC_X86_REG_RAX,UC_X86_REG_RCX,UC_X86_REG_RDX,UC_X86_REG_R8,UC_X86_REG_RDI,UC_X86_REG_RBX,UC_X86_REG_R15]:uc.reg_write(reg,0)
                    if s['name']=='poi_visible':uc.reg_write(UC_X86_REG_R15,0x4000);field=0
                    elif s['name'].startswith('poi_'):uc.reg_write(UC_X86_REG_RBX,0x4000);field=0
                    elif s['name']=='objective_icon_path':uc.reg_write(UC_X86_REG_RDX,0x4000);field=0x44
                    else:uc.reg_write(UC_X86_REG_RCX,0x4000);field=0x40
                    uc.mem_write(0x4000+field,value.to_bytes(4,'little'))
                    code=instruction[:-1]+b'\xff' if patch else instruction
                    uc.mem_write(0x1000,code)
                    written=[];uc.hook_add(UC_HOOK_MEM_WRITE,lambda *args:written.append(args))
                    before=bytes(uc.mem_read(0x4000,256));uc.emu_start(0x1000,0x1000+len(code),count=1)
                    zf=(uc.reg_read(UC_X86_REG_EFLAGS)>>6)&1
                    self.assertEqual(zf,0 if patch else int(value==instruction[-1]))
                    self.assertEqual(written,[]);self.assertEqual(bytes(uc.mem_read(0x4000,256)),before)

    def test_windows_sha256_implementation(self):
        lua=LuaRuntime(encoding=None)
        template=(ROOT/'src/map_icons_runtime.lua').read_bytes()
        cdefs=re.search(rb'ffi.cdef\[\[(.*?)\]\]',template,re.S)[1]
        function=template[template.index(b'local function hash_file'):template.index(b'local function filename')].replace(b'coroutine.yield()',b'')
        program=b"local ffi=require('ffi');ffi.cdef[["+cdefs+b"]]; local crypto=ffi.load('advapi32');\n"+function+b'\nreturn hash_file(...)'
        path=ROOT/'src/map_icons_runtime.lua'
        got=lua.execute(program,str(path).encode())
        self.assertEqual(got.decode(),hashlib.sha256(path.read_bytes()).hexdigest().upper())

if __name__=='__main__':unittest.main(verbosity=2)
