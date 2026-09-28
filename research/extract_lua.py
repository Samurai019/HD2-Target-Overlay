from pathlib import Path
import struct,re,argparse
parser=argparse.ArgumentParser(description='Extract Lua resources from installed mod patches')
parser.add_argument('data_dir',type=Path,help='Helldivers 2 data directory')
root=parser.parse_args().data_dir
out=Path(__file__).resolve().parent/'installed_lua'
out.mkdir(exist_ok=True)
for p in root.glob('9ba626afa44a3aa3.patch_*'):
    if not re.fullmatch(r'.*\.patch_\d+',p.name): continue
    with p.open('rb') as f:
        head=f.read(72)
        if len(head)!=72: continue
        magic,nt,nr=struct.unpack_from('<III',head)
        if magic!=0xf0000011 or nt>1000 or nr>10000: continue
        f.seek(72+nt*32)
        records=f.read(nr*80)
        for i in range(nr):
            h,t,off=struct.unpack_from('<QQQ',records,80*i)
            if t!=0xa14e8dfa2cd117e2:continue
            size=struct.unpack_from('<I',records,80*i+56)[0]
            f.seek(off); data=f.read(size)
            if len(data)<8:continue
            body=data[8:]
            target=out/(p.name+'_'+f'{h:016x}'+'.lua')
            target.write_bytes(body)
            print(target.name,body[:100])
