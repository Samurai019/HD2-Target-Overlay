import sys, unittest, json, struct
from pathlib import Path
from lupa.luajit21 import LuaRuntime
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from build_overlay import source_bytes
from build import resource_hash

class BlackBoxTests(unittest.TestCase):
    def setUp(self):
        self.lua=LuaRuntime(encoding=None,unpack_returned_tuples=True)
        self.lua.globals()[b'HD2OverlayTest']=True
        self.core=self.lua.execute(source_bytes())

    def test_resource_identity(self):
        self.assertEqual(resource_hash('content/objectives/obj_common/black_box/black_box_01'),0x3de2415ea33b6897)
        nodes=json.loads((ROOT/'tests/fixtures/black-box-nodes-supported-build.json').read_text())['nodes']
        mesh_hash=resource_hash('black_box_01')>>32
        self.assertEqual(mesh_hash,0x3c9e8cfd)
        self.assertEqual([n['index'] for n in nodes if int(n['name_hash'],16)==mesh_hash],[2])
        self.assertNotIn('0xe4a4586d',[n['name_hash'] for n in nodes])

    def test_black_box_named_node_and_origin_rejection(self):
        api=self.lua.execute(b'''return {
            IdString64={from_hex=function(v)return v end},
            IdString32={from_hex=function(v)assert(v=='3c9e8cfd');return v end},
            World={units_by_resource=function()return {1,2,3,4,5} end},
            Unit={alive=function()return true end,
                has_node=function(u,name)return u~=5 and name=='3c9e8cfd' end,
                node=function()return 2 end,
                world_position=function(u,n)
                    if n==0 then return {0,0,10} end
                    assert(n==2)
                    if u==1 then return {125,230,10} end
                    if u==2 then return {0,0,10} end
                    if u==3 then return {.0636,-.105,10} end
                    if u==4 then return {0,80,10} end
                end},
            Vector3={x=function(p)return p[1] end,y=function(p)return p[2] end,z=function(p)return p[3] end}}
        ''')
        points=self.core[b'black_box_positions'](api,self.lua.table_from([1]),1)
        self.assertEqual(len(points),2)
        self.assertEqual(points[1][b'x'],125)
        self.assertEqual(points[2][b'y'],80)

    def native_fixture(self,resource=0x3de2415ea33b6897,revealed=0,enabled=1,carrier=0,race=False,count=1,target_index=0):
        count+=target_index
        head=bytearray(112);struct.pack_into('<I',head,12,count)
        struct.pack_into('<Q',head,56,0x20000);struct.pack_into('<Q',head,80,0x30000)
        flags=bytearray(36);struct.pack_into('<I',flags,0,carrier);flags[4]=enabled;flags[5]=revealed
        memory={0x3326d00:struct.pack('<Q',0x10000),0x10000:bytes(head),
                0x20000:struct.pack('<Q',0x40008)*target_index+struct.pack('<Q',0x40000),
                0x30000:b'\0'*36*target_index+bytes(flags),
                0x40000:struct.pack('<Q',resource),0x40008:struct.pack('<Q',0xbd6f4de16b9aedcd)}
        calls={}
        def read(address,n):
            calls[address]=calls.get(address,0)+1
            if race and address==0x10000 and calls[address]>1:return b'\0'*n
            blob=memory.get(address)
            return blob[:n] if blob is not None and len(blob)>=n else None
        wrap=self.lua.eval(b'function(f)return function(...)return f(...)end end')
        return wrap(read)

    def test_native_marker_takes_over_after_pickup_and_drop(self):
        boxes=self.lua.execute(b'return {{x=120,y=230}}')
        self.assertEqual(len(self.core[b'unmarked_black_boxes'](self.native_fixture(carrier=123),0,boxes)),1)
        for resource in [0x3de2415ea33b6897,0x8ad7a3118bd48d1c,0x4a3e722b5a865e38]:
            # Original reveal persists after dropping; read it afresh also on
            # map reopen / joining a mission where the box was already picked.
            for revealed in [1,2]:
                self.assertEqual(len(self.core[b'unmarked_black_boxes'](
                    self.native_fixture(resource=resource,revealed=revealed),0,boxes)),0)
        self.assertEqual(len(self.core[b'unmarked_black_boxes'](
            self.native_fixture(resource=0xbd6f4de16b9aedcd,revealed=1),0,boxes)),1)
        self.assertEqual(len(self.core[b'unmarked_black_boxes'](
            self.native_fixture(revealed=1,enabled=0),0,boxes)),0)
        self.assertEqual(len(self.core[b'unmarked_black_boxes'](
            self.native_fixture(revealed=1,target_index=1),0,boxes)),0)

    def test_native_marker_snapshot_race_and_bounds(self):
        for read in [self.native_fixture(race=True),self.native_fixture(count=513)]:
            with self.assertRaises(Exception):self.core[b'native_black_box_visible'](read,0)
        self.assertFalse(self.core[b'native_black_box_visible'](self.native_fixture(count=0),0))

    def test_actual_native_carry_renderer_stride_and_flags(self):
        from unicorn import Uc,UC_ARCH_X86,UC_MODE_64,UC_HOOK_CODE
        from unicorn.x86_const import UC_X86_REG_R15,UC_X86_REG_RBX,UC_X86_REG_RIP
        fixture=json.loads((ROOT/'tests/fixtures/black-box-carry-native-supported-build.json').read_text())
        code=bytes.fromhex(fixture['instructions']['0x18b0b81'])
        for enabled,revealed in [(1,0),(1,1),(0,1),(0,0)]:
            vm=Uc(UC_ARCH_X86,UC_MODE_64)
            vm.mem_map(0x18b0000,0x2000);vm.mem_write(0x18b0b81,code)
            vm.mem_map(0x10000,0x1000);vm.mem_map(0x20000,0x1000)
            vm.mem_write(0x10050,struct.pack('<Q',0x20000))
            # Index 1 distinguishes the actual 36-byte stride from old 24.
            vm.mem_write(0x20000+36+4,bytes([enabled,revealed]))
            vm.reg_write(UC_X86_REG_R15,0x10000);vm.reg_write(UC_X86_REG_RBX,1)
            stopped=[]
            def stop(vm,address,size,user):
                if address in [0x18b0a56,0x18b0b9f]:stopped.append(address);vm.emu_stop()
            vm.hook_add(UC_HOOK_CODE,stop)
            vm.emu_start(0x18b0b81,0x18b0ba0,count=20)
            self.assertEqual(stopped,[0x18b0b9f if enabled and revealed else 0x18b0a56])

if __name__=='__main__':unittest.main()
