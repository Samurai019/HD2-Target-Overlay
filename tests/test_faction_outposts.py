import json,struct,sys,unittest
from pathlib import Path
from lupa.luajit21 import LuaRuntime
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from build_overlay import source_bytes

class FactionOutpostTests(unittest.TestCase):
    def setUp(self):
        self.lua=LuaRuntime(encoding=None,unpack_returned_tuples=True)
        self.lua.globals()[b'HD2OverlayTest']=True
        self.core=self.lua.execute(source_bytes())
        self.types=bytes.fromhex(json.loads((ROOT/'tests/fixtures/outpost-types-supported-build.json').read_text())['settings_hex'])
        self.records=json.loads((ROOT/'tests/fixtures/illuminate-outposts-20260929.json').read_text())['records']

    def read_fixture(self,cleared=False,discovered=False):
        head=bytearray(112);struct.pack_into('<I',head,12,len(self.records))
        struct.pack_into('<QQ',head,72,0x20000,0x30000)
        memory={0x33265c0:struct.pack('<Q',0x10000),0x10000:bytes(head),
                0x32fcde0:self.types.ljust(8192,b'\0')}
        for i,record in enumerate(self.records):
            state=bytearray.fromhex(record['network_hex'])
            if cleared:state[0x39]=1
            if discovered:state[0x3b]=1
            memory[0x20000+i*0x2b8]=bytes.fromhex(record['position_hex'])
            memory[0x30000+i*64]=bytes(state)
        return self.lua.eval(b'function(f)return function(...)return f(...)end end')(
            lambda a,n:memory[a][:n] if a in memory and len(memory[a])>=n else None)

    def test_real_illuminate_capture_keeps_six_counted_outposts(self):
        rows,error=self.core[b'outposts'](self.read_fixture(),0)
        self.assertEqual(error,b'');self.assertEqual(len(rows),11)
        self.assertEqual([row[b'category'] for row in rows.values()],[34,34,34,34,22,33,33,32,31,33,32])
        self.assertAlmostEqual(rows[1][b'x'],178.088333,places=5)
        self.assertTrue(all(not row[b'completed'] for row in rows.values()))
        empty=self.lua.table_from([])
        marked=self.core[b'filter'](empty,empty,rows)
        self.assertEqual(len(marked),6)
        self.assertEqual([row[b'index'] for row in marked.values()],list(range(5,11)))
        self.assertTrue(all(row[b'kind']==b'outpost' for row in marked.values()))

    def test_real_records_survive_discovery_and_clear_individually(self):
        empty=self.lua.table_from([])
        rows,error=self.core[b'outposts'](self.read_fixture(discovered=True),0)
        self.assertEqual(error,b'');self.assertEqual(len(self.core[b'filter'](empty,empty,rows)),6)
        rows[6][b'completed']=True
        self.assertEqual(len(self.core[b'filter'](empty,empty,rows)),5)
        rows,error=self.core[b'outposts'](self.read_fixture(cleared=True),0)
        self.assertEqual(error,b'');self.assertEqual(len(self.core[b'filter'](empty,empty,rows)),0)
        options=self.lua.table_from({b'outposts':False})
        self.assertEqual(len(self.core[b'filter'](empty,empty,rows,options)),0)

    def test_complete_type_table_and_new_record_before_terminator(self):
        types,count,raw=self.core[b'outpost_types'](self.read_fixture(),0)
        self.assertEqual(count,42);self.assertEqual(len(raw),42*32)
        self.assertEqual(types[34],self.types[34*32:35*32])
        self.types=self.types[:-32]+self.types[34*32:35*32]+b'\0'*32
        types,count,_=self.core[b'outpost_types'](self.read_fixture(),0)
        self.assertEqual(count,43);self.assertIsNotNone(types[42])

    def test_invalid_table_is_rejected(self):
        self.types=b'\0'*32
        with self.assertRaises(Exception):self.core[b'outpost_types'](self.read_fixture(),0)

    def test_real_robot_capture_keeps_seven_counted_outposts(self):
        self.records=json.loads((ROOT/'tests/fixtures/robot-outposts-20260929.json').read_text())['records']
        self.assertEqual(len(self.records),30)
        rows,error=self.core[b'outposts'](self.read_fixture(),0)
        self.assertEqual(error,b'');self.assertEqual(len(rows),12)
        self.assertEqual([row[b'category'] for row in rows.values()],[25,25,25,23,23,27,24,25,23,22,22,22])
        self.assertTrue(rows[6][b'discovered'])
        self.assertTrue(all(not row[b'completed'] for row in rows.values()))
        empty=self.lua.table_from([])
        marked=self.core[b'filter'](empty,empty,rows)
        self.assertEqual(len(marked),7)
        self.assertEqual([row[b'index'] for row in marked.values()],[7,8,9,10,16,17,18])

    def test_counting_flag_is_independent_of_type_hidden_and_spawner_count(self):
        # Same supported type: a legitimate single-spawner site is kept;
        # a multi-spawner mission-attached site is omitted by the native flag.
        self.records=self.records[:2]
        for i,r in enumerate(self.records):
            position=bytearray.fromhex(r['position_hex']);state=bytearray.fromhex(r['network_hex'])
            position[0x2a0]=1 if i==0 else 3
            position[0x2ab]=1 if i==0 else 0
            struct.pack_into('<II',state,0x1c,1 if i==0 else 10,1 if i==0 else 10)
            r['position_hex']=position.hex();r['network_hex']=state.hex()
        rows,error=self.core[b'outposts'](self.read_fixture(discovered=True),0)
        self.assertEqual(error,b'')
        empty=self.lua.table_from([]);marked=self.core[b'filter'](empty,empty,rows)
        self.assertEqual(len(marked),1);self.assertTrue(marked[1][b'native_hidden'])
        self.assertEqual(marked[1][b'index'],0)

if __name__=='__main__':unittest.main()
