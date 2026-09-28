# Target Overlay 1.1.0 菜单接入

上游：https://github.com/CowboyBingus/ModOptionsMenu ，核对提交 `4dedb3428b320507a80190dd3a083bd668e84126`（v1.0.1）。源代码保存在 `research/ModOptionsMenu` 供离线接口测试。上游菜单所校验的 game.dll / EXE SHA256 与本项目现有构建一致。菜单要求 Bingus Shared Loader v18+。

使用可选全局 `ModOptionsMenu` API 1：`register_option`、`get`、`on_change`。稳定保存键分别为 `astla.target_overlay.outposts`、`astla.target_overlay.objectives`、`astla.target_overlay.credits`。分类为 Target Overlay，中文行标签为标记虫巢、标记支线、标记蓝币；默认 true。代码不调用 `set` 覆盖玩家保存的设置。

延迟注册兼容 addon 加载顺序。注册成功后读取已应用值，并通过回调使当前坐标缓存失效；每30帧复读值覆盖菜单 `set` 不触发回调的情况。注册失败对同一 API 实例每项只尝试一次，记录在 `HD2TargetOverlay.options_error`，不停止覆盖层。没有菜单时三项默认开启；F7 总开关独立于持久化设置。

`tests/test_overlay_menu.py` 在 LuaJIT 中加载上游真实菜单代码，仅执行注册、值保存/加载和待应用值处理，不调用原生游戏菜单绘制入口，不修改外部游戏进程。覆盖中文标签、只注册一次、只订阅一次、未应用不生效、应用后回调清缓存、保存后重启恢复、全部8种分类组合、晚加载、缺失/不兼容接口、注册失败和异常。两个变异（忽略分类设置、未清缓存）均被捕获。全套51项通过；安装包归档与语法验证通过。

游戏内 MODS 分类、中文字体、APPLY 操作与图标切换尚待实测。菜单作为外部可选依赖，不包含在 Target Overlay 安装包中。
