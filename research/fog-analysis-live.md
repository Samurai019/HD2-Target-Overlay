# 迷雾诊断报告

仅分析已有文件，不连接游戏进程。

## FOG_SUMMARY.txt

```text
Fog probe 0.1; 2026-09-27 16:30:28
screen=3840,2160
main_world=[World]
overlay_world=nil
last_render_world=nil
lua_render_order=
columns: white=100 magenta=16381 cyan=30000; rows=world inventory index
inside=map center ladder; outside=bottom-left screen ladder; all alpha255
view.origin_x=-9.4704627990722656
view.scale=1.7641129493713379
view.cx=3344
view.icon_scale=2
view.container_y=80
view.pan_y=-35.977615356445312
view.cy=528
view.container_x=2896
view.xx=2
view.pan_x=-9.470458984375
view.xy=0
view.yx=0
view.origin_y=-35.977622985839844
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
update_source=@mods/astla/target_overlay.lua:744
render_source=@mods/astla/target_overlay.lua:597
capture.presenter.bin=presenter+0x120 length=200
capture.container.bin=presenter+0x4bf50 length=160
capture.map_mode.bin=presenter+0x636a0 length=32
capture.fog_flags.bin=presenter+0x64660 length=32
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
- 地图比例：1.76411。
- 中心X：3344。
- 中心Y：528。
- 半径：447。

## 截图判读

每行对应一个世界。三列：白色层级100，紫色16381，青色30000。地图中央与屏幕左下角是成对色块，全部不透明。

- 某行地图内外都鲜亮：该世界可以作为覆盖层候选。
- 某行只有高层级色块鲜亮：可能是图元排序问题。
- 地图外鲜亮但所有地图内色块都被染色：可能在世界GUI之后统一合成迷雾，需截图确认。
- 某行内外都不显示：该世界可能没有被渲染。创建成功不等于显示成功。

文本记录不能自动判断画面颜色。未知UI字节不会被解释成迷雾开关。
第二次按F8开启会覆盖采样。对比有迷雾和无迷雾地图时先保存各自的截图及FOG_*文件。

## 本次实机结论

用户确认虫巢和支线已正常，本次特殊任务没有支线，不影响独立色块诊断。

日志确认7个世界的测试GUI均创建成功，截图中可见两行屏幕外测试色块。地图外白、紫、青鲜亮，地图内部可见的三列均受迷雾染色；层级100、16381、30000未出现绕过迷雾的明显差异。结合该现象，后续地图区域合成是当前主要解释，而非单纯图元深度不足。尚未捕获GPU绘制调用，不能把该解释当成已定位到具体着色器。

Lua render_world仍未捕获调用，因此现有Lua回调无法提供真实原生合成顺序。继续增加Z值或在现有世界之间切换，没有得到可用候选。需要分析原版迷雾／地图合成材质及原生UI提交路径。

样本已保存在research/fog-case-01，避免下一次采样覆盖。
