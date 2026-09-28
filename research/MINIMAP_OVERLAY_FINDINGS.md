# Native minimap overlay binding: 1.8.46015.0

Runtime capture analyzed offline; no hooks or native calls added.

* 0x12f53a0 loads UI owner from game+0x346d538.
* 0x12f588f calls mission HUD update with owner+0x24e340.
* 0x12ec148 passes HUD+0x1a0e28 to minimap update 0x18a7c60.
* Native map constructor 0x18a55d7 sets byte +0x110=5 and +0x190=400. Overlay checks +0x190.
* Open handler 0x18ac910 sets +0x195=1 at 0x18ac952. Close handler 0x18accc0 clears it at 0x18accf3.
* Map update requires +0x194 and open/transition visibility. Overlay deliberately requires open=1, does not show closing animation markers.
* HUD update gates +0x58, +0x21f5b0 and modal owner (game+0x347ce28)+0x4294/+0x4298. Screen manager (game+0x3326340)+0xac21c must be 4.
* World projection: (world.x-map[0x120]+map[0x130])*map[0x148], likewise Y with +0x124/+0x134. See POI 0x18b86e2-0x18b8724 and objective rendering.
* POI renderer attaches children to presenter+0x4bf50 at 0x18b8b0d. Container is centered in map hierarchy (constructor 0x18b8d80). Widget screen matrix is +0x64..+0xa3. Native screen position helper 0x14523f0 returns translation +0x94/+0x9c in X/Z UI plane.
* +0x1bc/+0x1c0 is screen clip center, +0x1c4 clip extent, computed at 0x18a8263-0x18a8397. Shader normalization divides center/extent by screen size and flips vertical UV.

Overlay uses container X/Z basis and translation, then clips complete marker rectangles to center +/- extent. Alignment and GUI screen coordinate convention still need game visual validation. Tests validate data layout, pan/scale/matrix math, clipping, closed/modal visibility, NaN and root-race rejection; they cannot establish real-world UI alignment.

## 0.2.1 screenshot regression correction

User screenshot confirms the 0.2.0 points concentrate in the lower-left quadrant with some outside the circular map. The parent matrix translation was incorrectly treated as the centered marker anchor. Native marker constructors use anchor/pivot (0.5,0.5), while GUI rect positions are absolute. 0.2.1 uses the native clip center for the screen anchor and retains the parent matrix basis for zoom/scale. Entire outlined marker corners are clipped against the circle. Marker sizes scale with screen resolution. MAP_VIEW logging waits for expansion beyond 8% screen height (previous log captured a tiny opening-animation frame). Game alignment still needs visual confirmation.
