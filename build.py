"""Build the read-only probe. Does not modify the game installation."""
import json,struct,zipfile,hashlib,re
from pathlib import Path
from lupa.luajit21 import LuaRuntime

ROOT=Path(__file__).resolve().parent
def resource_hash(name):
    data=name.encode(); mask=(1<<64)-1; mix=0xc6a4a7935bd1e995
    value=len(data)*mix&mask; end=len(data)//8*8
    for word, in struct.iter_unpack('<Q',data[:end]):
        word=word*mix&mask; word^=word>>47
        value=(value^(word*mix&mask))*mix&mask
    if data[end:]:value=(value^int.from_bytes(data[end:],'little'))*mix&mask
    value^=value>>47; value=value*mix&mask; return value^(value>>47)

def main():
    source=(ROOT/'src/map_reveal_probe.lua').read_bytes()
    name='mods/astla/map_reveal_probe'
    assert source.startswith(('-- HD2-Addon: '+name+'\n').encode())
    lua=LuaRuntime(encoding=None,unpack_returned_tuples=True)
    lua.execute(b'assert(loadstring(...))',source)
    payload=struct.pack('<II',len(source),2)+source
    offset=192; total=(offset+len(payload)+15)&~15
    data=bytearray(total)
    struct.pack_into('<III20sQQ24s',data,0,0xf0000011,1,1,b'',total,0,b'')
    struct.pack_into('<IIQIIII',data,72,0,0,0xa14e8dfa2cd117e2,1,0,16,16)
    struct.pack_into('<7Q6I',data,104,resource_hash(name),0xa14e8dfa2cd117e2,offset,0,0,0,0,len(payload),0,0,16,16,0)
    data[offset:offset+len(payload)]=payload
    title='Map Icon Probe 0.1.0'
    assert title.isascii() and not re.search(r'[\\/:*?"<>|]',title)
    description='Read-only diagnostic; does not reveal icons yet. Requires Bingus Shared Loader v15+ (API 1 is the loader API level). In a mission, open the map and press F8.'
    manifest={'Version':1,'Guid':'ba3f72d1-3ad6-4a4c-8b87-90484faf048d','Name':title,'Description':description,
      'Options':[{'Name':title,'Description':description,'Include':['Addon']}]}
    files={'manifest.json':json.dumps(manifest,indent=2).encode(),
      'Addon/9ba626afa44a3aa3.patch_0':bytes(data),
      'Addon/9ba626afa44a3aa3.patch_0.stream':b'',
      'Addon/9ba626afa44a3aa3.patch_0.gpu_resources':b'',
      'README.md':(ROOT/'README.md').read_bytes()}
    dest=ROOT/'dist/Map-Icon-Probe-0.1.0.zip'; dest.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(dest,'w',zipfile.ZIP_DEFLATED) as z:
        for path,body in files.items():z.writestr(path,body)
    with zipfile.ZipFile(dest) as z:
        assert z.testzip() is None
        archive=z.read('Addon/9ba626afa44a3aa3.patch_0')
        off=struct.unpack_from('<Q',archive,120)[0]
        length=struct.unpack_from('<I',archive,160)[0]
        assert archive[off+8:off+length]==source
    print(dest)
    print('Archive round-trip and LuaJIT compilation passed; SHA256='+hashlib.sha256(dest.read_bytes()).hexdigest())

if __name__=='__main__':main()
