# 1.1.6 Stalker Lair exception and pending alignment capture

User confirmed 1.1.5 successfully excludes non-outpost holes. Preserve the
outpost cache +0x2ab eligibility gate.

ObjectiveComponentData entity 84 in entity-names.json:
`content/objectives/obj_bugs/entities/bug_destroy_stalker_lair/bug_destroy_stalker_lair`.
Its resource hash is b51d693ef3b1f3a9, independently recomputed with build.resource_hash.
Compare little-endian bytes a9f3b1f33e691db5, never a Lua numeric uint64.
Native objective renderer at 18b44b5/18b44c4 reads manager +0x50 entity handles;
18b44ed reads the first eight bytes for the component lookup key.

The exception creates a red outpost-style marker at the objective's coordinate
while importance==3 and success state !=2. Discovery only removes the white
marker. This marks the task location; it does not separately enumerate its
1–3 holes. Missing entity handles preserve ordinary side-objective classification.
Scene failure clears partial special classifications in mission_rows.

71 tests passed. Three in-memory source mutations were caught: disable exact
resource recognition, remove completion gate, remove ordinary counted-outpost
gate. Normal and diagnostic archives compiled and passed archive integrity checks.
Game verification of this exception remains pending.

Alignment remains unresolved; projection was deliberately unchanged. Screenshot
offset alone cannot distinguish coordinate differences from UI transform errors.
Native outposts attach to presenter+4ece8; POIs to +4bf50; unknown/discovered
objective containers are +f838/+14870. These containers share a constructor
parent but their actual runtime transforms have not been captured.
Native outpost widget array starts +4ee00, stride160, capacity32 (18b7775),
distinct from the outpost manager's native rendering iteration cap48.
14476a0 stores local position at widget+4/+8. Screen transform is +64..+a3;
144f160 writes +2c/+30 and 144f0d0 writes +3c/+40 anchor/pivot parameters.
Do not infer screen center from matrix translation alone without layout data.

Diagnostic F8 now records objective resource identities and states, view parameters
and resolution, raw110-byte containers and raw160-byte outpost widgets (max32).
Next step: user installs 1.1.6 diagnostic, discovers a visibly offset target,
opens the map fully and presses F8, retaining a matching screenshot. Read the
existing TargetOverlay_OUTPOST_DIAGNOSTIC.txt through the normal log workflow.
Derive a correction from native local coordinates and transforms before editing
projection. No external process reads or live native calls are needed.

## F8 capture 2026-09-29 06:38:55

Saved exact report in tests/fixtures/alignment-1.1.6-capture.txt. Back buffer
3840x2160; clip center (3344,528), radius447; all four containers have size
(448,448), screen origin(2896,80), X/Z scale2, centered anchor(3344,528).
Six initialized native outpost widgets match Core.map_project at their computed
geometric centers within .001 pixels. Widget2 (outpost record7) projects to
(3062.3515,337.2210), with native center(3062.3516,337.2210).
test_alignment_capture.py preserves this evidence and passes.

User cropped image nevertheless shows the red hex below the yellow artwork by
roughly50–60 pixels. Need a full-screen image paired with F8 to compare the actual
map circle and overlay positions against the recorded absolute coordinates;
crop removes screen origin and prevents distinguishing final GUI viewport mapping
from artwork placement. Do not shift world coordinates or claim fixed alignment.
No projection or packaged code changes were made during this capture review.
This mission's seven objective resource identities contain no Stalker Lair hash;
the capture does not verify that exception in-game.

Primary engine documentation consulted: Autodesk Stingray Gui (screen GUI origin
is viewport bottom-left; Gui.resolution() without viewport returns back-buffer
resolution), World.create_screen_gui, Viewport.set_rect. HD2 fork behavior still
requires verification; do not assume a guessed viewport correction factor.
https://help.autodesk.com/cloudhelp/ENU/Stingray-Help/lua_ref/obj_stingray_Gui.html
