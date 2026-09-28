-- HD2-Addon: mods/astla/map_reveal_probe
-- Read-only investigation build. Never writes game memory or calls game actions.
local Core = {}
local function u32(s, i)
    local a,b,c,d = s:byte(i,i+3)
    if not d then return nil end
    return a+b*256+c*65536+d*16777216
end
Core.u32 = u32
Core.signatures = {
    ShowOnMapComponentData = 'LDLD\1\0\0\0\9\229\183\39',
    ObjectiveComponentData = 'LDLD\1\0\0\0\40\101\89\68',
}
function Core.scan(reader, regions, emit, checkpoint, self_ranges)
    local found, total = {}, 0
    for _,r in ipairs(regions) do
        local at, tail = r.base, ''
        while at < r.base+r.size do
            checkpoint()
            local n = math.min(262144, r.base+r.size-at)
            total = total+n
            if total > 6*1024*1024*1024 then return found,'byte_limit' end
            local ok, bytes = pcall(reader,at,n)
            if ok and type(bytes)=='string' and #bytes==n then
                local combined, start = tail..bytes, at-#tail
                for name,sig in pairs(Core.signatures) do
                    if not found[name] then
                        local pos=1
                        while true do
                            local hit=combined:find(sig,pos,true)
                            if not hit then break end
                            pos=hit+1
                            local addr=start+hit-1
                            local own=false
                            for _,range in ipairs(self_ranges or {}) do
                                if addr >= range[1] and addr < range[2] then own=true end
                            end
                            if not own then
                                local good,head=pcall(reader,addr,24)
                                local size=good and type(head)=='string' and #head==24 and u32(head,13)
                                if size and size>0 and size<=2*1024*1024 then
                                    -- Dump candidates even if layout differs. No write decisions here.
                                    local success = emit(name,addr,size+24)
                                    if success then found[name]={address=addr,size=size} end
                                end
                            end
                            if found[name] then break end
                        end
                    end
                end
                if found.ShowOnMapComponentData and found.ObjectiveComponentData then
                    return found,'found_pair'
                end
                tail=combined:sub(-11)
            else tail='' end
            at=at+n
        end
    end
    return found,'scan_complete'
end
if rawget(_G,'HD2MapProbeTest') then return Core end
if rawget(_G,'HD2MapRevealProbe') then return end
local state={frame=0,phase='starting',captures=0,retired=false}
_G.HD2MapRevealProbe=state
local localapp=os.getenv('LOCALAPPDATA')
if not localapp then return end
local out=localapp..'\\Hd2MapRevealProbe'
local function write(name,data)
    local f,err=io.open(out..'\\'..name,'wb')
    if not f then error(err) end
    assert(f:write(data)); assert(f:close())
end
local function status(phase,detail)
    if state.phase==phase and state.detail==detail then return end
    state.phase,state.detail=phase,detail
    pcall(write,'STATUS.txt',phase..' - '..(detail or '')..'\r\nRead-only probe 0.1.0; captures='..state.captures..'\r\n')
end
local ok,err=pcall(function()
    local ffi=require('ffi')
    ffi.cdef[[
        typedef struct { void *BaseAddress; void *AllocationBase; unsigned long AllocationProtect;
            unsigned short PartitionId; size_t RegionSize; unsigned long State;
            unsigned long Protect; unsigned long Type; } HD2MRP_MBI;
        void *GetCurrentProcess(void);
        int ReadProcessMemory(void *, const void *, void *, size_t, size_t *);
        size_t VirtualQuery(const void *, HD2MRP_MBI *, size_t);
        void *GetModuleHandleA(const char *);
        unsigned long GetModuleFileNameA(void *, char *, unsigned long);
        unsigned long GetTickCount(void);
        int CreateDirectoryA(const char *, void *);
    ]]
    local kernel=ffi.load('kernel32')
    kernel.CreateDirectoryA(out,nil)
    state.ffi,state.kernel=ffi,kernel
    state.process=kernel.GetCurrentProcess()
    state.buffer=ffi.new('unsigned char[262144]')
    state.count=ffi.new('size_t[1]')
    state.mbi=ffi.new('HD2MRP_MBI[1]')
    state.now=function() return tonumber(kernel.GetTickCount())/1000 end
    state.read=function(addr,n)
        if n<1 or n>262144 then return nil end
        state.count[0]=0
        if kernel.ReadProcessMemory(state.process,ffi.cast('const void *',addr),state.buffer,n,state.count)==0 then return nil end
        if tonumber(state.count[0])~=n then return nil end
        return ffi.string(state.buffer,n)
    end
    local loader=rawget(_G,'CowboyBingusModLoader')
    if type(loader)=='table' and tonumber(loader.api) and loader.api<1 then error('Bingus Shared Loader API 1 required') end
    state.module=tonumber(ffi.cast('uintptr_t',kernel.GetModuleHandleA('game.dll')))
    if not state.module or state.module==0 then error('game.dll not loaded') end
    local filename=ffi.new('char[32768]')
    if kernel.GetModuleFileNameA(ffi.cast('void *',state.module),filename,32768)==0 then error('module filename unavailable') end
    write('MODULE.txt','base='..string.format('0x%X',state.module)..'\r\npath='..ffi.string(filename)..'\r\n')
    state.keyboard=rawget(_G,'stingray') and stingray.Keyboard
    if state.keyboard and type(state.keyboard.button_id)=='function' then
        local good,key=pcall(state.keyboard.button_id,'f8')
        if good then state.key=key end
    end
    assert(state.key~=nil,'F8 binding unavailable')
    status('READY','Enter a mission, open the map, then press F8 for a read-only capture')
end)
if not ok then status('FAILED',tostring(err)); return end

local function api_inventory()
    local rows,seen={},{}
    local function visit(t,path,depth)
        if seen[t] or #rows>=12000 then return end
        seen[t]=true
        local key,value=next(t)
        while key~=nil and #rows<12000 do
            if type(key)=='string' then
                local p=path..'.'..key
                rows[#rows+1]=p..' : '..type(value)
                if type(value)=='table' and depth<2 and key~='_G' and key~='package' then visit(value,p,depth+1) end
            end
            state.checkpoint()
            key,value=next(t,key)
        end
    end
    visit(_G,'_G',0)
    table.sort(rows)
    write('API_NAMES.txt',table.concat(rows,'\r\n'))
end
local function dump_range(name,addr,size)
    local f=io.open(out..'\\'..name,'wb')
    if not f then return false end
    state.active_file=f
    local done=0
    while done<size do
        state.checkpoint()
        local n=math.min(65536,size-done)
        local bytes=state.read(addr+done,n)
        if not bytes or not f:write(bytes) then f:close(); state.active_file=nil; return false end
        done=done+n
    end
    local closed=f:close()~=nil
    state.active_file=nil
    return closed
end
local function capture()
    local prefix=string.format('capture_%02d_',state.captures)
    local notes={}
    -- Code/rdata once, writable static sections each capture. Never follows arbitrary heap pointers.
    local dos=assert(state.read(state.module,64),'DOS header unreadable')
    assert(dos:sub(1,2)=='MZ','bad DOS header')
    local peoff=assert(u32(dos,61)); assert(peoff<1048576,'invalid PE offset')
    local pe=assert(state.read(state.module+peoff,264),'PE header unreadable')
    assert(pe:sub(1,4)=='PE\0\0','bad PE header')
    local sections=pe:byte(7)+pe:byte(8)*256
    local optsize=pe:byte(21)+pe:byte(22)*256
    assert(sections>0 and sections<=96 and optsize<=4096,'invalid PE geometry')
    local headers=assert(state.read(state.module+peoff+24+optsize,sections*40))
    local module_bytes,module_complete=0,true
    for i=0,sections-1 do
        local p=i*40+1
        local name=headers:sub(p,p+7):gsub('%z.*','')
        local size,rva,flags=u32(headers,p+8),u32(headers,p+12),u32(headers,p+36)
        local readable=math.floor(flags/1073741824)%2==1
        local writable=math.floor(flags/2147483648)%2==1
        notes[#notes+1]=string.format('section=%s rva=0x%X size=%d flags=0x%X',name,rva,size,flags)
        if readable and size>0 and (not state.module_dumped or writable) then
            module_bytes=module_bytes+size
            assert(module_bytes<=96*1024*1024,'module dump limit reached')
            local filename=prefix..string.format('module_%02d_%08X.bin',i,rva)
            local success=dump_range(filename,state.module+rva,size)
            if not success then module_complete=false end
            notes[#notes+1]=filename..' complete='..tostring(success)
            write(prefix..'INDEX.txt',table.concat(notes,'\r\n'))
        end
    end
    if module_complete then state.module_dumped=true end
    if state.captures==1 then api_inventory() end
    local regions,at={},0
    while at<140737488355328 do
        state.checkpoint()
        local k,ffi=state.kernel,state.ffi
        if k.VirtualQuery(ffi.cast('const void *',at),state.mbi,ffi.sizeof(state.mbi[0]))==0 then break end
        local m=state.mbi[0]
        local base=tonumber(ffi.cast('uintptr_t',m.BaseAddress))
        local size,prot=tonumber(m.RegionSize),tonumber(m.Protect)
        if size<=0 or base+size<=at then break end
        local low=prot%256
        if tonumber(m.State)==4096 and math.floor(prot/256)%2==0 and
           (low==2 or low==4 or low==8 or low==32 or low==64 or low==128) then
            regions[#regions+1]={base=base,size=size}
        end
        at=base+size
    end
    table.sort(regions,function(a,b) return a.size>b.size end)
    local self_ranges={}
    for _,sig in pairs(Core.signatures) do
        local address=tonumber(state.ffi.cast('uintptr_t',state.ffi.cast('const char *',sig)))
        self_ranges[#self_ranges+1]={address-4096,address+4096}
    end
    local found,reason=Core.scan(state.read,regions,function(name,address,size)
        local filename=prefix..name..string.format('_%X.bin',address)
        local success=dump_range(filename,address,size)
        notes[#notes+1]=filename..' complete='..tostring(success)
        write(prefix..'INDEX.txt',table.concat(notes,'\r\n'))
        return success
    end,state.checkpoint,self_ranges)
    notes[#notes+1]='scan_end='..reason
    notes[#notes+1]='tables='..tostring(found.ShowOnMapComponentData~=nil)..','..tostring(found.ObjectiveComponentData~=nil)
    write(prefix..'INDEX.txt',table.concat(notes,'\r\n'))
    status('CAPTURED','Read-only capture '..state.captures..' complete; '..reason..'; F8 captures again (maximum 4)')
end
local function start()
    if state.worker or state.captures>=4 then return end
    state.captures=state.captures+1
    state.started=state.now()
    state.worker=coroutine.create(capture)
    status('CAPTURING','Read-only capture '..state.captures..' running')
end
state.checkpoint=function()
    if state.now()-state.started>180 then error('capture timeout; partial files retained') end
    state.ops=state.ops+1
    if os.clock()>=state.deadline or state.ops>=32 then coroutine.yield() end
end
local original=rawget(_G,'update')
if type(original)~='function' then status('FAILED','update hook unavailable'); return end
local wrapper
local function retire()
    state.retired=true
    if rawget(_G,'update')==wrapper then _G.update=original end
end
local function tick()
    state.frame=state.frame+1
    if state.key and state.keyboard then
        local good,down=pcall(state.keyboard.button,state.key)
        down=good and (down==true or (type(down)=='number' and down>0))
        if down and not state.key_down then start() end
        state.key_down=down
    end
    if state.worker and state.frame%2==0 then
        state.deadline,state.ops=os.clock()+0.002,0
        local good,message=coroutine.resume(state.worker)
        if not good then
            if state.active_file then pcall(function() state.active_file:close() end); state.active_file=nil end
            state.worker=nil
            status('FAILED',tostring(message)..'; F8 retries within capture limit')
        elseif coroutine.status(state.worker)=='dead' then state.worker=nil end
    end
    if state.captures>=4 and not state.worker then retire() end
end
wrapper=function(...)
    if not state.retired then
        local success,message=pcall(tick)
        if not success then status('FAILED',tostring(message)); retire() end
    end
    return original(...)
end
_G.update=wrapper
return state
