"""Package the local selector-indicator fix for Mod Options Menu v1.0.1."""
import hashlib,json,struct,zipfile
from pathlib import Path
from lupa.luajit21 import LuaRuntime
from build import resource_hash
ROOT=Path(__file__).resolve().parent
UPSTREAM=ROOT/'research/ModOptionsMenu'
def main():
    source=(UPSTREAM/'src/mod_options_menu.lua').read_bytes()
    LuaRuntime(encoding=None).execute(b'assert(loadstring(...))',source)
    name='mods/cowboybingus/mod_options_menu'
    payload=struct.pack('<II',len(source),2)+source
    offset=192;total=(offset+len(payload)+15)&~15;data=bytearray(total)
    struct.pack_into('<III20sQQ24s',data,0,0xf0000011,1,1,b'',total,0,b'')
    struct.pack_into('<IIQIIII',data,72,0,0,0xa14e8dfa2cd117e2,1,0,16,16)
    struct.pack_into('<7Q6I',data,104,resource_hash(name),0xa14e8dfa2cd117e2,offset,0,0,0,0,len(payload),0,0,16,16,0)
    data[offset:offset+len(payload)]=payload
    title='Mod Options Menu v1.0.1 UI Fix'
    description='Local UI indicator fix for CowboyBingus Mod Options Menu v1.0.1. Refreshes reused selector rows on creation. Replace the original menu; enable only one menu. Requires Bingus Shared Loader v18+ and supported build.'
    option={'Name':title,'Description':description,'Include':['Addon']}
    manifest={'Version':1,'Guid':'95ef276a-6287-465f-ac5b-8512d2227b74','Name':title,'Description':description,'Options':[option]}
    path=ROOT/'dist/Mod-Options-Menu-v1.0.1-UI-Fix.zip'
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('manifest.json',json.dumps(manifest,indent=2))
        archive.writestr('Addon/9ba626afa44a3aa3.patch_0',data)
        archive.writestr('Addon/9ba626afa44a3aa3.patch_0.stream',b'')
        archive.writestr('Addon/9ba626afa44a3aa3.patch_0.gpu_resources',b'')
        archive.writestr('INSTALL.txt',(UPSTREAM/'INSTALL.txt').read_bytes())
        archive.writestr('UI_FIX_README.md',(ROOT/'research/MENU_INDICATOR_FIX.md').read_bytes())
    with zipfile.ZipFile(path) as archive:
        assert archive.testzip() is None
        assert archive.read('Addon/9ba626afa44a3aa3.patch_0')[offset+8:offset+len(payload)]==source
    print(path);print('SHA256='+hashlib.sha256(path.read_bytes()).hexdigest())
if __name__=='__main__':main()
