local Probe={}
function Probe.layout(view,index,width,height)
    local step=math.max(1,math.min(width/1920,height/1080))
    local gap=24*step;local size=16*step
    local inside_x=view.cx-72*step
    local inside_y=view.cy+(index-4.5)*gap
    local outside_x=24*step
    local outside_y=24*step+(index-1)*gap
    return {inside_x,inside_y,outside_x,outside_y,size,gap}
end
function Probe.new(api,read,base,out)
    local state={enabled=false,entries={},key=api.Keyboard.button_id('f8'),layers={-16381,0,100,401,403,16381}}
    local function save(name,data)
        local file=io.open(out..'\\FOG_'..name,'wb')
        if file then file:write(data);file:close() end
    end
    local function exists(list,world)
        for _,entry in pairs(list) do if entry==world then return true end end
        return false
    end
    function state:clear(list)
        for _,entry in ipairs(self.entries) do
            if exists(list,entry.world) then
                pcall(api.World.destroy_gui,entry.world,entry.gui)
            end
        end
        self.entries={};self.signature=nil
    end
    function state:key_tick(list)
        local value=api.Keyboard.button(self.key)
        local down=value==true or (type(value)=='number' and value>0)
        if down and not self.down then
            self.enabled=not self.enabled;self.captured=false
            self:clear(list)
            save('STATUS.txt',self.enabled and 'F8 probe armed; open native minimap\n' or 'F8 probe off; all diagnostic GUIs removed\n')
        end
        self.down=down
    end
    local function pointer(bytes)
        assert(bytes and #bytes==8,'UI owner read failed')
        local n=0
        for i=8,1,-1 do n=n*256+bytes:byte(i) end
        assert(n>=65536 and n<140737488355328 and n%4==0,'invalid UI owner')
        return n
    end
    function state:backend(lines)
        local function u32(b,o)
            local a,c,d,e=b:byte(o+1,o+4);assert(e,'short field');return a+c*256+d*65536+e*16777216
        end
        local function ptr(b,o)
            local n=u32(b,o)+u32(b,o+4)*4294967296
            assert(n>=65536 and n<140737488355328 and n%4==0,'invalid backend pointer');return n
        end
        local ok,error=pcall(function()
            local root=assert(read(base+0x3326308,8))
            local owner=ptr(root,0)
            local head=assert(read(owner,0xe0));save('backend_owner.bin',head)
            local table_address=ptr(head,0xd0)
            local methods=assert(read(table_address,0x248));save('backend_methods.bin',methods)
            for _,spec in ipairs({{'rect',0x108},{'bitmap_create',0x138},{'bitmap_update',0x140}}) do
                local address=ptr(methods,spec[2])
                local bytes=assert(read(address,1024),'backend code unreadable')
                save('backend_'..spec[1]..'.bin',bytes)
                lines[#lines+1]=string.format('backend.%s.address=0x%x',spec[1],address)
            end
            assert(read(base+0x3326308,8)==root,'backend changed')
        end)
        if not ok then lines[#lines+1]='backend.error='..tostring(error) end
    end
    function state:native_widgets(map,lines)
        local function u32(b,o)
            local a,c,d,e=b:byte(o+1,o+4)
            assert(e,'short native field');return a+c*256+d*65536+e*16777216
        end
        local offsets={[3]=0x148,[4]=0x1a8,[7]=0x2a8,[8]=0x2a8,[9]=0x470,[10]=0x1148,[11]=0x148,[13]=0x138}
        for _,spec in ipairs({{'spore_bitmap',0x637b8},{'spore_parent',0x636a8},
            {'map_bitmap',0x5ab40},{'map_container',0x4bf50}}) do
            local ok,error=pcall(function()
                local data=assert(read(map+spec[2],0x1160),'widget unavailable')
                save(spec[1]..'.bin',data)
                local flags=u32(data,0)
                local kind=math.floor(flags/262144)%16
                local bucket=math.floor(flags/536870912)%8
                local depth=data:byte(0xbd)+data:byte(0xbe)*256
                lines[#lines+1]=string.format('native.%s=kind:%d bucket:%d order:%d flags:0x%08x',spec[1],kind,bucket,depth,flags)
                local offset=offsets[kind]
                if offset then
                    local bytes=data:sub(offset+1,offset+8)
                    local n=0;for i=8,1,-1 do n=n*256+bytes:byte(i) end
                    if n>=65536 and n<140737488355328 and n%4==0 then
                        local material=read(n,256)
                        if material then save(spec[1]..'_material.bin',material);lines[#lines+1]='native.'..spec[1]..'.material=captured256' end
                    end
                end
            end)
            if not ok then lines[#lines+1]='native.'..spec[1]..'.error='..tostring(error) end
        end
    end
    function state:capture(list,view,width,height,overlay)
        local lines={'Fog probe 0.3; '..os.date('%Y-%m-%d %H:%M:%S'),
            'screen='..width..','..height,'main_world='..tostring(api.Application.main_world()),
            'overlay_world='..tostring(overlay.world),'last_render_world='..tostring(overlay.last_render_world),
            'lua_render_order='..tostring(overlay.render_signature),
            'columns: -16381,0,100,401,403,16381; colors repeat white,magenta,cyan; rows=world index',
            'inside=map center ladder; outside=bottom-left screen ladder; all alpha255'}
        for key,value in pairs(view) do lines[#lines+1]='view.'..key..'='..tostring(value) end
        local count=0
        for _,world in pairs(list) do
            count=count+1;if count>8 then lines[#lines+1]='worlds truncated at8';break end
            lines[#lines+1]='world.'..count..'='..tostring(world)
        end
        for _,name in ipairs({'update','render'}) do
            local fn=rawget(_G,name)
            local ok,info=pcall(function()return debug.getinfo(fn,'S')end)
            if ok and info then lines[#lines+1]=name..'_source='..tostring(info.source)..':'..tostring(info.linedefined) end
        end
        local ok,err=pcall(function()
            local root=assert(read(base+0x346d538,8))
            local map=pointer(root)+0x24e340+0x1a0e28
            for _,spec in ipairs({{'presenter.bin',0x120,0xc8},{'container.bin',0x4bf50,0xa0},
                {'map_mode.bin',0x636a0,32},{'fog_flags.bin',0x64660,32}}) do
                local bytes=assert(read(map+spec[2],spec[3]),spec[1]..' unreadable')
                save(spec[1],bytes)
                lines[#lines+1]=string.format('capture.%s=presenter+0x%x length=%d',spec[1],spec[2],#bytes)
            end
            self:native_widgets(map,lines)
            self:backend(lines)
            assert(read(base+0x346d538,8)==root,'UI owner changed')
        end)
        if not ok then lines[#lines+1]='capture_error='..tostring(err) end
        save('SUMMARY.txt',table.concat(lines,'\n')..'\n')
    end
    function state:draw(list,view,width,height,overlay)
        if not self.enabled or not view then self:clear(list);return end
        if not self.captured then self:capture(list,view,width,height,overlay);self.captured=true end
        local keys={view.cx,view.cy,width,height}
        for _,world in pairs(list) do keys[#keys+1]=tostring(world) end
        for i,v in ipairs(keys) do keys[i]=tostring(v) end
        local signature=table.concat(keys,':')
        if self.signature==signature then return end
        self:clear(list)
        local lines={};local count=0
        for _,world in pairs(list) do
            count=count+1;if count>8 then break end
            local ok,err=pcall(function()
                local gui=assert(api.World.create_screen_gui(world,'scale',1,1))
                self.entries[#self.entries+1]={gui=gui,world=world}
                local layout=Probe.layout(view,count,width,height)
                local colors={{255,255,255,255},{255,255,0,255},{255,0,255,255}}
                for _,start in ipairs({{layout[1],layout[2]},{layout[3],layout[4]}}) do
                    for col,layer in ipairs(self.layers) do
                        local x=start[1]+(col-1)*layout[6]
                        local y=start[2];local size=layout[5]
                        assert(api.Gui.rect(gui,api.Vector3(x-2,y-2,layer-1),api.Vector2(size+4,size+4),api.Color(255,0,0,0)))
                        local c=colors[(col-1)%3+1]
                        assert(api.Gui.rect(gui,api.Vector3(x,y,layer),api.Vector2(size,size),api.Color(c[1],c[2],c[3],c[4])))
                    end
                end
            end)
            lines[#lines+1]='world.'..count..'='..tostring(world)..' '..(ok and 'samples created' or tostring(err))
        end
        self.signature=signature
        save('DRAW.txt',table.concat(lines,'\n')..'\n')
        save('STATUS.txt','F8 probe visible; F8 toggles off; close map clears samples\n')
    end
    return state
end
return Probe
