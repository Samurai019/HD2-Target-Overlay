"""Real pinned Mod Options Menu v1.2 API; native widgets/files are fixtures."""
import hashlib
import itertools
import json
from pathlib import Path
import unittest
import test_overlay

ROOT = Path(__file__).resolve().parents[1]


class FieldSuppliesMenuTests(unittest.TestCase):
    def setUp(self):
        base = test_overlay.OverlayTests(); base.setUp()
        self.lua, self.core = base.lua, base.core
        self.lua.execute(b"os.setlocale('C')")  # Match native Lua byte character classes.
        metadata = json.loads((ROOT/'research/field-supplies-menu-fixture.json').read_text())
        source = ROOT/'research/ModOptionsMenu-v1.2/src'
        for name,digest in metadata['files'].items():
            self.assertEqual(hashlib.sha256((source/name).read_bytes()).hexdigest(),digest)
        self.create = self.lua.execute((ROOT/'tests/menu_fixture.lua').read_bytes())(
            (source/'options.lua').read_bytes(), (source/'api.lua').read_bytes(),
            (source/'bingus_text.lua').read_bytes())

    def state(self):
        return self.lua.execute(b'return {options={},rows={}}')

    def test_defaults_apply_persist_restart_and_cancel(self):
        menu, native, mom, saved = self.create(b'')
        state = self.state();self.core[b'menu_step'](state,menu)
        self.assertEqual(native[b'option_count'],10)
        for key in (b'ammo',b'grenades',b'stims'):
            self.assertTrue(state[b'options'][key])
            self.assertTrue(native[b'options'][b'astla.target_overlay.'+key][b'kind']==b'toggle')
        options = mom
        # Match the real menu's APPLY workflow; pending values must not leak.
        for key in (b'ammo',b'grenades',b'stims'):
            options[b'set_pending'](b'astla.target_overlay.'+key,False)
        self.core[b'menu_step'](state,menu)
        self.assertTrue(state[b'options'][b'ammo'])
        self.assertEqual(options[b'apply_pending'](),3)
        self.assertTrue(all(not state[b'options'][k] for k in (b'ammo',b'grenades',b'stims')))
        self.assertIsNone(state[b'rows'])
        menu2, native2, mom2, saved2 = self.create(saved())
        restored = self.state();self.core[b'menu_step'](restored,menu2)
        self.assertTrue(all(not restored[b'options'][k] for k in (b'ammo',b'grenades',b'stims')))
        mom2[b'set_pending'](b'astla.target_overlay.ammo',True)
        mom2[b'drop_pending']()
        self.core[b'menu_step'](restored,menu2)
        self.assertFalse(restored[b'options'][b'ammo'])
        self.assertEqual(saved2(),saved())

    def test_256_category_combinations_and_bounded_registration(self):
        menu,native,_,_=self.create(b'')
        state=self.state();self.core[b'menu_step'](state,menu)
        for _ in range(50):self.core[b'menu_step'](state,menu)
        self.assertEqual(native[b'option_count'],10)
        keys=[b'outposts',b'objectives',b'credits',b'black_boxes',b'medals',b'ammo',b'grenades',b'stims']
        kinds=[b'outpost',b'objective',b'credit_poi',b'black_box',b'medal',b'ammo',b'grenades',b'stims']
        rows=self.lua.execute(b'return {{kind="objective",importance=3,x=1,y=2}}')
        posts=self.lua.execute(b'return {{kind="outpost",x=3,y=4}}')
        points=self.lua.execute(b'return {{x=5,y=6}}')
        supplies=self.lua.table_from({key:points for key in (b'ammo',b'grenades',b'stims')})
        for values in itertools.product([False,True],repeat=8):
            for key,value in zip(keys,values):self.assertTrue(menu[b'set'](b'astla.target_overlay.'+key,value))
            self.core[b'menu_step'](state,menu)
            selected=self.core[b'filter'](rows,points,posts,state[b'options'],points,points,supplies)
            self.assertEqual(sorted(r[b'kind'] for r in selected.values()),sorted(k for k,v in zip(kinds,values) if v))


if __name__=='__main__':unittest.main()
