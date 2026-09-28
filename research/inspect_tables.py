import struct, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
def h(s):
    n = 5381
    for c in s: n = (n * 33 + ord(c)) & 0xffffffff
    return (n - 5381) & 0xffffffff

b = (ROOT/'filediver/datalibrary/dl_library.dl_typelib').read_bytes()
head = struct.unpack_from('<4s8I', b)
_, ver, nt, ne, nm, nv, na, nd, ns = head
ids = struct.unpack_from(f'<{nt}I', b, 36)
td = 36 + 4*(nt+ne)
md = td + 36*nt + 32*ne
strings = md + 72*nm + 16*nv + 8*na + nd
assert strings+ns == len(b), (head, strings, len(b))
def name(off):
    if off == 0xffffffff: return ''
    if not ns: return hex(off)
    return b[strings+off:b.index(b'\0',strings+off)].decode()

types={}
for target in ['ShowOnMapComponentData','ShowOnMapComponent','ObjectiveComponentData','ObjectiveComponent','ComponentIndexData']:
    ix=ids.index(h(target)); t=struct.unpack_from('<9I',b,td+36*ix)
    members=[]
    for i in range(t[7],t[7]+t[6]):
        m=struct.unpack_from('<18I',b,md+72*i)
        members.append(dict(name=name(m[0]),offset=m[10],size=m[6],type_hash=f'{m[4]:08x}',atom=m[3]&255,storage=(m[3]>>8)&255,bits=m[3]>>16))
    types[target]=dict(hash=f'{h(target):08x}',size=t[3],members=members)
(ROOT/'target-layouts.json').write_text(json.dumps(types,indent=2),encoding='utf8')
blob=(ROOT/'filediver/datalibrary/generated_entities.dl_bin').read_bytes()
for target in ['ShowOnMapComponentData','ObjectiveComponentData']:
    sig=b'LDLD'+struct.pack('<II',1,h(target)); off=blob.find(sig)
    size=struct.unpack_from('<I',blob,off+12)[0]
    (ROOT/(target+'.bin')).write_bytes(blob[off:off+24+size])
    print(target,'blob offset',off,'size',size,'first bytes',blob[off:off+96].hex())
print(json.dumps(types,indent=2))
