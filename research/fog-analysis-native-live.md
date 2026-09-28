# 迷雾诊断报告

仅分析已有文件，不连接游戏进程。

## FOG_SUMMARY.txt

```text
Fog probe 0.2; 2026-09-27 16:43:38
screen=3840,2160
main_world=[World]
overlay_world=[World]
last_render_world=nil
lua_render_order=
columns: white=100 magenta=16381 cyan=30000; rows=world inventory index
inside=map center ladder; outside=bottom-left screen ladder; all alpha255
view.origin_x=-293.17010498046875
view.scale=0.56089746952056885
view.cx=3344
view.icon_scale=2
view.container_y=80
view.pan_y=16.7393798828125
view.cy=528
view.container_x=2896
view.xx=2
view.pan_x=-293.17010498046875
view.xy=0
view.yx=0
view.origin_y=16.739364624023438
view.yy=2
view.tx=3344
view.radius=447
view.ty=528
world.1=[World]
world.2=[World]
world.3=[World]
world.4=[World]
world.5=[World]
world.6=[World]
world.7=[World]
update_source=@mods/astla/target_overlay.lua:774
render_source=@mods/astla/target_overlay.lua:627
capture.presenter.bin=presenter+0x120 length=200
capture.container.bin=presenter+0x4bf50 length=160
capture.map_mode.bin=presenter+0x636a0 length=32
capture.fog_flags.bin=presenter+0x64660 length=32
native.spore_bitmap=kind:3 bucket:6 order:402 flags:0xc00c1053
native.spore_bitmap.material=captured256
native.spore_parent=kind:1 bucket:6 order:402 flags:0xc0045019
native.map_bitmap=kind:3 bucket:6 order:510 flags:0xc00c1053
native.map_bitmap.material=captured256
native.map_container=kind:1 bucket:6 order:403 flags:0xc0041019
```

## FOG_DRAW.txt

```text
world.1=[World] samples created
world.2=[World] samples created
world.3=[World] samples created
world.4=[World] samples created
world.5=[World] samples created
world.6=[World] samples created
world.7=[World] samples created
```

## RENDER_ORDER.txt

```text
No Lua render_world calls observed; using world inventory fallback
```

## 地图快照

- enabled=1, open=1。
- 地图比例：0.560897。
- 中心X：3344。
- 中心Y：528。
- 半径：447。

## 原生UI绘制分组

- spore_bitmap：类型3，原生分组6，组内顺序402，flags=0xc00c1053。
- spore_parent：类型1，原生分组6，组内顺序402，flags=0xc0045019。
- map_bitmap：类型3，原生分组6，组内顺序510，flags=0xc00c1053。
- map_container：类型1，原生分组6，组内顺序403，flags=0xc0041019。

分组来自原生UI字段，不等于Lua矩形的Z值。尚未获得Lua GUI与此字段的映射。
孢子材质资源已在原版构造函数确认：content/ui/shared/misc/spore_obfuscation。

## 截图判读

每行对应一个世界。三列：白色层级100，紫色16381，青色30000。地图中央与屏幕左下角是成对色块，全部不透明。

- 某行地图内外都鲜亮：该世界可以作为覆盖层候选。
- 某行只有高层级色块鲜亮：可能是图元排序问题。
- 地图外鲜亮但所有地图内色块都被染色：可能在世界GUI之后统一合成迷雾，需截图确认。
- 某行内外都不显示：该世界可能没有被渲染。创建成功不等于显示成功。

文本记录不能自动判断画面颜色。未知UI字节不会被解释成迷雾开关。
第二次按F8开启会覆盖采样。对比有迷雾和无迷雾地图时先保存各自的截图及FOG_*文件。
