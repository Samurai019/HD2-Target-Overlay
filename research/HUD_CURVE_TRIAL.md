# HUD curve trial 1.1.7

User confirmed flat HUD aligns perfectly. Do not change original map projection.

Offline module strings: hud_curve at225f4d0; hud_curve_amount at22c23c8.
12f3ca2 loads screen manager via RVA3326340. 12f3cc7 reads float at
screen manager+ac4dc; 12f3ccf multiplies it by float .15 at23c67c0.
12f3d28 writes this value into the shader parameter vector's Y component;
12f3d43 calls100a720 to set it. No live native calls or game writes introduced.

The shader formula has NOT been extracted. Trial assumes cylindrical inverse
sampling: x unchanged, y'=H/2+(y-H/2)/(1+.15*setting*(2*x/W-1)^2).
Setting0 returns original x,y exactly. Read fail/NaN/out-of-range outside0..1
falls back to flat projection and is visible in diagnostic view_curve_error.
This approximation contracts vertical distances toward screen center more at
screen sides, matching the observed growing offset near the bottom of the map.
Only marker centers move; their shapes stay undistorted. Actual rectangle corners
are mapped back to the original circle for conservative clipping.

76 tests passed; in-memory mutations disabling compensation and reversing the
warp were caught. Archive syntax and integrity checks passed. No in-game claim
of alignment has been made. Need user screenshots paired with F8 after installing
the1.1.7 diagnostic package and enabling HUD curve. Report now includes live curve.
Previous1.1.6 archives retained for rollback.

## 1.1.8 calibration workflow

User reported1.1.7 improves the bottom but overcorrects the right. Do not tune
the formula again without native display measurements. User requested an effect
test. Built a read-only diagnostic package (same GUID, replaces older overlay).
F9 hides ordinary overlay symbols and draws nine numbered fixed flat points and
a96-point flat map circle (cyan), along with1.1.7 predicted counterparts
(magenta). Native HUD remains unchanged; its existing edge/icons are references.
The mod does not inject calibration points into the native curvature pipeline.
F9 again restores normal symbols. Closed map/F7 hide the diagnostic graphics.
F8 retains independent timestamped, sequentially named captures, with live curve
and all nine raw/predicted coordinates, while preserving legacy latest-report path.

79 tests passed, including real Lua runtime toggle/draw cache/cleanup, closed map,
F7, F8 edge triggering and capture preservation. Two mutations (repeat toggle
whileheld and remove capture sequence) were caught. Calibration zip syntax and
integrity checks passed. User should stay in one place and capture full-resolution,
uncropped full-game screenshots and F8 records at curve0,.5,1 after map expansion.
Fit actual transform using native boundary and known reference coordinates before
changing the production compensation model. Latest log at build time was still
1.1.6 capture; no1.1.7 live curve value was available.
