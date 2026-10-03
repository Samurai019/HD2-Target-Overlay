import json,struct,zipfile,hashlib
from pathlib import Path
from lupa.luajit21 import LuaRuntime
from build import resource_hash
ROOT=Path(__file__).resolve().parent
def source_bytes():
    reference=(ROOT/'src/map_icons_runtime.lua').read_text(encoding='utf-8-sig')
    helper=reference[reference.index('local function hash_file'):reference.index('local function filename')]
    source=(ROOT/'src/overlay.lua').read_text(encoding='utf-8-sig').replace('-- HASH_HELPER\n',helper+'\n')
    rows=json.loads((ROOT/'research/render-patches.json').read_text(encoding='utf-8-sig'))
    header=['-- HD2-Addon: mods/astla/target_overlay',
      'local function unhex(s)return (s:gsub("%x%x",function(v)return string.char(tonumber(v,16))end)) end',
      'local ORIGINAL_SITES={']
    for s in rows:header.append('{rva=%d,bytes=unhex("%s")},'%(s['rva'],s['original']))
    header.append('}')
    result=('\n'.join(header)+'\n'+source).encode()
    for forbidden in [b'WriteProcessMemory',b'VirtualProtect',b'OpenProcess(',b'FlushInstructionCache',b'ffi.copy',b'ffi.fill']:
        assert forbidden not in result
    return result
def main():
    source=source_bytes();lua=LuaRuntime(encoding=None);lua.execute(b'assert(loadstring(...))',source)
    name='mods/astla/target_overlay';payload=struct.pack('<II',len(source),2)+source
    offset=192;total=(offset+len(payload)+15)&~15;data=bytearray(total)
    struct.pack_into('<III20sQQ24s',data,0,0xf0000011,1,1,b'',total,0,b'')
    struct.pack_into('<IIQIIII',data,72,0,0,0xa14e8dfa2cd117e2,1,0,16,16)
    struct.pack_into('<7Q6I',data,104,resource_hash(name),0xa14e8dfa2cd117e2,offset,0,0,0,0,len(payload),0,0,16,16,0)
    data[offset:offset+len(payload)]=payload
    title='Target Overlay 1.3.0'
    description='Minimap overlay for counted outposts, the Stalker Lair side objective (a dedicated hollow red eight-point star), undiscovered side objectives loaded super-credit models and main-mission black-box models (hollow yellow diamonds). Other mission-attached holes are excluded. Red markers remain until cleared; white markers disappear on discovery; credit markers disappear on pickup; black-box markers disappear when the native black-box marker takes over. HUD curvature alignment follows the live setting and has been confirmed in-game. Medals use a dedicated gold octagonal medal icon with blue ribbons, follow loaded model presence and pickup, and are disabled by default. Five independent toggles in the optional Mod Options Menu (requires Bingus Shared Loader v18+). F7 toggles the overlay. Read-only game access. Requires Bingus Shared Loader v15+ and game build 1.8.46015.0.'
    manifest={'Version':1,'Guid':'ad42316a-e57c-4aa6-a4ec-987ce39de584','Name':title,'Description':description,
      'Options':[{'Name':title,'Description':description,'Include':['Addon']}]}
    path=ROOT/'dist/Target-Overlay-1.3.0.zip'
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('manifest.json',json.dumps(manifest,indent=2))
        z.writestr('Addon/9ba626afa44a3aa3.patch_0',data)
        z.writestr('Addon/9ba626afa44a3aa3.patch_0.stream',b'')
        z.writestr('Addon/9ba626afa44a3aa3.patch_0.gpu_resources',b'')
        z.writestr('README.md',(ROOT/'OVERLAY.md').read_bytes())
    with zipfile.ZipFile(path) as z:
        assert z.testzip() is None
        assert z.read('Addon/9ba626afa44a3aa3.patch_0')[offset+8:offset+len(payload)]==source
    (ROOT/'dist/target_overlay.lua').write_bytes(source)
    print(path);print('SHA256='+hashlib.sha256(path.read_bytes()).hexdigest())
if __name__=='__main__':main()
