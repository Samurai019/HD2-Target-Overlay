local Core={}
-- Exact entity resource, compared as bytes to avoid Lua's 64-bit precision loss.
local STALKER_LAIR=string.char(0xa9,0xf3,0xb1,0xf3,0x3e,0x69,0x1d,0xb5)
-- Verified draw order above the native spore mask.
Core.layers={outline=402,symbol=403}
function Core.after_update(previous,after,...)
    local function finish(...) after();return ... end
    return finish(previous(...))
end
local function u32(s,o)
    local a,b,c,d=s:byte(o+1,o+4)
    assert(d,'short uint32')
    return a+b*256+c*65536+d*16777216
end
local function ptr(s,o,label)
    local n=u32(s,o)+u32(s,o+4)*4294967296
    assert(n>=65536 and n<140737488355328 and n%4==0,(label or 'pointer')..string.format(' invalid: 0x%x',n))
    return n
end
local function f32(s,o)
    local b=u32(s,o);local sign=b>=2147483648 and -1 or 1
    local exp=math.floor(b/8388608)%256;local mant=b%8388608
    if exp==255 then return nil end
    if exp==0 then return sign*mant*2^-149 end
    return sign*(1+mant/8388608)*2^(exp-127)
end
function Core.snapshot(read,base)
    local rows,identity={},{}
    local specs={{rva=0x3326590,count=12,array=72,stride=20,kind='marker'},
                 {rva=0x3326da0,count=36,array=104,stride=100,kind='objective'}}
    for _,s in ipairs(specs) do
        local root=assert(read(base+s.rva,8),'manager unavailable')
        local address=ptr(root,0)
        local head=assert(read(address,112),'header unavailable')
        local count=u32(head,s.count)
        assert(count<=512,'unexpected record count')
        identity[#identity+1]=root
        if count>0 then
            local data=ptr(head,s.array)
            local bytes=assert(read(data,count*s.stride),'coordinates unavailable')
            for i=0,count-1 do
                local x,y=f32(bytes,i*s.stride),f32(bytes,i*s.stride+4)
                if x and y and math.abs(x)<100000 and math.abs(y)<100000 then
                    -- Native objective state lives at +0x20 in each 100-byte
                    -- coordinate/network record. Success is exactly state 2;
                    -- discovery/render fields +0x40/+0x44 are independent.
                    local objective_state=s.kind=='objective' and u32(bytes,i*s.stride+0x20) or nil
                    rows[#rows+1]={x=x,y=y,kind=s.kind,index=i,
                        objective_state=objective_state,completed=objective_state==2,
                        discovered=s.kind=='objective' and u32(bytes,i*s.stride+0x44)==0 or false,
                        reveal_state=s.kind=='objective' and u32(bytes,i*s.stride+0x44) or nil}
                end
            end
        end
        assert(read(base+s.rva,8)==root and read(address,112)==head,'scene changed during read')
    end
    return rows,table.concat(identity)
end
-- Classify records from native component metadata, without changing discovery.
function Core.classify_objectives(read,base,rows,identity)
    local root=assert(read(base+0x3326da0,8),'objective root unavailable')
    assert(not identity or root==identity:sub(9,16),'objective scene changed')
    local address=ptr(root,0)
    local head=assert(read(address,112),'objective header unavailable')
    local count=u32(head,36);assert(count<=512,'unexpected objective count')
    if count>0 then
        local cache=ptr(head,96,'objective cache')
        -- Native objective renderer uses the entity handle array at +0x50.
        -- Missing/empty handles must not disable ordinary side objectives.
        local handles_ok,handles=pcall(function()
            return assert(read(ptr(head,80,'objective entity array'),count*8))
        end)
        for _,row in ipairs(rows) do
            if row.kind=='objective' and row.index<count then
                row.importance=u32(assert(read(cache+row.index*0x1078+0x1038,4),'objective importance unavailable'),0)
                row.stalker_lair=false;row.resource=nil
                if handles_ok then
                    local valid,unit=pcall(ptr,handles,row.index*8)
                    local resource=valid and read(unit,8) or nil
                    row.resource=resource
                    row.stalker_lair=resource==STALKER_LAIR
                end
            end
        end
    end
    assert(read(base+0x3326da0,8)==root and read(address,112)==head,'objective scene changed')
    return rows
end
function Core.classify_pois(read,base,rows,identity)
    local marker_root=assert(read(base+0x3326590,8))
    assert(not identity or marker_root==identity:sub(1,8),'marker scene changed before classification')
    local marker=ptr(marker_root,0)
    local mh=assert(read(marker,112))
    local handles=u32(mh,12)>0 and assert(read(ptr(mh,56,'POI entity array'),u32(mh,12)*8)) or ''
    local registry_root=assert(read(base+0x346bf98,8))
    local registry=ptr(registry_root,0,'component registry')
    local table_root=assert(read(registry+0xf128c8,8))
    local settings=assert(read(ptr(table_root,0,'POI component table'),2080))
    local flags=u32(mh,12)>0 and assert(read(ptr(mh,80,'POI flags'),u32(mh,12)*24)) or ''
    local small={}
    for i=0,51 do
        local index=u32(settings,i*16+8)
        if index<26 then
            local offset=832+index*48
            local sx,sy=f32(settings,offset+24),f32(settings,offset+28)
            if settings:byte(offset+41)==1 and settings:byte(offset+33)==0 and
                sx and sy and sx>0 and sy>0 and sx<=32 and sy<=32 then
                small[settings:sub(i*16+1,i*16+8)]=true
            end
        end
    end
    for _,row in ipairs(rows) do
        if row.kind=='marker' then
            -- Manager storage can contain empty entity slots. They are not POIs.
            local valid,unit=pcall(ptr,handles,row.index*8)
            local resource=valid and read(unit,8) or nil
            row.small_poi=resource~=nil and small[resource]==true
            row.discovered=flags:byte(row.index*24+1)==1
        end
    end
    assert(read(base+0x3326590,8)==marker_root and read(marker,112)==mh and
        read(base+0x346bf98,8)==registry_root and read(registry+0xf128c8,8)==table_root,
        'POI scene changed during classification')
    return rows
end
function Core.classify(read,base,rows,identity)
    Core.classify_objectives(read,base,rows,identity)
    Core.classify_pois(read,base,rows,identity)
    return rows
end
function Core.mission_rows(read,base,credits,options)
    local rows,identity=Core.snapshot(read,base)
    local errors={}
    local ok,message=pcall(Core.classify_objectives,read,base,rows,identity)
    if not ok then
        errors[#errors+1]='SIDE: '..tostring(message)
        for _,row in ipairs(rows) do row.importance=nil;row.stalker_lair=false end
    end
    local post_ok,posts,post_errors=pcall(Core.outposts,read,base)
    if not post_ok then errors[#errors+1]='OUTPOST: '..tostring(posts);posts={} end
    if post_ok and post_errors and post_errors~='' then errors[#errors+1]='OUTPOST: '..post_errors end
    return Core.filter(rows,credits,posts,options),table.concat(errors,'\n')
end
function Core.outpost_types(read,base)
    -- +0x2a0 is a byte, so at most 256 entries are addressable. The supported
    -- build's static table ends in a zero record; 21 was only a partial dump.
    local bytes=assert(read(base+0x32fcde0,256*32),'outpost types unavailable')
    local types={}
    for category=0,255 do
        local settings=bytes:sub(category*32+1,category*32+32)
        assert(#settings==32,'short outpost settings')
        if settings==string.rep('\0',32) then
            assert(category>0,'empty outpost type table')
            return types,category,bytes:sub(1,category*32)
        end
        local inner,outer=f32(settings,16),f32(settings,20)
        assert((category==0 or settings:sub(1,8)~=string.rep('\0',8)) and
            settings:byte(13)<=1 and settings:byte(14)<=1 and
            inner and outer and inner>=0 and outer>=inner and outer<=100000,
            'invalid outpost type settings')
        types[category]=settings
    end
    error('outpost type table has no terminator')
end
function Core.outposts(read,base)
    local root=assert(read(base+0x33265c0,8))
    local manager=ptr(root,0)
    local head=assert(read(manager,112))
    local count=u32(head,12);assert(count<=128,'unexpected outpost count')
    local rows,errors={},{}
    if count>0 then
        local cache,network=ptr(head,72,'outpost cache'),ptr(head,80,'outpost network')
        local types=Core.outpost_types(read,base)
        for i=0,count-1 do
            local ok,row=pcall(function()
                local position=assert(read(cache+i*0x2b8,0x2b8))
                local state=assert(read(network+i*64,64),'outpost state unavailable')
                local category=position:byte(0x2a1)
                assert(category and types[category],'unexpected outpost type')
                -- Settings +0xc only suppress the native map widget. Hidden
                -- outposts still need an overlay; identify real types by their
                -- icon resource instead (the empty type has a zero resource).
                local settings=types[category]
                local valid_type=settings:sub(1,8)~=string.rep('\0',8)
                local native_hidden=settings:byte(13)~=0
                -- Native status mask 913384 and cleared-count 913491 both
                -- gate on cache +0x2ab. Mission-attached locations are excluded
                -- there even when they contain destructible spawners.
                local counts_as_outpost=position:byte(0x2ac)~=0
                local discovered=state:byte(0x3c)==1
                -- Native renderer +0x39 selects the cleared-outpost appearance;
                -- discovery is a separate byte at +0x3b.
                local completed=state:byte(0x3a)~=0
                local x,y=f32(position,0),f32(position,4)
                if x and y and math.abs(x)<100000 and math.abs(y)<100000 and valid_type then
                    return {x=x,y=y,kind='outpost',discovered=discovered,category=category,index=i,
                        native_hidden=native_hidden,completed=completed,counts_as_outpost=counts_as_outpost}
                end
            end)
            if ok and row then rows[#rows+1]=row
            elseif not ok then errors[#errors+1]=string.format('record %d: %s',i,tostring(row)) end
        end
    end
    assert(read(base+0x33265c0,8)==root and read(manager,112)==head,'outposts changed during read')
    return rows,table.concat(errors,'\n')
end
-- Manual, bounded capture for missing faction outposts; no address-space scan.
function Core.outpost_diagnostic(read,base,options,view)
    local lines={'Target Overlay 1.1.10 HUD curve diagnostic',
        'outposts_enabled='..tostring(options and options.outposts)}
    local function hex(bytes)
        return bytes and (bytes:gsub('.',function(c)return string.format('%02x',c:byte())end)) or 'UNREADABLE'
    end
    local ok,message=pcall(function()
        local root=assert(read(base+0x33265c0,8),'outpost root unavailable')
        local manager=ptr(root,0)
        local head=assert(read(manager,112),'outpost header unavailable')
        local count=u32(head,12)
        lines[#lines+1]=string.format('manager=0x%x count=%d',manager,count)
        lines[#lines+1]='header_hex='..hex(head)
        local _,type_count,types=Core.outpost_types(read,base)
        lines[#lines+1]='type_count='..type_count
        lines[#lines+1]='types_hex='..hex(types)
        if count>0 then
            local cache,network=ptr(head,72,'outpost cache'),ptr(head,80,'outpost network')
            lines[#lines+1]=string.format('cache=0x%x network=0x%x capture_limit=128',cache,network)
            for i=0,math.min(count,128)-1 do
                local position=read(cache+i*0x2b8,0x2b8)
                local state=read(network+i*64,64)
                lines[#lines+1]=string.format('record=%d position_hex=%s network_hex=%s',i,hex(position),hex(state))
            end
        end
        lines[#lines+1]='scene_consistent='..tostring(read(base+0x33265c0,8)==root and read(manager,112)==head)
    end)
    if not ok then lines[#lines+1]='CAPTURE_ERROR='..tostring(message) end
    local objective_ok,objective_error=pcall(function()
        local rows,identity=Core.snapshot(read,base)
        Core.classify_objectives(read,base,rows,identity)
        for _,row in ipairs(rows) do
            if row.kind=='objective' then
                lines[#lines+1]=string.format('objective=%d resource_hex=%s xy=(%.3f,%.3f) importance=%s stalker_lair=%s state=%s discovered=%s',
                    row.index,hex(row.resource),row.x,row.y,tostring(row.importance),tostring(row.stalker_lair),
                    tostring(row.objective_state),tostring(row.discovered))
            end
        end
    end)
    if not objective_ok then lines[#lines+1]='OBJECTIVE_CAPTURE_ERROR='..tostring(objective_error) end
    if view and view.map_address then
        for _,key in ipairs({'origin_x','origin_y','pan_x','pan_y','scale','cx','cy','radius','xx','xy','yx','yy','tx','ty','width','height','hud_curve','curve_error'}) do
            lines[#lines+1]='view_'..key..'='..tostring(view[key])
        end
        -- Separate native containers and actual outpost widget transforms let
        -- us distinguish a UI anchor offset from different world coordinates.
        for _,item in ipairs({{'outposts',0x4ece8},{'pois',0x4bf50},{'objectives_unknown',0xf838},{'objectives_discovered',0x14870}}) do
            lines[#lines+1]='container_'..item[1]..'_hex='..hex(read(view.map_address+item[2],0x110))
        end
        for i=0,31 do
            lines[#lines+1]=string.format('native_outpost_widget=%d hex=%s',i,hex(read(view.map_address+0x4ee00+i*0x160,0x160)))
        end
    end
    local valid,rows,errors=pcall(Core.outposts,read,base)
    if valid then
        lines[#lines+1]='parsed_count='..#rows
        for i,row in ipairs(rows) do
            local projected=view and Core.map_project({row},view) or {}
            lines[#lines+1]=string.format('parsed=%d type=%s xy=(%.3f,%.3f) discovered=%s cleared=%s type_hidden=%s keep=%s inside_map=%s counts_as_outpost=%s record=%d',
                i,tostring(row.category),row.x,row.y,tostring(row.discovered),tostring(row.completed),
                tostring(row.native_hidden),tostring(Core.keep_location(row)),tostring(view and #projected>0),
                tostring(row.counts_as_outpost),row.index)
        end
        if errors~='' then lines[#lines+1]='PARSE_ERRORS='..errors end
    else lines[#lines+1]='PARSE_ERROR='..tostring(rows) end
    return table.concat(lines,'\n')..'\n'
end
function Core.credit_positions(api,list,main,diagnostic)
    local resource=api.IdString64.from_hex('bd6f4de16b9aedcd')
    local points,seen,detail={},{},{}
    local worlds_seen=0
    for _,world in pairs(list) do
        worlds_seen=worlds_seen+1;assert(worlds_seen<=8,'too many worlds')
        local gameplay=main==nil or world==main
        if diagnostic then detail[#detail+1]=string.format('world=%d gameplay=%s',worlds_seen,tostring(gameplay)) end
        local units=api.World.units_by_resource(world,resource)
        assert(type(units)=='table','resource query unavailable')
        local count=0
        for _,unit in pairs(units) do
            count=count+1;assert(count<=128,'too many credit units')
            if not seen[unit] and api.Unit.alive(unit) then
                seen[unit]=true
                local root=api.Unit.world_position(unit,0)
                local rx,ry=api.Vector3.x(root),api.Vector3.y(root)
                local rz=api.Vector3.z and api.Vector3.z(root) or nil
                local node=0
                local note='root fallback'
                if api.Unit.has_node and api.Unit.node then
                    local name=api.IdString32 and api.IdString32.from_hex('e4a4586d') or 'interact'
                    local node_ok,result=pcall(function()
                        if api.Unit.has_node(unit,name) then return api.Unit.node(unit,name) end
                    end)
                    if node_ok and type(result)=='number' and result>=0 and result<256 then
                        node=result;note='interact'
                    elseif not node_ok then note='interact lookup failed: '..tostring(result) end
                end
                local position=api.Unit.world_position(unit,node)
                local x,y=api.Vector3.x(position),api.Vector3.y(position)
                local z=api.Vector3.z and api.Vector3.z(position) or nil
                if type(x)=='number' and type(y)=='number' and x==x and y==y and
                    math.abs(x)<100000 and math.abs(y)<100000 then
                    -- Observed three distinct units returning zero root positions.
                    -- A nearby bind-pose interaction offset does not resolve that ambiguity.
                    local unresolved=rx==0 and ry==0 and (rz==nil or rz==0) and x*x+y*y<1
                    local selected=gameplay and not unresolved
                    if diagnostic then detail[#detail+1]=string.format('  unit=%s root=(%s,%s,%s) node=%d %s position=(%.3f,%.3f,%s) selected=%s unresolved_origin=%s',
                        tostring(unit),tostring(rx),tostring(ry),tostring(rz),node,note,x,y,tostring(z),tostring(selected),tostring(unresolved)) end
                    if selected then points[#points+1]={x=x,y=y} end
                end
            end
        end
    end
    return points,table.concat(detail,'\n')
end
function Core.keep_location(row)
    if row.kind=='outpost' then return row.counts_as_outpost~=false and not row.completed end
    return not row.discovered
end
function Core.filter(rows,credits,outposts,options)
    options=options or {outposts=true,objectives=true,credits=true}
    local selected={}
    for _,row in ipairs(rows) do
        if options.objectives and row.kind=='objective' and row.importance==3 and Core.keep_location(row)
            and (not row.stalker_lair or not options.outposts) then
            selected[#selected+1]=row
        end
        -- This side objective is deliberately absent from the outpost count.
        -- Its own success state means all mission-required holes were cleared.
        if options.outposts and row.kind=='objective' and row.importance==3 and row.stalker_lair and not row.completed then
            selected[#selected+1]={x=row.x,y=row.y,kind='stalker_lair',stalker_lair=true,
                index=row.index,completed=false,counts_as_outpost=true}
        end
    end
    -- Model presence is the only credit criterion; pickup destroys the unit.
    for _,credit in ipairs(options.credits and credits or {}) do
        selected[#selected+1]={x=credit.x,y=credit.y,kind='credit_poi'}
    end
    for _,row in ipairs(options.outposts and outposts or {}) do if Core.keep_location(row) then selected[#selected+1]=row end end
    return selected
end
-- Optional Mod Options Menu API 1. Stable IDs key the menu's saved values.
Core.option_specs={
    {key='outposts',id='astla.target_overlay.outposts',label='标记虫巢',
        description='用红色六边形标记计入据点统计的虫巢、机器人哨站、飞碟据点；追踪虫巢穴使用专属红色八角星。发现后保留，清除后撤销；排除其他任务附带虫洞。'},
    {key='objectives',id='astla.target_overlay.objectives',label='标记支线',
        description='标记尚未发现的支线任务。发现后撤销白色标记。'},
    {key='credits',id='astla.target_overlay.credits',label='标记蓝币',
        description='标记已加载的超级货币模型。拾取后撤销蓝色标记。'}
}
function Core.menu_step(state,menu)
    if type(menu)~='table' or menu.api~=1 or type(menu.register_option)~='function' or
        type(menu.get)~='function' or type(menu.on_change)~='function' then return end
    if state.options_menu~=menu then
        state.options_menu=menu;state.option_links={};state.options_error=nil
    end
    local function apply(key,value)
        if type(value)=='boolean' and state.options[key]~=value then
            state.options[key]=value;state.rows=nil
        end
    end
    for _,spec in ipairs(Core.option_specs) do
        local link=state.option_links[spec.id]
        if link==nil then
            -- Registration failures are terminal for this API instance; don't
            -- retry each frame or let a broken optional menu stop the overlay.
            state.option_links[spec.id]=false
            local ok,result,reason=pcall(menu.register_option,spec.id,{type='toggle',mod='Target Overlay',
                label=spec.label,description=spec.description,default=true})
            if ok and result==true then
                local key=spec.key
                local hooked,accepted=pcall(menu.on_change,spec.id,function(value) apply(key,value) end)
                state.option_links[spec.id]=true
                if not hooked or accepted~=true then state.options_error='Menu callback unavailable: '..spec.id end
            else state.options_error='Menu registration failed: '..spec.id..': '..tostring(ok and reason or result) end
        end
        if state.option_links[spec.id] then
            -- Also covers saved values on registration and programmatic set(),
            -- which intentionally does not invoke menu callbacks.
            local ok,value=pcall(menu.get,spec.id)
            if ok then apply(spec.key,value) end
        end
    end
end
-- Native mission HUD is embedded in the UI owner; all reads are bounded.
function Core.map_view(read,base,width,height)
    local root=assert(read(base+0x346d538,8),'UI owner unavailable')
    local owner=ptr(root,0)
    local hud=owner+0x24e340
    local gate=assert(read(hud+0x58,1),'HUD gate unavailable')
    local ready=assert(read(hud+0x21f5b0,1),'HUD readiness unavailable')
    local map=hud+0x1a0e28
    local head=assert(read(map+0x120,0xc8),'map header unavailable')
    assert(u32(head,0x70)==400,'unexpected map presenter')
    local open=head:byte(0x76)==1 -- presenter +0x195, native open/close handlers
    if gate:byte(1)~=1 or ready:byte(1)~=1 or not open or head:byte(0x75)~=1 then return nil end
    local screens=ptr(assert(read(base+0x3326340,8),'screen manager unavailable'),0)
    if u32(assert(read(screens+0xac21c,4),'screen state unavailable'),0)~=4 then return nil end
    local modal=ptr(assert(read(base+0x347ce28,8),'modal owner unavailable'),0)
    local modal_state=assert(read(modal+0x4294,8),'modal state unavailable')
    if u32(modal_state,0)~=0 or u32(modal_state,4)~=0 then return nil end
    local function value(o)
        local v=assert(f32(head,o),'invalid map value')
        assert(math.abs(v)<100000,'map value out of range');return v
    end
    local view={origin_x=value(0),origin_y=value(4),pan_x=value(0x10),pan_y=value(0x14),
        scale=value(0x28),cx=value(0x9c),cy=value(0xa0),radius=value(0xa4),map_address=map,width=width,height=height}
    -- 12f3cc7 reads the live setting; 12f3ccf multiplies it by 0.15 for
    -- hud_curve_amount. Optional read: failure preserves the flat projection.
    local curve_ok,curve=pcall(function()
        local v=assert(f32(assert(read(screens+0xac4dc,4)),0),'invalid HUD curve')
        assert(v>=0 and v<=1,'HUD curve outside supported range');return v
    end)
    view.hud_curve=curve_ok and curve or 0
    view.curve_error=not curve_ok and tostring(curve) or nil
    -- Markers are children of the centered map container. Its X/Z matrix
    -- is already in screen pixels and includes the game's HUD scaling.
    local parent=assert(read(map+0x4bf50,0xa0),'map container unavailable')
    local function matrix(o)
        local v=assert(f32(parent,o),'invalid map matrix')
        assert(math.abs(v)<100000,'map matrix out of range');return v
    end
    view.xx,view.xy,view.yx,view.yy=matrix(0x64),matrix(0x84),matrix(0x6c),matrix(0x8c)
    view.container_x,view.container_y=matrix(0x94),matrix(0x9c)
    -- Widget matrices describe their lower-left origin, but native markers
    -- use a centered parent anchor. The map clip center is that anchor.
    view.tx,view.ty=view.cx,view.cy
    view.icon_scale=math.min(width/1920,height/1080)
    assert(view.scale>0 and view.scale<100 and view.radius>10 and view.radius<math.max(width,height), 'invalid map extent')
    assert(math.abs(view.xx*view.yy-view.xy*view.yx)>0.00001,'singular map matrix')
    assert(view.cx>=0 and view.cx<=width and view.cy>=0 and view.cy<=height,'map outside screen')
    assert(read(base+0x346d538,8)==root and read(map+0x120,0xc8)==head,'map changed during read')
    return view
end
-- Vertical HUD contraction fitted to five native icons at curve 0/.5/1.
-- Strength .15 is independently verified in the native parameter setter.
-- X is unchanged; contraction is strongest at the screen's horizontal center.
function Core.hud_warp(x,y,view,inverse)
    local amount=view.hud_curve or 0
    if amount==0 then return x,y end
    local nx=2*x/view.width-1
    local factor=1-0.15*amount*(1-nx*nx)
    local dy=y-view.height/2
    return x,view.height/2+(inverse and dy/factor or dy*factor)
end
function Core.calibration_points(view)
    local points={}
    for row=1,3 do for col=1,3 do
        local x=view.cx+(col-2)*view.radius*.55
        local y=view.cy+(2-row)*view.radius*.55
        local wx,wy=Core.hud_warp(x,y,view)
        points[#points+1]={id=(row-1)*3+col,x=x,y=y,wx=wx,wy=wy}
    end end
    return points
end
function Core.calibration_rects(view)
    local rects={};local scale=view.icon_scale or 1
    local raw={220,0,220,255};local warped={220,255,90,220}
    local digits={'010110010010111','110001010100111','110001010001110',
        '101101111001001','111100110001110','011100111101111',
        '111001010010010','111101111101111','111101111001110'}
    local function rect(x,y,w,h,color)
        rects[#rects+1]={x=x,y=y,w=w,h=h,color=color}
    end
    local function point(x,y,id,color)
        rect(x-7*scale,y-scale,14*scale,2*scale,color)
        rect(x-scale,y-7*scale,2*scale,14*scale,color)
        for i=1,15 do if digits[id]:sub(i,i)=='1' then
            local col=(i-1)%3;local row=math.floor((i-1)/3)
            rect(x+(10+col*2)*scale,y+(4-row*2)*scale,2*scale,2*scale,color)
        end end
    end
    -- The flat circle and predicted curved edge are visual references only.
    -- They intentionally show the difference from the native map boundary.
    for i=0,95 do
        local theta=i*math.pi/48
        local x=view.cx+view.radius*math.cos(theta)
        local y=view.cy+view.radius*math.sin(theta)
        local wx,wy=Core.hud_warp(x,y,view)
        rect(x-scale,y-scale,2*scale,2*scale,raw)
        rect(wx-scale,wy-scale,2*scale,2*scale,warped)
    end
    for _,p in ipairs(Core.calibration_points(view)) do
        point(p.x,p.y,p.id,raw);point(p.wx,p.wy,p.id,warped)
    end
    return rects
end
function Core.map_project(rows,view)
    local out={}
    for _,p in ipairs(rows) do
        local x=(p.x-view.origin_x+view.pan_x)*view.scale
        local y=(p.y-view.origin_y+view.pan_y)*view.scale
        local px=view.tx+x*view.xx+y*view.xy
        local py=view.ty+x*view.yx+y*view.yy
        local size=(p.kind=='stalker_lair' and 28 or (p.kind=='objective' and 22 or (p.kind=='marker' and 16 or 20)))*(view.icon_scale or 1)
        local half=size/2+4*(view.icon_scale or 1)
        px,py=Core.hud_warp(px,py,view)
        local inside=true
        -- Test actual GUI corners through the inverse deformation against the
        -- original circle, so the curved edge cannot expose outside markers.
        for _,sx in ipairs({-1,1}) do for _,sy in ipairs({-1,1}) do
            local cx,cy=Core.hud_warp(px+sx*half,py+sy*half,view,true)
            if (cx-view.cx)^2+(cy-view.cy)^2>view.radius^2 then inside=false end
        end end
        if inside then
            out[#out+1]={x=px,y=py,kind=p.kind,size=size,completed=p.completed==true}
        end
    end
    return out
end
function Core.marker_color(p)
    if p.kind=='credit_poi' then return {255,45,120,255} end
    if p.kind=='outpost' or p.kind=='stalker_lair' then return {255,255,45,55} end
    if p.kind=='objective' then return {255,255,255,255} end
    return {255,55,218,234}
end
-- Rasterize hollow polygons using the established rectangle GUI API.
function Core.glyph(kind,size,thickness,step)
    local count=kind=='outpost' and 6 or (kind=='credit_poi' and 3 or 4)
    local vertices={}
    if kind=='stalker_lair' then
        -- Eight outer tips, alternating with deep valleys; a hollow contour.
        for i=0,15 do
            local angle=math.pi/2+i*math.pi/8
            local radius=i%2==0 and 1 or 0.48
            vertices[#vertices+1]={math.cos(angle)*radius,math.sin(angle)*radius}
        end
    elseif count==4 then vertices={{-1,-1},{1,-1},{1,1},{-1,1}}
    elseif count==3 then vertices={{0,1},{-1,-1},{1,-1}}
    else vertices={{1,0},{0.5,0.866},{-0.5,0.866},{-1,0},{-0.5,-0.866},{0.5,-0.866}} end
    local function span(y,radius)
        local intersections={}
        for i,a in ipairs(vertices) do
            local b=vertices[i%#vertices+1]
            local ay,by=a[2]*radius,b[2]*radius
            if (ay<=y and by>y) or (by<=y and ay>y) then
                local x=a[1]*radius+(y-ay)*(b[1]-a[1])*radius/(by-ay)
                intersections[#intersections+1]=x
            end
        end
        -- A concave star can have multiple disconnected spans in one row.
        table.sort(intersections)
        local spans={}
        for i=1,#intersections-1,2 do spans[#spans+1]={intersections[i],intersections[i+1]} end
        return spans
    end
    local result={};local radius=size/2
    for y=-radius,radius-step,step do
        local inner=span(y+step/2,math.max(0,radius-thickness))
        for _,outer in ipairs(span(y+step/2,radius)) do
            local cursor,right=outer[1],outer[2]
            for _,hole in ipairs(inner) do
                if hole[2]>cursor and hole[1]<right then
                    local stop=math.min(right,hole[1])
                    if stop>cursor then result[#result+1]={cursor,y,stop-cursor,step} end
                    cursor=math.max(cursor,hole[2])
                end
            end
            if cursor<right then result[#result+1]={cursor,y,right-cursor,step} end
        end
    end
    return result
end
function Core.draw_key(projected)
    local keys={}
    for _,p in ipairs(projected) do
        keys[#keys+1]=string.format('%s:%.3f:%.3f:%.3f:%s',p.kind,p.x,p.y,p.size,tostring(p.completed==true))
    end
    return table.concat(keys,';')
end
function Core.project(rows,player)
    local xmin,xmax,ymin,ymax
    for _,p in ipairs(rows) do
        xmin=math.min(xmin or p.x,p.x);xmax=math.max(xmax or p.x,p.x)
        ymin=math.min(ymin or p.y,p.y);ymax=math.max(ymax or p.y,p.y)
    end
    if not xmin then return {} end
    if player then
        xmin=math.min(xmin,player.x);xmax=math.max(xmax,player.x)
        ymin=math.min(ymin,player.y);ymax=math.max(ymax,player.y)
    end
    local span=math.max(xmax-xmin,ymax-ymin,100)*1.12
    local cx,cy=(xmin+xmax)/2,(ymin+ymax)/2
    local out={}
    for _,p in ipairs(rows) do out[#out+1]={x=(p.x-cx)/span+0.5,y=(p.y-cy)/span+0.5,kind=p.kind} end
    if player then out[#out+1]={x=(player.x-cx)/span+0.5,y=(player.y-cy)/span+0.5,kind='player'} end
    return out
end
function Core.choose_world(list,main,last)
    for _,world in pairs(list) do if world==last then return world end end
    for _,world in ipairs(list) do if world~=main then return world end end
    return main
end
if rawget(_G,'HD2OverlayTest') then return Core end
if rawget(_G,'HD2TargetOverlay') then return end
local state={frame=0,enabled=true,ids={},phase='starting',options={outposts=true,objectives=true,credits=true}}
_G.HD2TargetOverlay=state
local function status(phase,message)
    if state.phase==phase and state.message==message then return end
    state.phase,state.message=phase,message

end
local ffi,crypto,kernel,base,read,sr
-- HASH_HELPER is inserted by build_overlay.py (read-only CryptoAPI SHA256).
-- HASH_HELPER
local function init()
    ffi=require('ffi')
    ffi.cdef[[
      void *GetCurrentProcess(void); void *GetModuleHandleA(const char *);
      unsigned long GetModuleFileNameA(void *,char *,unsigned long);
      int ReadProcessMemory(void *,const void *,void *,size_t,size_t *);
      int CryptAcquireContextA(uintptr_t *,const char *,const char *,unsigned long,unsigned long);
      int CryptCreateHash(uintptr_t,unsigned long,uintptr_t,unsigned long,uintptr_t *);
      int CryptHashData(uintptr_t,const unsigned char *,unsigned long,unsigned long);
      int CryptGetHashParam(uintptr_t,unsigned long,unsigned char *,unsigned long *,unsigned long);
      int CryptDestroyHash(uintptr_t);int CryptReleaseContext(uintptr_t,unsigned long);
    ]]
    kernel,crypto=ffi.load('kernel32'),ffi.load('advapi32')
    local loader=rawget(_G,'CowboyBingusModLoader')
    assert(type(loader)=='table' and tonumber(loader.api) and loader.api>=1,'Loader API 1 required')
    status('VERIFYING','Checking game build; no code or discovery writes')
    local handle=kernel.GetModuleHandleA('game.dll')
    base=tonumber(ffi.cast('uintptr_t',handle));assert(base and base>0,'game.dll unavailable')
    local path=ffi.new('char[32768]')
    assert(kernel.GetModuleFileNameA(handle,path,32768)>0,'module filename unavailable')
    assert(hash_file(ffi.string(path))=='2E2C3B7C2500646DADD5F2B4C6E0504DBB7E7896139F64CDDC0D1813C718F51E','Unsupported game build')
    local proc=kernel.GetCurrentProcess()
    local buffer,count=ffi.new('char[65536]'),ffi.new('size_t[1]')
    read=function(address,n)
        if n<1 or n>65536 then return nil end
        count[0]=0
        if kernel.ReadProcessMemory(proc,ffi.cast('const void *',address),buffer,n,count)==0 or tonumber(count[0])~=n then return nil end
        return ffi.string(buffer,n)
    end
    -- Refuse while the previous rendering patch is still active. Never undo it here.
    for _,s in ipairs(ORIGINAL_SITES) do assert(read(base+s.rva,#s.bytes)==s.bytes,'Old rendering patch/conflicting code still active; disable it and restart') end
    sr=rawget(_G,'stingray') or rawget(_G,'s3d');assert(sr and sr.Gui and sr.World,'GUI API unavailable')
    state.key=sr.Keyboard.button_id('f7')
    if OUTPOST_DIAGNOSTIC then
        state.capture_key=sr.Keyboard.button_id('f8')
        state.calibration_key=sr.Keyboard.button_id('f9')
    end
    status('READY','Overlay follows native minimap visibility; F7 enables/disables overlay')
end
local function worlds()
    local list=sr.Application.worlds()
    assert(type(list)=='table','world inventory unavailable')
    return list
end
local function live(list,world)
    for _,w in pairs(list) do if w==world then return true end end
    return false
end
local function capture_outposts()
    local loader=rawget(_G,'CowboyBingusModLoader')
    local directory=type(loader)=='table' and loader.log_directory
    if type(directory)~='string' then
        local localapp=os.getenv('LOCALAPPDATA')
        assert(localapp,'Diagnostic log directory unavailable')
        directory=localapp..'\\CowboyBingus\\Helldivers2\\Logs'
    end
    local width,height=sr.Gui.resolution()
    local valid,view=pcall(Core.map_view,read,base,width,height)
    local report=Core.outpost_diagnostic(read,base,state.options,valid and view or nil)
    state.capture_sequence=(state.capture_sequence or 0)+1
    report=report..'calibration_enabled='..tostring(state.calibration==true)..'\n'
        ..'captured_at='..os.date('%Y-%m-%d %H:%M:%S')..'\n'
    if valid and view then
        for _,p in ipairs(Core.calibration_points(view)) do
            report=report..string.format('calibration_point=%d flat=(%.3f,%.3f) trial=(%.3f,%.3f)\n',p.id,p.x,p.y,p.wx,p.wy)
        end
    end
    report=report..'map_open='..tostring(valid and view~=nil)..'\n'
        ..'overlay_enabled='..tostring(state.enabled)..'\n'
        ..'category_error='..tostring(state.category_error)..'\n'
        ..'snapshot_error='..tostring(state.snapshot_error)..'\n'
        ..'menu_error='..tostring(state.options_error)..'\n'
    local path=directory..'\\TargetOverlay_OUTPOST_DIAGNOSTIC.txt'
    local file,reason=io.open(path,'wb')
    if not file then state.capture_error=tostring(reason);return end
    local wrote,write_error=file:write(report)
    file:close()
    state.capture_error=not wrote and tostring(write_error) or nil
    state.capture_path=wrote and path or nil
    if wrote then
        local tag=valid and view and string.format('%.3f',view.hud_curve or 0) or 'unknown'
        local copy_path=directory..'\\TargetOverlay_HUD_'..os.date('%Y%m%d_%H%M%S')
            ..'_curve_'..tag..'_'..state.capture_sequence..'.txt'
        local copy,copy_reason=io.open(copy_path,'wb')
        if copy then
            local saved,save_reason=copy:write(report);copy:close()
            state.calibration_capture_path=saved and copy_path or nil
            if not saved then state.capture_error=tostring(save_reason) end
        else state.capture_error=tostring(copy_reason) end
    end
end
local function clear(list)
    if state.gui and live(list,state.world) then
        for _,id in ipairs(state.ids) do pcall(sr.Gui.destroy_rect,state.gui,id) end
    end
    state.ids={}
    state.last_draw=nil
end
local function release(list)
    clear(list)
    if state.gui and live(list,state.world) then pcall(sr.World.destroy_gui,state.world,state.gui) end
    state.gui,state.world=nil,nil
end
-- Render-world order is stronger evidence than world inventory order.
local function install_render_tracking()
    local application=sr.Application
    local original=application.render_world
    if type(original)~='function' then return end
    local tracer=function(world,...)
        if state.in_render then
            state.render_order[#state.render_order+1]=world
            state.last_render_world=world
        end
        return original(world,...)
    end
    local ok=pcall(function() application.render_world=tracer end)
    if not ok or application.render_world~=tracer then return end
    state.render_original,state.render_tracer=original,tracer
    local original_render=rawget(_G,'render')
    if type(original_render)=='function' then
        local render_wrapper
        render_wrapper=function(...)
            state.render_order={};state.in_render=true
            local function finish(...)
                state.in_render=false
                return ...
            end
            return finish(original_render(...))
        end
        state.global_render_original,state.global_render_wrapper=original_render,render_wrapper
        _G.render=render_wrapper
    end
end
local function draw(rows,view,list)
    local main=sr.Application.main_world()
    local target=Core.choose_world(list,main,state.last_render_world)
    if not target or not live(list,target) then return end
    if state.world~=target then release(list) end
    if not state.gui then state.gui=assert(sr.World.create_screen_gui(target,'scale',1,1));state.world=target end
    if OUTPOST_DIAGNOSTIC and state.calibration then
        local signature=table.concat({'calibration',view.cx,view.cy,view.radius,view.width,view.height,view.hud_curve or 0},':')
        if state.last_draw==signature then return end
        clear(list)
        for _,p in ipairs(Core.calibration_rects(view)) do
            local c=p.color
            local id=sr.Gui.rect(state.gui,sr.Vector3(p.x,p.y,Core.layers.symbol),
                sr.Vector2(p.w,p.h),sr.Color(c[1],c[2],c[3],c[4]))
            assert(id~=nil,'calibration rectangle creation failed');state.ids[#state.ids+1]=id
        end
        state.last_draw=signature
        return
    end
    local projected=Core.map_project(rows,view)
    local signature=Core.draw_key(projected)
    if state.last_draw==signature then return end
    clear(list)
    local function rect(px,py,w,h,c,layer)
        local id=sr.Gui.rect(state.gui,sr.Vector3(px,py,layer or 100),sr.Vector2(w,h),sr.Color(c[1],c[2],c[3],c[4]))
        assert(id~=nil,'rectangle creation failed');state.ids[#state.ids+1]=id
    end
    for _,p in ipairs(projected) do
        local px,py=p.x,p.y
        local size=p.size
        local edge=math.max(2,2*view.icon_scale)
        local color=Core.marker_color(p)
        local step=math.max(1,view.icon_scale)
        for _,spec in ipairs({{size+4*edge,4*edge,{255,0,0,0},Core.layers.outline},{size,edge,color,Core.layers.symbol}}) do
            for _,part in ipairs(Core.glyph(p.kind,spec[1],spec[2],step)) do
                if part[3]>0 then rect(px+part[1],py+part[2],part[3],part[4],spec[3],spec[4]) end
            end
        end
    end
    state.last_draw=signature
end
local function refresh()
    local list=worlds()
    if not state.enabled then clear(list);state.rows=nil;status('HIDDEN','F7 enables overlay');return end
    local width,height=sr.Gui.resolution()
    assert(type(width)=='number' and type(height)=='number' and width>0 and height>0,'invalid screen size')
    local valid,view=pcall(Core.map_view,read,base,width,height)
    if not valid or not view then
        clear(list)
        state.rows=nil
        local detail=not valid and tostring(view) or 'Native minimap closed or HUD hidden'
        status('MAP_HIDDEN',detail)
        return
    end
    if OUTPOST_DIAGNOSTIC and state.calibration then
        draw({},view,list);status('CALIBRATING','F9 closes calibration; F8 captures current HUD curve')
        return
    end
    local ok,rows=true,state.rows
    if not rows or state.frame%30==0 then
        ok,rows=pcall(function()
            local credit_ok,credits=true,{}
            if state.options.credits then credit_ok,credits=pcall(Core.credit_positions,sr,list,sr.Application.main_world()) end
            state.credit_error=not credit_ok and tostring(credits) or nil
            state.credit_count=credit_ok and #credits or 0
            local selected,errors=Core.mission_rows(read,base,credit_ok and credits or {},state.options)
            state.category_error=errors~='' and errors or nil
            return selected
        end)
        state.rows=ok and rows or nil
    end
    state.snapshot_error=not ok and tostring(rows) or state.category_error
    if not ok or #rows==0 then
        clear(list);status('WAITING','No validated mission coordinates; panel cleared');return
    end
    draw(rows,view,list)
    status('DRAWING','Minimap overlay active')
end
local previous=rawget(_G,'update')
if type(previous)~='function' then return end
local worker=coroutine.create(init)
local wrapper
local function tick()
    state.frame=state.frame+1
    if not state.options_menu or state.frame%30==0 then Core.menu_step(state,rawget(_G,'ModOptionsMenu')) end
    if worker then
        if state.frame<120 then return end
        local ok,message=coroutine.resume(worker)
        if not ok then error(message) end
        if coroutine.status(worker)=='dead' then worker=nil;install_render_tracking() end
        return
    end
    local down=sr.Keyboard.button(state.key)
    down=down==true or (type(down)=='number' and down>0)
    if down and not state.down then state.enabled=not state.enabled;state.frame=0 end
    state.down=down
    if OUTPOST_DIAGNOSTIC and state.calibration_key then
        local calibration_down=sr.Keyboard.button(state.calibration_key)
        calibration_down=calibration_down==true or (type(calibration_down)=='number' and calibration_down>0)
        if calibration_down and not state.calibration_down then
            state.calibration=not state.calibration;state.last_draw=nil;state.rows=nil
        end
        state.calibration_down=calibration_down
    end
    refresh()
    if OUTPOST_DIAGNOSTIC then
        local capture_down=sr.Keyboard.button(state.capture_key)
        capture_down=capture_down==true or (type(capture_down)=='number' and capture_down>0)
        if capture_down and not state.capture_down then
            local captured,message=pcall(capture_outposts)
            if not captured then state.capture_error=tostring(message) end
        end
        state.capture_down=capture_down
    end
end
local function overlay_update()
    if not state.failed then
        local ok,message=pcall(tick)
        if not ok then
            state.failed=true
            if sr then pcall(function()release(worlds())end) end
            status('FAILED',tostring(message))
            if rawget(_G,'update')==wrapper then _G.update=previous end
        end
    end
end
wrapper=function(...)
    return Core.after_update(previous,overlay_update,...)
end
_G.update=wrapper
local shutdown=rawget(_G,'shutdown')
if type(shutdown)=='function' then
    _G.shutdown=function(...)
        if sr then
            pcall(function()release(worlds())end)
            if sr.Application.render_world==state.render_tracer then sr.Application.render_world=state.render_original end
        end
        if rawget(_G,'render')==state.global_render_wrapper then _G.render=state.global_render_original end
        return shutdown(...)
    end
end
return state
