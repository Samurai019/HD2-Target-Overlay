import argparse,os,struct
from pathlib import Path

def analyze(folder):
    lines=['# 迷雾诊断报告','','仅分析已有文件，不连接游戏进程。','']
    summary=folder/'FOG_SUMMARY.txt'
    if not summary.exists():return '\n'.join(lines+['尚无采样。打开有迷雾的小地图后按F8。'])+'\n'
    for name in ('FOG_SUMMARY.txt','FOG_DRAW.txt','FOG_ERROR.txt','RENDER_ORDER.txt'):
        p=folder/name
        if p.exists():lines += [f'## {name}','','```text',p.read_text(encoding='utf8',errors='replace').strip(),'```','']
    p=folder/'FOG_presenter.bin'
    if p.exists():
        b=p.read_bytes()
        if len(b)==200:
            lines+=['## 地图快照','',f'- enabled={b[0x74]}, open={b[0x75]}。']
            for name,o in [('地图比例',0x28),('中心X',0x9c),('中心Y',0xa0),('半径',0xa4)]:
                lines.append(f'- {name}：{struct.unpack_from("<f",b,o)[0]:g}。')
        else:lines.append(f'快照长度异常：{len(b)}，预期200。')
    lines+=['','## 原生UI绘制分组','']
    getters={3:0x148,4:0x1a8,7:0x2a8,8:0x2a8,9:0x470,10:0x1148,11:0x148,13:0x138}
    for label in ('spore_bitmap','spore_parent','map_bitmap','map_container'):
        p=folder/('FOG_'+label+'.bin')
        if not p.exists():continue
        b=p.read_bytes()
        if len(b)!=0x1160:lines.append(label+'：快照不完整');continue
        flags=struct.unpack_from('<I',b)[0];kind=(flags>>18)&15;bucket=(flags>>29)&7
        order=struct.unpack_from('<H',b,0xbc)[0]
        lines.append(f'- {label}：类型{kind}，原生分组{bucket}，组内顺序{order}，flags=0x{flags:08x}。')
    lines+=['','分组来自原生UI字段，不等于Lua矩形的Z值。尚未获得Lua GUI与此字段的映射。',
             '孢子材质资源已在原版构造函数确认：content/ui/shared/misc/spore_obfuscation。']
    import re
    metadata=summary.read_text(encoding='utf8',errors='replace')
    for name in ('rect','bitmap_create','bitmap_update'):
        p=folder/('FOG_backend_'+name+'.bin')
        match=re.search(r'backend\.'+name+r'\.address=0x([0-9a-f]+)',metadata)
        if p.exists() and match:
            try:
                from capstone import Cs,CS_ARCH_X86,CS_MODE_64
                address=int(match.group(1),16)
                lines+=['',f'## 后端 {name}（最多80条指令）','','```text']
                for i,ins in enumerate(Cs(CS_ARCH_X86,CS_MODE_64).disasm(p.read_bytes(),address)):
                    if i>=80:break
                    lines.append(f'{ins.address:x} {ins.mnemonic} {ins.op_str}')
                lines+=['```']
            except ImportError:lines.append('保留代码快照；反汇编需要capstone。')
    lines+=['','## 截图判读','',
        '每行对应一个世界。0.4.5六列：-16381、0、100、401、403、16381，颜色按白、紫、青重复。旧版本列定义以SUMMARY为准。地图中央与屏幕左下角是成对色块，全部不透明。','',
        '- 某行地图内外都鲜亮：该世界可以作为覆盖层候选。',
        '- 某行只有高层级色块鲜亮：可能是图元排序问题。',
        '- 地图外鲜亮但所有地图内色块都被染色：可能在世界GUI之后统一合成迷雾，需截图确认。',
        '- 某行内外都不显示：该世界可能没有被渲染。创建成功不等于显示成功。','',
        '文本记录不能自动判断画面颜色。未知UI字节不会被解释成迷雾开关。',
        '第二次按F8开启会覆盖采样。对比有迷雾和无迷雾地图时先保存各自的截图及FOG_*文件。']
    return '\n'.join(lines)+'\n'

def main():
    ap=argparse.ArgumentParser(description='Analyze saved fog probe files; no process access.')
    ap.add_argument('--input',type=Path,default=Path(os.getenv('LOCALAPPDATA','.'))/'Hd2TargetOverlay')
    ap.add_argument('--output',type=Path)
    args=ap.parse_args();output=args.output or args.input/'FOG_ANALYSIS.md'
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(analyze(args.input),encoding='utf8');print(output)
if __name__=='__main__':main()
