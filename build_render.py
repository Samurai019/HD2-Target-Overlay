import json,struct,zipfile,hashlib
from pathlib import Path
from lupa.luajit21 import LuaRuntime
from build import resource_hash

ROOT=Path(__file__).resolve().parent
def source_bytes():
    rows=json.loads((ROOT/'research/render-patches.json').read_text())
    lines=['-- HD2-Addon: mods/astla/map_icons_display_only',
      'local function unhex(s) return (s:gsub("%x%x",function(v)return string.char(tonumber(v,16))end)) end',
      'local SITES={']
    for s in rows:
        lines.append('{name="%s",rva=%d,offset=%d,bytes=unhex("%s"),value=%d},'%(s['name'],s['rva'],s['offset'],s['original'],s['replacement']))
    lines.append('}')
    return ('\n'.join(lines)+'\n').encode()+(ROOT/'src/map_icons_runtime.lua').read_bytes()

def main():
    source=source_bytes()
    lua=LuaRuntime(encoding=None);lua.execute(b'assert(loadstring(...))',source)
    name='mods/astla/map_icons_display_only'
    payload=struct.pack('<II',len(source),2)+source;off=192;total=(off+len(payload)+15)&~15
    archive=bytearray(total)
    struct.pack_into('<III20sQQ24s',archive,0,0xf0000011,1,1,b'',total,0,b'')
    struct.pack_into('<IIQIIII',archive,72,0,0,0xa14e8dfa2cd117e2,1,0,16,16)
    struct.pack_into('<7Q6I',archive,104,resource_hash(name),0xa14e8dfa2cd117e2,off,0,0,0,0,len(payload),0,0,16,16,0)
    archive[off:off+len(payload)]=payload
    title='Map Icons Display Only 0.1.0 Experimental'
    description='Experimental local map icon rendering override for game 1.8.46015.0 only. Does not write discovery flags. Requires Bingus Shared Loader v15+; API 1 is its API level.'
    manifest={'Version':1,'Guid':'7b9d4d2d-5177-4345-80ad-d862c53b5882','Name':title,'Description':description,
      'Options':[{'Name':title,'Description':description,'Include':['Addon']}]}
    dest=ROOT/'dist/Map-Icons-Display-Only-0.1.0.zip';dest.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(dest,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('manifest.json',json.dumps(manifest,indent=2))
        z.writestr('Addon/9ba626afa44a3aa3.patch_0',archive)
        z.writestr('Addon/9ba626afa44a3aa3.patch_0.stream',b'')
        z.writestr('Addon/9ba626afa44a3aa3.patch_0.gpu_resources',b'')
        z.writestr('README.md',(ROOT/'DISPLAY_ONLY.md').read_bytes())
    with zipfile.ZipFile(dest) as z:
        assert z.testzip() is None
        restored=z.read('Addon/9ba626afa44a3aa3.patch_0')
        assert restored[off+8:off+len(payload)]==source
    (ROOT/'dist/map_icons_display_only.lua').write_bytes(source)
    print(dest);print('SHA256='+hashlib.sha256(dest.read_bytes()).hexdigest())

if __name__=='__main__':main()
