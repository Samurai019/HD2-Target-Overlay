# HUD curve calibration 1.1.9

User supplied three1.1.8 calibration PNGs. Only the curve0 F8 report was saved:
TargetOverlay_HUD_20260929_071322_curve_0.000_1.txt. It establishes screen3840x2160,
logical map center(3344,528), radius447. Images are cropped but unscaled; the
known cyan cross5 locates each crop's origin. Cross centers are measured from
horizontal/vertical high-coverage bands, avoiding spurious individual pixels.
Curves0/.5/1 follow requested capture order and agree with magenta-vs-cyan trial
cross5 displacement (approximately0/22/42 pixels).

Native power, drop, resupply, heavy nest and light nest artwork centroids were
measured using color masks. Native positions are independent of calibration GUI.
Measured points and provenance are in hud-curve-image-points.json; reproducible
read-only image analysis is measure_hud_curve.py. Source PNGs are user attachments
in the temp directory; they are not modified or copied into the package.

Model replacing the rejected1.1.7 guess:

nx = 2*x/width - 1
factor = 1 - .15*curve*(1 - nx*nx)
x' = x
y' = height/2 + (y-height/2)*factor

Inverse divides the centered Y by factor. Valid curve0..1 keeps factor>=.85
inside the screen. Native shader strength.15 is independently identified at
12f3cc7/12f3ccf; shader source has not been extracted. This is an empirical
display model validated on sampled native icons, not a claim of full shader recovery.
The previous model used nx² and inverse sampling, overcorrecting the far right.

Maximum absolute vertical displacement residual:

| Curve | Five native icon measurements |
| --- | --- |
| .5 | .469 pixels |
| 1 | .416 pixels |

Color-centroid shifts and raster edges have subpixel uncertainty. X centroid
differences are around one pixel; production X projection remains unchanged.
Flat HUD returns x,y exactly. GUI symbol corner clipping uses the matching inverse.
Existing faction/outpost exclusion, Stalker Lair exception and completion rules
are unchanged.81 tests pass, including measured-icon regression, flat restore,
roundtrip inverse, resolution scaling and curved clipping. Mutations changing
the complementary nx factor or forward/inverse multiplication were caught by
the independent measured-icon test. All three archives passed Lua syntax/content
and ZIP integrity checks. Updated build's visual result still needs user confirmation.

## Formal release confirmation

User confirmed1.1.9 in-game test completed without issues and requested the formal release. Formula unchanged. Formal build sets OUTPOST_DIAGNOSTIC=false; F8/F9 are ignored and no diagnostic files are written. Installation documentation was simplified to current behavior.
