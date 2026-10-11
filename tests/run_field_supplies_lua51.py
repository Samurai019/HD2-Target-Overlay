"""Portable Lua 5.1 validation/build; deliberately excludes LuaJIT/Windows FFI.

The existing upstream tests import lupa.luajit21. This runner supplies the
compatible Lua 5.1 implementation only for the explicitly selected pure-Lua
tests. It does not claim to exercise FFI or JIT behavior.
"""
import argparse
import locale
from pathlib import Path
import runpy
import sys
import unittest
from lupa import lua51

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'tests')]
sys.modules['lupa.luajit21'] = lua51
locale.setlocale(locale.LC_ALL, 'C')

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--build', action='store_true')
parser.add_argument('--evidence', action='store_true')
args = parser.parse_args()
print('Runtime: Lua 5.1 (Lupa); Windows FFI/JIT not exercised.', flush=True)
if args.build or args.evidence:
    runpy.run_path(str(ROOT/('research/inspect_field_supplies.py' if args.evidence else 'build_overlay.py')),
                   run_name='__main__')
else:
    modules = ['test_overlay', 'test_medal', 'test_black_box', 'test_hud_curve',
               'test_stalker_lair', 'test_overlay_performance', 'test_overlay_scheduling',
               'test_release_runtime', 'test_faction_outposts', 'test_field_supplies',
               'test_field_supplies_menu']

    def leaves(suite):
        for test in suite:
            if isinstance(test, unittest.TestSuite):
                yield from leaves(test)
            else:
                yield test

    suite = unittest.defaultTestLoader.loadTestsFromNames(modules)
    # Separate unchanged native-x86 test needs Unicorn, not the Lua locator.
    selected = unittest.TestSuite(test for test in leaves(suite)
                                 if not test.id().endswith('test_actual_native_carry_renderer_stride_and_flags'))
    result = unittest.TextTestRunner(verbosity=2).run(selected)
    sys.exit(not result.wasSuccessful())
