-- HD2-Addon: mods/astla/map_icons_display_only
local function unhex(s) return (s:gsub("%x%x",function(v)return string.char(tonumber(v,16))end)) end
local SITES={
{name="poi_visible",rva=25921193,offset=12,bytes=unhex("41807cff0100750b41803cff000f8428040000f3410f109548010000498b4424380f28da8b4c24400f28e2f3440f1045"),value=255},
{name="poi_original_icon",rva=25921443,offset=11,bytes=unhex("eeb8ff488b5c2468803cfb000f8406020000488b5580f30f104cfb04f30f1054fb08807a2000743ff3410f1085480100"),value=255},
{name="poi_opacity",rva=25921778,offset=11,bytes=unhex("e8b8ff488b442470803cc3000f85a2010000488b4580807829000f84ef010000f3440f5c45b8f30f104590f3410f5cff"),value=255},
{name="objective_icon_path",rva=25904826,offset=13,bytes=unhex("c6842e0cfc00000042837c024401f30f58cbf30f59c2f30f114d20f30f58c4f30f1145244c8b75204c8975304c897424"),value=255},
{name="objective_detail_icon",rva=25907290,offset=12,bytes=unhex("488b4588488b4d90807c0840007525488b442460498bfd488b4dc88b84012801000085c0746983bda400000000750583"),value=255},
}
-- This template receives a plaintext addon marker and verified site list at build time.
local Core={sites=SITES}
local function patched(site)
    return site.bytes:sub(1,site.offset)..string.char(site.value)..site.bytes:sub(site.offset+2)
end
function Core.apply(api,base)
    local pending,backups={},{}
    for _,s in ipairs(SITES) do
        local current=api.read(base+s.rva,#s.bytes)
        if current~=s.bytes and current~=patched(s) then error('Code fingerprint mismatch: '..s.name) end
        backups[#backups+1]=s.name..' '..string.format('%X',s.rva)..' '..(current:gsub('.',function(c)return string.format('%02x',c:byte())end))
        if current==s.bytes then pending[#pending+1]=s end
    end
    api.backup(table.concat(backups,'\n'))
    local touched={}
    local ok,message=pcall(function()
        for _,s in ipairs(pending) do
            -- Revalidate immediately before each write, including neighboring instructions.
            assert(api.read(base+s.rva,#s.bytes)==s.bytes,'Code changed during validation: '..s.name)
            touched[#touched+1]=s
            api.write(base+s.rva+s.offset,string.char(s.value))
            assert(api.read(base+s.rva,#s.bytes)==patched(s),'Readback failed: '..s.name)
        end
    end)
    if not ok then
        local failures={}
        for i=#touched,1,-1 do
            local s=touched[i]
            local good,err=pcall(function()
                local current=api.read(base+s.rva,#s.bytes)
                if current==patched(s) then
                    api.write(base+s.rva+s.offset,s.bytes:sub(s.offset+1,s.offset+1))
                elseif current~=s.bytes then error('rollback conflict') end
                assert(api.read(base+s.rva,#s.bytes)==s.bytes,'rollback readback failed')
            end)
            if not good then failures[#failures+1]=s.name..': '..tostring(err) end
        end
        error(tostring(message)..'; rollback '..(#failures==0 and 'OK' or table.concat(failures,'; ')))
    end
    return #pending
end
if rawget(_G,'HD2MapIconsTest') then return Core end
if rawget(_G,'HD2MapIconsDisplayOnly') then return end
local state={phase='initializing',frames=0}
_G.HD2MapIconsDisplayOnly=state
local out=(os.getenv('LOCALAPPDATA') or '.')..'\\Hd2MapIconsDisplayOnly'
local function save(name,text)
    local f=assert(io.open(out..'\\'..name,'wb'))
    assert(f:write(text));assert(f:close())
end
local function status(phase,message)
    state.phase=phase
    pcall(save,'STATUS.txt',phase..' - '..message..'\r\nMap Icons Display Only 0.1.0 experimental\r\n')
end
local ffi,kernel,crypto,process,base
local count,buffer,oldprotect
local function hash_file(path)
    local provider,hash=ffi.new('uintptr_t[1]'),ffi.new('uintptr_t[1]')
    local file
    local ok,result=pcall(function()
        assert(crypto.CryptAcquireContextA(provider,nil,nil,24,0xF0000000)~=0,'CryptAcquireContext failed')
        assert(crypto.CryptCreateHash(provider[0],0x800c,0,0,hash)~=0,'CryptCreateHash failed')
        file=assert(io.open(path,'rb'))
        while true do
            local bytes=file:read(65536)
            if not bytes then break end
            assert(crypto.CryptHashData(hash[0],ffi.cast('const unsigned char *',bytes),#bytes,0)~=0,'SHA256 update failed')
            coroutine.yield()
        end
        file:close();file=nil
        local digest,n=ffi.new('unsigned char[32]'),ffi.new('unsigned long[1]',32)
        assert(crypto.CryptGetHashParam(hash[0],2,digest,n,0)~=0 and n[0]==32,'SHA256 finish failed')
        return (ffi.string(digest,32):gsub('.',function(c)return string.format('%02X',c:byte())end))
    end)
    if file then file:close() end
    if hash[0]~=0 then crypto.CryptDestroyHash(hash[0]) end
    if provider[0]~=0 then crypto.CryptReleaseContext(provider[0],0) end
    if not ok then error(result) end
    return result
end
local function filename(handle)
    local b=ffi.new('char[32768]')
    local n=kernel.GetModuleFileNameA(handle,b,32768)
    assert(n>0 and n<32768,'module filename unavailable')
    return ffi.string(b,n)
end
local function setup()
    ffi=require('ffi')
    ffi.cdef[[
        void *GetCurrentProcess(void);
        void *GetModuleHandleA(const char *);
        unsigned long GetModuleFileNameA(void *,char *,unsigned long);
        int CreateDirectoryA(const char *,void *);
        int ReadProcessMemory(void *,const void *,void *,size_t,size_t *);
        int WriteProcessMemory(void *,void *,const void *,size_t,size_t *);
        int VirtualProtect(void *,size_t,unsigned long,unsigned long *);
        int FlushInstructionCache(void *,const void *,size_t);
        int CryptAcquireContextA(uintptr_t *,const char *,const char *,unsigned long,unsigned long);
        int CryptCreateHash(uintptr_t,unsigned long,uintptr_t,unsigned long,uintptr_t *);
        int CryptHashData(uintptr_t,const unsigned char *,unsigned long,unsigned long);
        int CryptGetHashParam(uintptr_t,unsigned long,unsigned char *,unsigned long *,unsigned long);
        int CryptDestroyHash(uintptr_t);
        int CryptReleaseContext(uintptr_t,unsigned long);
    ]]
    kernel,crypto=ffi.load('kernel32'),ffi.load('advapi32')
    kernel.CreateDirectoryA(out,nil)
    local loader=rawget(_G,'CowboyBingusModLoader')
    assert(type(loader)=='table' and tonumber(loader.api) and loader.api>=1,'Bingus Shared Loader API 1 required')
    process=kernel.GetCurrentProcess()
    local handle=kernel.GetModuleHandleA('game.dll')
    base=tonumber(ffi.cast('uintptr_t',handle))
    assert(base and base>0,'game.dll unavailable')
    status('VERIFYING','Checking game build SHA256; no memory writes yet')
    assert(hash_file(filename(nil))=='F5FEE03DCFDB2E553A4752C283590950AC13316B376D8196AA556FF0400D5F06','Unsupported helldivers2.exe build')
    assert(hash_file(filename(handle))=='2E2C3B7C2500646DADD5F2B4C6E0504DBB7E7896139F64CDDC0D1813C718F51E','Unsupported game.dll build')
    count,buffer=ffi.new('size_t[1]'),ffi.new('unsigned char[256]')
    oldprotect=ffi.new('unsigned long[1]')
    local api={}
    local protections={}
    api.read=function(addr,n)
        assert(n<=256,'read too large')
        count[0]=0
        if kernel.ReadProcessMemory(process,ffi.cast('const void *',addr),buffer,n,count)==0 or tonumber(count[0])~=n then return nil end
        return ffi.string(buffer,n)
    end
    api.write=function(addr,bytes)
        assert(#bytes==1,'only a single instruction-immediate byte may be written')
        local allowed=false
        for _,s in ipairs(SITES) do
            if addr==base+s.rva+s.offset and (bytes:byte()==s.value or bytes==s.bytes:sub(s.offset+1,s.offset+1)) then allowed=true end
        end
        assert(allowed,'write outside the five verified code sites')
        local ptr=ffi.cast('void *',addr)
        assert(kernel.VirtualProtect(ptr,1,0x40,oldprotect)~=0,'VirtualProtect failed')
        local protection=protections[addr] or tonumber(oldprotect[0])
        protections[addr]=protection
        count[0]=0
        local wrote=kernel.WriteProcessMemory(process,ptr,ffi.cast('const void *',bytes),1,count)~=0 and tonumber(count[0])==1
        local restored=kernel.VirtualProtect(ptr,1,protection,oldprotect)~=0
        if restored then protections[addr]=nil end
        local flushed=kernel.FlushInstructionCache(process,ptr,1)~=0
        assert(wrote and restored and flushed,'Code write/protection/cache operation failed')
    end
    api.backup=function(text) save('original_code.txt',text) end
    local success,n=pcall(Core.apply,api,base)
    local protection_error=false
    for addr,protection in pairs(protections) do
        if kernel.VirtualProtect(ffi.cast('void *',addr),1,protection,oldprotect)==0 then protection_error=true end
    end
    assert(not protection_error,'Page protection restoration failed; restart the game before continuing')
    if not success then error(n) end
    status('APPLIED','Five rendering comparisons verified; changed '..n..' bytes. In-game behavior needs testing; discovery data was not written.')
end
local original=rawget(_G,'update')
if type(original)~='function' then status('FAILED','update unavailable');return end
local worker=coroutine.create(setup)
local wrapper
wrapper=function(...)
    if worker then
        state.frames=state.frames+1
        if state.frames>=120 then
            local ok,message=coroutine.resume(worker)
            if not ok then status('FAILED',tostring(message));worker=nil
            elseif coroutine.status(worker)=='dead' then worker=nil end
            if not worker and rawget(_G,'update')==wrapper then _G.update=original end
        end
    end
    return original(...)
end
_G.update=wrapper
return state
