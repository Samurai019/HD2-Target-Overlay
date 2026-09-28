import struct,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
import test_overlay

class HudCurveTests(unittest.TestCase):
    def setUp(self):
        self.fixture=test_overlay.OverlayTests();self.fixture.setUp()
        self.lua=self.fixture.lua;self.core=self.fixture.core

    def view(self,amount):
        original=self.fixture.map_fixture()
        value=None if amount is None else struct.pack('<f',amount)
        reader=self.lua.eval(b'function(read,value)return function(a,n) if a==0x200000+0xac4dc then return value end return read(a,n) end end')(original,value)
        return self.core[b'map_view'](reader,0,1920,1080)

    def test_live_setting_zero_and_invalid_fallback(self):
        for amount in (0,.5,1):
            view=self.view(amount)
            self.assertEqual(view[b'hud_curve'],amount)
            self.assertIsNone(view[b'curve_error'])
        for amount in (None,-1,2,float('nan')):
            view=self.view(amount)
            self.assertEqual(view[b'hud_curve'],0)
            self.assertIsNotNone(view[b'curve_error'])

    def test_disabled_projection_is_unchanged_and_enable_updates_without_reload(self):
        row=self.lua.table_from([self.lua.table_from({b'x':100,b'y':200,b'kind':b'outpost'})])
        flat=self.core[b'map_project'](row,self.view(0))[1]
        self.assertEqual((flat[b'x'],flat[b'y']),(830,440))
        curved=self.core[b'map_project'](row,self.view(1))[1]
        self.assertEqual(curved[b'x'],flat[b'x'])
        self.assertGreater(curved[b'y'],flat[b'y'])
        restored=self.core[b'map_project'](row,self.view(0))[1]
        self.assertEqual((restored[b'x'],restored[b'y']),(flat[b'x'],flat[b'y']))

    def test_edges_contract_toward_screen_center_and_round_trip(self):
        view=self.lua.table_from({b'hud_curve':1,b'width':3840,b'height':2160})
        for x,y in [(3344,528),(3062,337),(3505,399),(3840,200),(0,200),(1920,200),(3344,1700)]:
            wx,wy=self.core[b'hud_warp'](x,y,view)
            self.assertEqual(wx,x)
            self.assertLessEqual(abs(wy-1080),abs(y-1080))
            rx,ry=self.core[b'hud_warp'](wx,wy,view,True)
            self.assertAlmostEqual(rx,x);self.assertAlmostEqual(ry,y)
        self.assertEqual(self.core[b'hud_warp'](0,200,view),(0,200))
        self.assertEqual(self.core[b'hud_warp'](3840,200,view),(3840,200))
        self.assertEqual(self.core[b'hud_warp'](1920,200,view),(1920,332))
        # Lower points need more upward correction at the same horizontal position.
        low=self.core[b'hud_warp'](3344,100,view)[1]-100
        high=self.core[b'hud_warp'](3344,700,view)[1]-700
        self.assertGreater(low,high)

    def test_measured_native_icons_at_half_and_full_curvature(self):
        import json
        data=json.loads((Path(__file__).resolve().parents[1]/'research/hud-curve-image-points.json').read_text())
        baseline=data['relative_points'][0]
        mx,my=data['logical_map_center']
        for sample,amount in enumerate(data['curves'][1:],1):
            view=self.lua.table_from({b'hud_curve':amount,b'width':data['width'],b'height':data['height']})
            for flat,observed in zip(baseline,data['relative_points'][sample]):
                x,y=mx+flat[0],my-flat[1]
                wx,wy=self.core[b'hud_warp'](x,y,view)
                # Native artwork centroid can change slightly as it deforms;
                # the measured vertical displacement is within half a pixel.
                expected_y=my-observed[1]
                self.assertLess(abs(wy-expected_y),.5)
                self.assertEqual(wx,x)

    def test_curved_clipping_checks_actual_symbol_corners(self):
        view=self.view(1)
        rows=self.lua.table_from([self.lua.table_from({b'x':x,b'y':y,b'kind':b'outpost'})
                                for x in range(30,170,10) for y in range(130,280,10)])
        result=self.core[b'map_project'](rows,view)
        self.assertGreater(len(result),0)
        for p in result.values():
            half=p[b'size']/2+4*view[b'icon_scale']
            for sx in (-1,1):
                for sy in (-1,1):
                    x,y=self.core[b'hud_warp'](p[b'x']+sx*half,p[b'y']+sy*half,view,True)
                    self.assertLessEqual((x-view[b'cx'])**2+(y-view[b'cy'])**2,view[b'radius']**2+.00001)

    def test_normalized_resolution_scaling_and_right_edge_correction(self):
        large=self.lua.table_from({b'hud_curve':1,b'width':3840,b'height':2160})
        small=self.lua.table_from({b'hud_curve':1,b'width':1920,b'height':1080})
        for x,y in ((3098,774),(3344,528),(3590,282)):
            a=self.core[b'hud_warp'](x,y,large)
            b=self.core[b'hud_warp'](x/2,y/2,small)
            self.assertAlmostEqual(a[0]/2,b[0]);self.assertAlmostEqual(a[1]/2,b[1])
        # The earlier x-squared model overcorrected the far right.
        left=self.core[b'hud_warp'](3098,528,large)[1]-528
        right=self.core[b'hud_warp'](3590,528,large)[1]-528
        self.assertGreater(left,right)

if __name__=='__main__':unittest.main()
