# 迷雾诊断报告

仅分析已有文件，不连接游戏进程。

## FOG_SUMMARY.txt

```text
Fog probe 0.3; 2026-09-27 16:50:50
screen=3840,2160
main_world=[World]
overlay_world=[World]
last_render_world=nil
lua_render_order=
columns: -16381,0,100,401,403,16381; colors repeat white,magenta,cyan; rows=world index
inside=map center ladder; outside=bottom-left screen ladder; all alpha255
view.origin_x=290.65008544921875
view.scale=0.56089746952056885
view.cx=3344
view.icon_scale=2
view.container_y=80
view.pan_y=-71.033203125
view.cy=528
view.container_x=2896
view.xx=2
view.pan_x=290.65008544921875
view.xy=0
view.yx=0
view.origin_y=-71.033203125
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
update_source=@mods/astla/target_overlay.lua:799
render_source=@mods/astla/target_overlay.lua:652
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
backend.rect.address=0x7ff75feaf2d0
backend.bitmap_create.address=0x7ff75feaf820
backend.bitmap_update.address=0x7ff75feaf9e0
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

## 后端 rect（最多80条指令）

```text
7ff75feaf2d0 mov rax, rsp
7ff75feaf2d3 push rbx
7ff75feaf2d4 sub rsp, 0x90
7ff75feaf2db mov dword ptr [rax - 0x6c], 0x42c80000
7ff75feaf2e2 mov rbx, rcx
7ff75feaf2e5 mov dword ptr [rax - 0x68], 0x42c80000
7ff75feaf2ec mov dword ptr [rax - 0x60], 0xffffffff
7ff75feaf2f3 mov qword ptr [rax - 0x5c], 0
7ff75feaf2fb mov qword ptr [rax - 0x54], 0
7ff75feaf303 movups xmm0, xmmword ptr [rdx]
7ff75feaf306 movups xmm1, xmmword ptr [rdx + 0x10]
7ff75feaf30a movups xmmword ptr [rax - 0x4c], xmm0
7ff75feaf30e movups xmm0, xmmword ptr [rdx + 0x20]
7ff75feaf312 movups xmmword ptr [rax - 0x3c], xmm1
7ff75feaf316 movups xmm1, xmmword ptr [rdx + 0x30]
7ff75feaf31a movups xmmword ptr [rax - 0x2c], xmm0
7ff75feaf31e movups xmmword ptr [rax - 0x1c], xmm1
7ff75feaf322 test r8, r8
7ff75feaf325 je 0x7ff75feaf349
7ff75feaf327 movss xmm0, dword ptr [r8]
7ff75feaf32c movss xmm1, dword ptr [r8 + 4]
7ff75feaf332 movss dword ptr [rax - 0x78], xmm0
7ff75feaf337 movss xmm0, dword ptr [r8 + 8]
7ff75feaf33d movss dword ptr [rax - 0x70], xmm0
7ff75feaf342 movss dword ptr [rax - 0x74], xmm1
7ff75feaf347 jmp 0x7ff75feaf35a
7ff75feaf349 mov qword ptr [rsp + 0x24], 0
7ff75feaf352 mov dword ptr [rsp + 0x20], 0
7ff75feaf35a mov rax, qword ptr [rsp + 0xc0]
7ff75feaf362 mov dword ptr [rsp + 0x34], r9d
7ff75feaf367 test rax, rax
7ff75feaf36a je 0x7ff75feaf381
7ff75feaf36c movss xmm0, dword ptr [rax]
7ff75feaf370 movss xmm1, dword ptr [rax + 4]
7ff75feaf375 movss dword ptr [rsp + 0x2c], xmm0
7ff75feaf37b movss dword ptr [rsp + 0x30], xmm1
7ff75feaf381 mov r8, qword ptr [rsp + 0xc8]
7ff75feaf389 test r8, r8
7ff75feaf38c je 0x7ff75feaf3c4
7ff75feaf38e cvttss2si eax, dword ptr [r8]
7ff75feaf393 movzx edx, al
7ff75feaf396 cvttss2si eax, dword ptr [r8 + 4]
7ff75feaf39c shl edx, 8
7ff75feaf39f movzx ecx, al
7ff75feaf3a2 cvttss2si eax, dword ptr [r8 + 8]
7ff75feaf3a8 or edx, ecx
7ff75feaf3aa shl edx, 8
7ff75feaf3ad movzx ecx, al
7ff75feaf3b0 cvttss2si eax, dword ptr [r8 + 0xc]
7ff75feaf3b6 or edx, ecx
7ff75feaf3b8 shl edx, 8
7ff75feaf3bb movzx ecx, al
7ff75feaf3be or edx, ecx
7ff75feaf3c0 mov dword ptr [rsp + 0x38], edx
7ff75feaf3c4 mov edx, dword ptr [rbx + 0x98]
7ff75feaf3ca lea r8, [rsp + 0x20]
7ff75feaf3cf mov rcx, rbx
7ff75feaf3d2 call 0x7ff75fdd2220
7ff75feaf3d7 mov eax, dword ptr [rbx + 0x98]
7ff75feaf3dd lea ecx, [rax + 1]
7ff75feaf3e0 mov dword ptr [rbx + 0x98], ecx
7ff75feaf3e6 add rsp, 0x90
7ff75feaf3ed pop rbx
7ff75feaf3ee ret 
7ff75feaf3ef int3 
7ff75feaf3f0 mov rax, rsp
7ff75feaf3f3 sub rsp, 0x98
7ff75feaf3fa mov dword ptr [rax - 0x6c], 0x42c80000
7ff75feaf401 mov r10d, edx
7ff75feaf404 mov dword ptr [rax - 0x68], 0x42c80000
7ff75feaf40b mov r11, rcx
7ff75feaf40e mov dword ptr [rax - 0x60], 0xffffffff
7ff75feaf415 mov qword ptr [rax - 0x5c], 0
7ff75feaf41d mov qword ptr [rax - 0x54], 0
7ff75feaf425 movups xmm0, xmmword ptr [r8]
7ff75feaf429 movups xmm1, xmmword ptr [r8 + 0x10]
7ff75feaf42e movups xmmword ptr [rax - 0x4c], xmm0
7ff75feaf432 movups xmm0, xmmword ptr [r8 + 0x20]
7ff75feaf437 movups xmmword ptr [rax - 0x3c], xmm1
7ff75feaf43b movups xmm1, xmmword ptr [r8 + 0x30]
```

## 后端 bitmap_create（最多80条指令）

```text
7ff75feaf820 mov qword ptr [rsp + 0x10], rbx
7ff75feaf825 push rbp
7ff75feaf826 lea rbp, [rsp - 0x2f]
7ff75feaf82b sub rsp, 0xb0
7ff75feaf832 mov qword ptr [rbp + 0x3f], 0
7ff75feaf83a mov r10, r8
7ff75feaf83d mov rax, qword ptr [rbp + 0x3f]
7ff75feaf841 mov rbx, rcx
7ff75feaf844 mov dword ptr [rbp + 0x3f], 0x3f800000
7ff75feaf84b mov dword ptr [rbp + 0x43], 0x3f800000
7ff75feaf852 mov qword ptr [rbp - 0x29], rax
7ff75feaf856 mov rax, qword ptr [rbp + 0x3f]
7ff75feaf85a mov dword ptr [rbp - 0x55], 0x42c80000
7ff75feaf861 mov dword ptr [rbp - 0x51], 0x42c80000
7ff75feaf868 mov dword ptr [rbp - 0x49], 0xffffffff
7ff75feaf86f mov qword ptr [rbp - 0x45], 0
7ff75feaf877 mov qword ptr [rbp - 0x3d], 0
7ff75feaf87f mov qword ptr [rbp - 0x21], rax
7ff75feaf883 movups xmm0, xmmword ptr [rdx]
7ff75feaf886 movups xmm1, xmmword ptr [rdx + 0x10]
7ff75feaf88a movups xmmword ptr [rbp - 0x19], xmm0
7ff75feaf88e movups xmm0, xmmword ptr [rdx + 0x20]
7ff75feaf892 movups xmmword ptr [rbp - 9], xmm1
7ff75feaf896 movups xmm1, xmmword ptr [rdx + 0x30]
7ff75feaf89a movups xmmword ptr [rbp + 7], xmm0
7ff75feaf89e movups xmmword ptr [rbp + 0x17], xmm1
7ff75feaf8a2 test r9, r9
7ff75feaf8a5 je 0x7ff75feaf8c9
7ff75feaf8a7 movss xmm0, dword ptr [r9]
7ff75feaf8ac movss xmm1, dword ptr [r9 + 4]
7ff75feaf8b2 movss dword ptr [rbp - 0x61], xmm0
7ff75feaf8b7 movss xmm0, dword ptr [r9 + 8]
7ff75feaf8bd movss dword ptr [rbp - 0x59], xmm0
7ff75feaf8c2 movss dword ptr [rbp - 0x5d], xmm1
7ff75feaf8c7 jmp 0x7ff75feaf8d8
7ff75feaf8c9 mov qword ptr [rbp - 0x5d], 0
7ff75feaf8d1 mov dword ptr [rbp - 0x61], 0
7ff75feaf8d8 mov eax, dword ptr [rbp + 0x5f]
7ff75feaf8db mov dword ptr [rbp - 0x4d], eax
7ff75feaf8de mov rax, qword ptr [rbp + 0x67]
7ff75feaf8e2 test rax, rax
7ff75feaf8e5 je 0x7ff75feaf8fa
7ff75feaf8e7 movss xmm0, dword ptr [rax]
7ff75feaf8eb movss xmm1, dword ptr [rax + 4]
7ff75feaf8f0 movss dword ptr [rbp - 0x55], xmm0
7ff75feaf8f5 movss dword ptr [rbp - 0x51], xmm1
7ff75feaf8fa mov r8, qword ptr [rbp + 0x6f]
7ff75feaf8fe test r8, r8
7ff75feaf901 je 0x7ff75feaf938
7ff75feaf903 cvttss2si eax, dword ptr [r8]
7ff75feaf908 movzx edx, al
7ff75feaf90b cvttss2si eax, dword ptr [r8 + 4]
7ff75feaf911 shl edx, 8
7ff75feaf914 movzx ecx, al
7ff75feaf917 cvttss2si eax, dword ptr [r8 + 8]
7ff75feaf91d or edx, ecx
7ff75feaf91f shl edx, 8
7ff75feaf922 movzx ecx, al
7ff75feaf925 cvttss2si eax, dword ptr [r8 + 0xc]
7ff75feaf92b or edx, ecx
7ff75feaf92d shl edx, 8
7ff75feaf930 movzx ecx, al
7ff75feaf933 or edx, ecx
7ff75feaf935 mov dword ptr [rbp - 0x49], edx
7ff75feaf938 mov rax, qword ptr [rbp + 0x77]
7ff75feaf93c mov rcx, qword ptr [rbp + 0x7f]
7ff75feaf940 mov qword ptr [rbp - 0x31], r10
7ff75feaf944 test rax, rax
7ff75feaf947 jne 0x7ff75feaf94e
7ff75feaf949 test rcx, rcx
7ff75feaf94c je 0x7ff75feaf95c
7ff75feaf94e mov rax, qword ptr [rax]
7ff75feaf951 mov qword ptr [rbp - 0x29], rax
7ff75feaf955 mov rax, qword ptr [rcx]
7ff75feaf958 mov qword ptr [rbp - 0x21], rax
7ff75feaf95c mov edx, dword ptr [rbx + 0x98]
7ff75feaf962 lea r8, [rbp - 0x61]
7ff75feaf966 mov rcx, rbx
7ff75feaf969 call 0x7ff75fdd2ef0
7ff75feaf96e mov eax, dword ptr [rbx + 0x98]
```

## 后端 bitmap_update（最多80条指令）

```text
7ff75feaf9e0 push rbp
7ff75feaf9e2 lea rbp, [rsp - 0x27]
7ff75feaf9e7 sub rsp, 0xb0
7ff75feaf9ee movups xmm0, xmmword ptr [r8]
7ff75feaf9f2 mov qword ptr [rbp + 0x37], 0
7ff75feaf9fa mov r10d, edx
7ff75feaf9fd mov rax, qword ptr [rbp + 0x37]
7ff75feafa01 mov r11, rcx
7ff75feafa04 movups xmm1, xmmword ptr [r8 + 0x10]
7ff75feafa09 mov qword ptr [rbp - 0x31], rax
7ff75feafa0d mov dword ptr [rbp + 0x37], 0x3f800000
7ff75feafa14 mov dword ptr [rbp + 0x3b], 0x3f800000
7ff75feafa1b mov rax, qword ptr [rbp + 0x37]
7ff75feafa1f movups xmmword ptr [rbp - 0x21], xmm0
7ff75feafa23 mov qword ptr [rbp - 0x29], rax
7ff75feafa27 movups xmm0, xmmword ptr [r8 + 0x20]
7ff75feafa2c mov rax, qword ptr [rbp + 0x57]
7ff75feafa30 mov dword ptr [rbp - 0x5d], 0x42c80000
7ff75feafa37 mov dword ptr [rbp - 0x59], 0x42c80000
7ff75feafa3e mov dword ptr [rbp - 0x51], 0xffffffff
7ff75feafa45 mov qword ptr [rbp - 0x4d], 0
7ff75feafa4d mov qword ptr [rbp - 0x45], 0
7ff75feafa55 movups xmmword ptr [rbp - 0x11], xmm1
7ff75feafa59 movups xmm1, xmmword ptr [r8 + 0x30]
7ff75feafa5e movups xmmword ptr [rbp - 1], xmm0
7ff75feafa62 movups xmmword ptr [rbp + 0xf], xmm1
7ff75feafa66 test rax, rax
7ff75feafa69 je 0x7ff75feafa8a
7ff75feafa6b movss xmm0, dword ptr [rax]
7ff75feafa6f movss xmm1, dword ptr [rax + 4]
7ff75feafa74 movss dword ptr [rbp - 0x69], xmm0
7ff75feafa79 movss xmm0, dword ptr [rax + 8]
7ff75feafa7e movss dword ptr [rbp - 0x61], xmm0
7ff75feafa83 movss dword ptr [rbp - 0x65], xmm1
7ff75feafa88 jmp 0x7ff75feafa99
7ff75feafa8a mov qword ptr [rbp - 0x65], 0
7ff75feafa92 mov dword ptr [rbp - 0x69], 0
7ff75feafa99 mov eax, dword ptr [rbp + 0x5f]
7ff75feafa9c mov dword ptr [rbp - 0x55], eax
7ff75feafa9f mov rax, qword ptr [rbp + 0x67]
7ff75feafaa3 test rax, rax
7ff75feafaa6 je 0x7ff75feafabb
7ff75feafaa8 movss xmm0, dword ptr [rax]
7ff75feafaac movss xmm1, dword ptr [rax + 4]
7ff75feafab1 movss dword ptr [rbp - 0x5d], xmm0
7ff75feafab6 movss dword ptr [rbp - 0x59], xmm1
7ff75feafabb mov r8, qword ptr [rbp + 0x6f]
7ff75feafabf test r8, r8
7ff75feafac2 je 0x7ff75feafaf9
7ff75feafac4 cvttss2si eax, dword ptr [r8]
7ff75feafac9 movzx edx, al
7ff75feafacc cvttss2si eax, dword ptr [r8 + 4]
7ff75feafad2 shl edx, 8
7ff75feafad5 movzx ecx, al
7ff75feafad8 cvttss2si eax, dword ptr [r8 + 8]
7ff75feafade or edx, ecx
7ff75feafae0 shl edx, 8
7ff75feafae3 movzx ecx, al
7ff75feafae6 cvttss2si eax, dword ptr [r8 + 0xc]
7ff75feafaec or edx, ecx
7ff75feafaee shl edx, 8
7ff75feafaf1 movzx ecx, al
7ff75feafaf4 or edx, ecx
7ff75feafaf6 mov dword ptr [rbp - 0x51], edx
7ff75feafaf9 mov rax, qword ptr [rbp + 0x77]
7ff75feafafd mov rcx, qword ptr [rbp + 0x7f]
7ff75feafb01 mov qword ptr [rbp - 0x39], r9
7ff75feafb05 test rax, rax
7ff75feafb08 jne 0x7ff75feafb0f
7ff75feafb0a test rcx, rcx
7ff75feafb0d je 0x7ff75feafb1d
7ff75feafb0f mov rax, qword ptr [rax]
7ff75feafb12 mov qword ptr [rbp - 0x31], rax
7ff75feafb16 mov rax, qword ptr [rcx]
7ff75feafb19 mov qword ptr [rbp - 0x29], rax
7ff75feafb1d lea r8, [rbp - 0x69]
7ff75feafb21 mov edx, r10d
7ff75feafb24 mov rcx, r11
7ff75feafb27 call 0x7ff75fdd2ef0
7ff75feafb2c add rsp, 0xb0
```

## 截图判读

每行对应一个世界。0.4.5六列：-16381、0、100、401、403、16381，颜色按白、紫、青重复。旧版本列定义以SUMMARY为准。地图中央与屏幕左下角是成对色块，全部不透明。

- 某行地图内外都鲜亮：该世界可以作为覆盖层候选。
- 某行只有高层级色块鲜亮：可能是图元排序问题。
- 地图外鲜亮但所有地图内色块都被染色：可能在世界GUI之后统一合成迷雾，需截图确认。
- 某行内外都不显示：该世界可能没有被渲染。创建成功不等于显示成功。

文本记录不能自动判断画面颜色。未知UI字节不会被解释成迷雾开关。
第二次按F8开启会覆盖采样。对比有迷雾和无迷雾地图时先保存各自的截图及FOG_*文件。
