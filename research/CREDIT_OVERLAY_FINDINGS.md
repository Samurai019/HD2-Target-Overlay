# Target Overlay 0.3.0 evidence

Build1.8.46015.0. Plain datalibrary parsed by filediver/cmd/overlay-info: ExplorationRewardType3 (CreditCard) on entities818603ed54533506 and bd6f4de16b9aedcd, both Unit components resource bd6f4de16b9aedcd. Both destroy after interaction. Lua query signatures and loading behavior require live verification.

Objective manager3326da0: cache+60 stride1078 importance1038. Enum0Primary1Prerequisite2Optional3Tactical. Keep2/3. Completion network state+20==2.

ShowOnMap manager3326590: entity handle array+38. Entity first8 component lookup key. Native4fef10 reads global346bf98 owner+f128c8. Table2080bytes:52 hash slots16bytes, index+8;26 records48bytes at340. Discovery-location+28, world-size+20, icon sizes18/1c (hex). Component settings are separate from actual discovery state.

Outpost render18b68a0 uses global33265c0 count+c, cache+48 stride2b8, XYZ at0. Network+50 stride40. Discovery+3b ignored. Flag+39 selects cleared gray at18b7570, gray literal23c9aa0 floats(0.6,0.4,0.4,0.4). MapMarkerType10..21 are four sizes each of Bug, Bot, Illuminate outposts.

Nearest small POI within35m, runner-up distance gap>=5m; experimental thresholds. No persistent credit cache. Resource API failure suppresses only blue POIs and logs diagnostics.

## 0.4.0 live correction and discovery rules
Live DIAGNOSTIC: POI component table address ended in54c. This is valid4-byte alignment; requiring8-byte alignment rejected the table. Pointer check now allows4. Component record glyph sizes restricted32. Query detected3credit models but no POI classification in0.3.1, so screenshot cyan markers were outpost-manager rows, not confirmed credit marks.
Native outpost renderer skips type settings byte+c when nonzero (18b6b67); apply this per cached type+2a0 using static settings32fcde0 stride32, bounded types0..20. Tactical importance3 selected, Optional2 omitted to exclude optional discovery sites; requires live classification confirmation.
Discovery: objective coordinate/network byte40 used at18b5062; ShowOnMap network24-byte record firstbyte controlsvisibility at18b87ab; outpostnetworkbyte3b controls native placeholder at18b6c27. Read-only. Completed state no longer used for marker visibility/color.
Credits nearest eligible POI<=25m, runner-up gap>=8m, reject discovered matched POI. Draw actual modelXY rather than POIcenter. Raster polygon rings use established Gui.rect API and cleanup path.

## 0.4.2
Objective network+44==1 selects unknown-location widget branch at18b46c2/18b46eb; secondary objective aggregate at18b558f checks equality0 to reveal. Earlier +40 check was insufficient. Use reveal enum0 for discovered, leave1/2/unknown visible rather than treating unknown as discovered. Outpost+3b unchanged.
0.4.1 layer16380/16381 unsuccessful in live fog screenshot. Track Lua render_world order during globalrender; choose last observed liveworld for ownGUI nextupdate. No additional render_world calls, no changes to native HUD. Fallback retained and logged if no calls observed. Live verification needed.
