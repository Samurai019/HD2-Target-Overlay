import struct,re,bisect,sys
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_64
ROOT=Path(__file__).resolve().parent/'runtime'
segments=[]
for p in ROOT.glob('capture_01_module_*.bin'):
    segments.append((int(p.stem.split('_')[-1],16),p.read_bytes()))
def read(rva,n):
    for start,b in segments:
        if start<=rva and rva+n<=start+len(b): return b[rva-start:rva-start+n]
    return b''
pdata=read(0x37d8000,1832304)
funcs=[]
for i in range(0,len(pdata)-11,12):
    a,b,c=struct.unpack_from('<III',pdata,i)
    if 0x1000<=a<b<=0x2111000:funcs.append((a,b,c))
funcs.sort();starts=[x[0] for x in funcs]
def function(at):
    ix=bisect.bisect_right(starts,at)-1
    return funcs[ix] if ix>=0 and at<funcs[ix][1] else (at,at+256,0)
def disasm(at):
    a,b,c=function(at)
    print(f'FUNCTION {a:x}-{b:x} unwind={c:x}')
    cs=Cs(CS_ARCH_X86,CS_MODE_64)
    for ins in cs.disasm(read(a,b-a),a):
        print(f'{ins.address:08x} {ins.mnemonic:8} {ins.op_str}')
if __name__=='__main__':
    for arg in sys.argv[1:]:disasm(int(arg,16))
