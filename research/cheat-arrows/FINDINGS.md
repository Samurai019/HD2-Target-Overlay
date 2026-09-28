# 超级货币光柱包分析

只读分析用户提供的Customizable Cheat Arrows归档。Credit/High与Credit/Low均替换unit资源bd6f4de16b9aedcd；High另带三个material，Low只有unit。High/Low是箭头高度选项，不是LOD名称。

Filediver LoadInfo成功解析两种unit：High104个节点、6网格、2个LOD组；Low21个节点、8网格、2个LOD组。两者节点0都为StingrayEntityRoot，节点1为FbxAxisSystem_ConvertNode，交互节点名称哈希e4a4586d（interact）分别为103与20，本地位移约(0.063,-0.078,0.087)。同一资源内确有LOD组，包中未替换不同LOD资源ID。

实时0.4.8日志的三个候选都在主世界，节点0XYZ全为0。因此辅助世界过滤并没有解决错误坐标。用户说明误标位置为地图中心的落地点，符合零坐标投影的表现，不能据此认定对象跟随玩家。

0.4.9按名称读取interact世界位置，并拒绝未解析的零根坐标+原点附近交互偏移。这里只验证了节点结构和模拟流程，实际节点坐标仍需实机核对。若仍全为默认坐标，应调查引擎单位包装器／对象实例位置来源，不继续猜固定节点编号。
