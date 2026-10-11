# Field supplies / 野外补给 — 1.4.0 local prototype

Based on upstream Target Overlay commit `db47765` (1.3.7). This change adds loaded
field ammo, grenade and stim boxes to the existing minimap overlay. It does not
alter Enemy HP HUD+, game files, discovery state, inventory or pickup behavior.

## Resource evidence

Parsed FileDiver's pinned `generated_entities.dl_bin` and `dl_library.dl_typelib`
at commit `bf0ce329db3cf0043994eb717ea86433c303cb36`. Input digests and decoded
records are in `field-supplies.json`; `inspect_field_supplies.py` reproduces them.

| Setting | Unit model / main entity | InteractType |
| --- | --- | --- |
| ammo | `79ccffd281e3f3a9` | 4 / PickupAmmo |
| grenades | `97af34fbf093409c` | 6 / PickupGrenades |
| stims | `b4ca4c5b922f7965` | 5 / PickupHealth |

All three main entities use paths under `content/fac_helldivers/discoverables/`.
Their first interaction zone is enabled, has `delete_after_interact = 1`, and
`reenable_immediately = 0`. These values come from InteractableComponent's zone
array at +8, zone stride 136, fields +45 / +101 / +100 respectively.
UnitComponent's first 8 bytes identify the model. These are distinct from
decorative crates, supply backpacks and hellpod supplies.

The position node is **StingrayEntityRoot**, thin hash `4a182741`, read from zone
+12 and independently checked against the resource-name hash. Unlike black
boxes, root node index 0 is valid. The shared locator retains finite-coordinate,
gameplay-world, deduplication and unresolved-origin checks. Supplies refuse to
query if the main world is absent, and cap enumeration at 512 units per category.

The stim model is also used by entity `02d9d0ad53ceb9df`, whose initial interaction
is disabled. Its purpose is unresolved. Model lookup intentionally marks model
presence, not current interactability. This remains an in-game validation case;
do not claim that every visible stim marker can immediately be picked up.

Primary source definitions:
- [UnitComponent](https://github.com/xypwn/filediver/blob/bf0ce329db3cf0043994eb717ea86433c303cb36/datalibrary/unit_component.go)
- [InteractableComponent](https://github.com/xypwn/filediver/blob/bf0ce329db3cf0043994eb717ea86433c303cb36/datalibrary/interactable_component.go)
- [InteractType](https://github.com/xypwn/filediver/blob/bf0ce329db3cf0043994eb717ea86433c303cb36/datalibrary/enum/interacttype.go)

## Behavior

Three independent, default-on menu settings: `astla.target_overlay.ammo`,
`.grenades`, `.stims`. Existing saved IDs/defaults remain intact. Turning a
category off avoids its model query. Settings changes invalidate the target
snapshot. Normal queries keep the existing two-second interval; categories
fail independently and stale results are cleared. A mission-table failure
does not erase independently located pickups. Destroyed or unloaded models
disappear on the next successful query. No persistent model cache is kept.

Icons: yellow ammunition, orange grenade, green cross, with the existing black
outline, glyph cache, minimap clipping, scale and HUD-curvature projection.

## Validation

97 selected tests passed using Lupa Lua 5.1 on macOS. The portable runner explicitly
uses Lua 5.1 for the compatible test subset; this is not a LuaJIT FFI run.
Coverage includes existing minimap scheduling/projection and new resource IDs,
valid root node 0, origin/NaN rejection, auxiliary-world exclusion, per-category
limits, destroyed/unloaded models, query failure/recovery, query cadence, all
256 category combinations, and real menu APPLY/save/restart/cancel semantics.

Menu API fixtures use the unmodified options.lua, api.lua and bingus_text.lua
from Mod Options Menu v1.2 commit `fd0160807b6cc75c2eeb74dbf9793a3c5d30deb6`;
`field-supplies-menu-fixture.json` pins their digests. Only filesystem/native
descriptors are fixtures. Place these files in `research/ModOptionsMenu-v1.2/src/`.
Older upstream full-menu tests require the separately extracted v1.0.1 UI-fix
archive under `research/ModOptionsMenu` and Windows FFI; they are not included
in the macOS subset. No Windows native FFI tests or in-game tests were run for
this change. No deployment occurred.

Portable validation (Python with Lupa installed):

```sh
python tests/run_field_supplies_lua51.py
python tests/run_field_supplies_lua51.py --build
```

Standard upstream LuaJIT build remains `python build_overlay.py`. The ZIP is a
single mod package with a root manifest and Addon patch, never a nested ZIP.

In-game checks still needed: each type at a known location, pickup by self and
teammate, cancelled/full-inventory interaction, unloaded/reloaded areas, scene
changes, crowded POIs, category toggles, map zoom/curvature, and the disabled
stim variant. Already-unloaded/unspawned items cannot be inferred by this path.
