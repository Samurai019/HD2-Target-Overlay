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
    if not (n>=65536 and n<140737488355328 and n%4==0) then
        error((label or 'pointer')..string.format(' invalid: 0x%x',n))
    end
    return n
end
local function f32(s,o)
    local b=u32(s,o);local sign=b>=2147483648 and -1 or 1
    local exp=math.floor(b/8388608)%256;local mant=b%8388608
    if exp==255 then return nil end
    if exp==0 then return sign*mant*2^-149 end
    return sign*(1+mant/8388608)*2^(exp-127)
end
function Core.snapshot(read,base,objectives_only)
    local rows,identity={},{}
    local specs={{rva=0x3326590,count=12,array=72,stride=20,kind='marker'},
                 {rva=0x3326da0,count=36,array=104,stride=100,kind='objective'}}
    for _,s in ipairs(specs) do
        if objectives_only and s.kind=='marker' then
            identity[#identity+1]=string.rep('\0',8)
        else
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
function Core.mission_rows(read,base,credits,options,black_boxes,medals)
    if options and not options.objectives and not options.outposts then
        return Core.filter({},credits,{},options,black_boxes,medals),''
    end
    local rows,identity=Core.snapshot(read,base,true)
    local errors={}
    local ok,message=pcall(Core.classify_objectives,read,base,rows,identity)
    if not ok then
        errors[#errors+1]='SIDE: '..tostring(message)
        for _,row in ipairs(rows) do row.importance=nil;row.stalker_lair=false end
    end
    local post_ok,posts,post_errors=true,{},nil
    if not options or options.outposts then post_ok,posts,post_errors=pcall(Core.outposts,read,base) end
    if not post_ok then errors[#errors+1]='OUTPOST: '..tostring(posts);posts={} end
    if post_ok and post_errors and post_errors~='' then errors[#errors+1]='OUTPOST: '..post_errors end
    return Core.filter(rows,credits,posts,options,black_boxes,medals),table.concat(errors,'\n')
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
function Core.model_positions(api,list,main,resource_hex,position_node)
    local resource=api.IdString64.from_hex(resource_hex)
    local points,seen={},{}
    local worlds_seen=0
    for _,world in pairs(list) do
        worlds_seen=worlds_seen+1;assert(worlds_seen<=8,'too many worlds')
        local gameplay=main==nil or world==main
        if gameplay then
        local units=api.World.units_by_resource(world,resource)
        assert(type(units)=='table','resource query unavailable')
        local count=0
        for _,unit in pairs(units) do
            count=count+1;assert(count<=128,'too many model units')
            if not seen[unit] and api.Unit.alive(unit) then
                seen[unit]=true
                local root=api.Unit.world_position(unit,0)
                local rx,ry=api.Vector3.x(root),api.Vector3.y(root)
                local rz=api.Vector3.z and api.Vector3.z(root) or nil
                local node=0
                if api.Unit.has_node and api.Unit.node then
                    local node_hex=position_node and position_node.hex or 'e4a4586d'
                    local name=api.IdString32 and api.IdString32.from_hex(node_hex) or (position_node and position_node.name or 'interact')
                    local node_ok,result=pcall(function()
                        if api.Unit.has_node(unit,name) then return api.Unit.node(unit,name) end
                    end)
                    if node_ok and type(result)=='number' and result>=0 and result<256 then
                        node=result
                    end
                end
                local position=api.Unit.world_position(unit,node)
                local x,y=api.Vector3.x(position),api.Vector3.y(position)
                if type(x)=='number' and type(y)=='number' and x==x and y==y and
                    math.abs(x)<100000 and math.abs(y)<100000 then
                    -- Observed three distinct units returning zero root positions.
                    -- A nearby bind-pose interaction offset does not resolve that ambiguity.
                    local unresolved=rx==0 and ry==0 and (rz==nil or rz==0) and x*x+y*y<1
                    -- Carryable black boxes have a named mesh node, no interact
                    -- node. Never publish their unresolved root/default XY.
                    if position_node then
                        unresolved=node==0 or x*x+y*y<0.0001 or (rx==0 and ry==0 and x*x+y*y<1)
                    end
                    local selected=gameplay and not unresolved
                    if selected then points[#points+1]={x=x,y=y} end
                end
            end
        end
        end
    end
    return points
end
function Core.credit_positions(api,list,main)
    return Core.model_positions(api,list,main,'bd6f4de16b9aedcd')
end
function Core.medal_positions(api,list,main)
    -- ExplorationReward medals entity 147bd99513726f88 -> Unit model.
    return Core.model_positions(api,list,main,'773c4184e4bad0df')
end
function Core.black_box_positions(api,list,main)
    -- UnitComponent data maps the carryable entities to this model resource.
    return Core.model_positions(api,list,main,'3de2415ea33b6897',
        {hex='3c9e8cfd',name='black_box_01'})
end
-- Native ObjectiveCarry records use entity resources, not the queried model ID.
-- All three carryable entities share the black-box model. Compare raw bytes.
local BLACK_BOX_ENTITIES={
    [string.char(0x97,0x68,0x3b,0xa3,0x5e,0x41,0xe2,0x3d)]=true,
    [string.char(0x1c,0x8d,0xd4,0x8b,0x11,0xa3,0xd7,0x8a)]=true,
    [string.char(0x38,0x5e,0x86,0x5a,0x2b,0x72,0x3e,0x4a)]=true
}
function Core.native_black_box_visible(read,base)
    local root=assert(read(base+0x3326d00,8),'black-box carry manager unavailable')
    local address=ptr(root,0)
    local head=assert(read(address,112),'black-box map header unavailable')
    local count=u32(head,12);assert(count<=512,'unexpected map marker count')
    local visible=false
    if count>0 then
        local handles=assert(read(ptr(head,56),count*8),'map marker entities unavailable')
        local flags=assert(read(ptr(head,80),count*36),'carry marker visibility unavailable')
        for i=0,count-1 do
            local valid,entity=pcall(ptr,handles,i*8)
            if valid then
                local resource=assert(read(entity,8),'map marker resource unavailable')
                -- ObjectiveCarry map renderer 18b0b81 uses stride 0x24:
                -- byte +4 enables the icon, byte +5 reveals it. The reveal
                -- field is initialized to 0 at 5c956c and replicated at
                -- 5c971d. Once revealed, leave this item to the native HUD,
                -- including when it is temporarily disabled while attached.
                if BLACK_BOX_ENTITIES[resource] and flags:byte(i*36+6)~=0 then visible=true end
            end
        end
    end
    assert(read(base+0x3326d00,8)==root and read(address,112)==head,'black-box carry scene changed')
    return visible
end
function Core.unmarked_black_boxes(read,base,boxes)
    if #boxes==0 then return boxes end
    return Core.native_black_box_visible(read,base) and {} or boxes
end
function Core.keep_location(row)
    if row.kind=='outpost' then return row.counts_as_outpost~=false and not row.completed end
    return not row.discovered
end
function Core.filter(rows,credits,outposts,options,black_boxes,medals)
    options=options or {outposts=true,objectives=true,credits=true,black_boxes=true,medals=false}
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
    for _,medal in ipairs(options.medals and medals or {}) do
        selected[#selected+1]={x=medal.x,y=medal.y,kind='medal'}
    end
    for _,box in ipairs(options.black_boxes and black_boxes or {}) do
        selected[#selected+1]={x=box.x,y=box.y,kind='black_box'}
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
        description='标记已加载的超级货币模型。拾取后撤销蓝色标记。'},
    {key='black_boxes',id='astla.target_overlay.black_boxes',label='标记黑匣子',
        description='用黄色空心菱形标记已加载且原版尚未标记的主线黑匣子。首次拾取后由原版标记接管，黄色标记撤销。'},
    {key='medals',id='astla.target_overlay.medals',label='标记勋章',default=false,
        description='用金色八边形与蓝色绶带奖章标记已加载的勋章（Medal）。拾取后撤销，默认关闭。'}
}
Core.rate_specs={
    {key='refresh_hz',id='astla.target_overlay.refresh_hz',type='slider',label='刷新频率（次/秒）',default=5,max=60,
        description='平时地图图标的显示更新频率，范围1–60次/秒。默认5；目标位置查询仍每2秒进行一次。'},
    {key='boost_hz',id='astla.target_overlay.boost_hz',type='slider',label='临时提速刷新频率（次/秒）',default=60,max=120,
        description='打开、关闭、放大、缩小地图时的显示更新频率，范围1–120次/秒。默认60，最后一次操作后半秒恢复普通频率。'}
}
Core.menu_specs={}
for _,group in ipairs({Core.option_specs,Core.rate_specs}) do
    for _,spec in ipairs(group) do Core.menu_specs[#Core.menu_specs+1]=spec end
end
function Core.display_interval(state,now)
    local boosted=now<(state.fast_until or 0)
    return 1/(state.options[boosted and 'boost_hz' or 'refresh_hz'] or (boosted and 60 or 5))
end
function Core.menu_step(state,menu)
    if type(menu)~='table' or menu.api~=1 or type(menu.register_option)~='function' or
        type(menu.get)~='function' or type(menu.on_change)~='function' then return end
    if state.options_menu~=menu then
        state.options_menu=menu;state.option_links={};state.options_error=nil
    end
    local function apply(spec,value)
        if spec.type=='slider' then
            if type(value)=='number' and value==value and value>=1 and value<=spec.max and value%1==0 and
                state.options[spec.key]~=value then
                state.options[spec.key]=value;state.next_display=0
            end
        elseif type(value)=='boolean' and state.options[spec.key]~=value then
            state.options[spec.key]=value;state.rows=nil
        end
    end
    for _,spec in ipairs(Core.menu_specs) do
        local link=state.option_links[spec.id]
        if link==nil then
            -- Registration failures are terminal for this API instance; don't
            -- retry each frame or let a broken optional menu stop the overlay.
            state.option_links[spec.id]=false
            local config={type=spec.type or 'toggle',mod='Target Overlay',label=spec.label,description=spec.description}
            if spec.type=='slider' then
                config.min,config.max,config.step,config.default=1,spec.max,1,spec.default
            else config.default=spec.default~=false end
            local ok,result,reason=pcall(menu.register_option,spec.id,config)
            if ok and result==true then
                local option=spec
                local hooked,accepted=pcall(menu.on_change,spec.id,function(value) apply(option,value) end)
                state.option_links[spec.id]=true
                if not hooked or accepted~=true then state.options_error='Menu callback unavailable: '..spec.id end
            else state.options_error='Menu registration failed: '..spec.id..': '..tostring(ok and reason or result) end
        end
        if state.option_links[spec.id] then
            -- Also covers saved values on registration and programmatic set(),
            -- which intentionally does not invoke menu callbacks.
            local ok,value=pcall(menu.get,spec.id)
            if ok then apply(spec,value) end
        end
    end
end
-- Native mission HUD is embedded in the UI owner; all reads are bounded.
function Core.map_gate(read,base)
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
    return map,head,root,screens
end
-- The native close handler clears +0x195 before the widget's exit animation.
-- Check only while overlay rectangles exist: two bounded reads, no transforms.
function Core.map_is_open(read,base,map,owner)
    if not map or not owner or read(base+0x346d538,8)~=owner then return false end
    return read(map+0x195,1)==string.char(1)
end
function Core.map_view(read,base,width,height)
    local map,head,root,screens=Core.map_gate(read,base)
    if not map then return nil end
    local function value(o)
        local v=assert(f32(head,o),'invalid map value')
        assert(math.abs(v)<100000,'map value out of range');return v
    end
    local view={origin_x=value(0),origin_y=value(4),pan_x=value(0x10),pan_y=value(0x14),
        scale=value(0x28),cx=value(0x9c),cy=value(0xa0),radius=value(0xa4),map_address=map,ui_owner=root,width=width,height=height}
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
        for sx=-1,1,2 do for sy=-1,1,2 do
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
    if p.kind=='medal' then return {255,255,165,50} end
    if p.kind=='black_box' then return {255,255,210,45} end
    if p.kind=='credit_poi' then return {255,45,120,255} end
    if p.kind=='outpost' or p.kind=='stalker_lair' then return {255,255,45,55} end
    if p.kind=='objective' then return {255,255,255,255} end
    return {255,55,218,234}
end
-- Rasterize hollow polygons using the established rectangle GUI API.
function Core.glyph(kind,size,thickness,step)
    local count=kind=='outpost' and 6 or (kind=='credit_poi' and 3 or 4)
    local vertices={}
    if kind=='medal' then
        local parts=Core.glyph('medal_ribbon',size,thickness,step)
        for _,part in ipairs(parts) do part[5]={255,45,120,255} end
        for _,part in ipairs(Core.glyph('medal_body',size,thickness,step)) do
            part[5]={255,235,195,70};parts[#parts+1]=part
        end
        return parts
    elseif kind=='medal_ribbon' then
        -- Visible fabric above the medal; mirror below after rasterization.
        vertices={{-.46,1},{0,.90},{.46,1},{.46,.60},{0,.79},{-.46,.60}}
    elseif kind=='medal_body' then
        -- Complete eight-edge gold ring, including the edges across the ribbon.
        for i=0,7 do
            local angle=math.pi/2+i*math.pi/4
            vertices[#vertices+1]={.79*math.cos(angle),.79*math.sin(angle)}
        end
    elseif kind=='black_box' then
        vertices={{0,1},{-1,0},{0,-1},{1,0}}
    elseif kind=='stalker_lair' then
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
        local inner=kind=='medal_ribbon' and {} or span(y+step/2,math.max(0,radius-thickness))
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
    if kind=='medal_ribbon' then
        local count=#result
        for i=1,count do
            local p=result[i];result[#result+1]={p[1],-p[2]-p[4],p[3],p[4]}
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
-- Cache only the current resolution's shapes; never retain engine Vector/Color
-- temporaries across frames. Merge identical adjacent scanlines losslessly.
function Core.compact_glyph(parts)
    local result,previous={},{}
    for _,p in ipairs(parts) do
        if p[3]>0 then
            local color=p[5]
            local key=string.format('%.17g:%.17g',p[1],p[3])
            if color then key=key..':'..table.concat(color,':') end
            local prior=previous[key]
            if prior and prior[2]+prior[4]==p[2] then
                prior[4]=prior[4]+p[4]
            else
                local copy={p[1],p[2],p[3],p[4],color}
                result[#result+1]=copy;previous[key]=copy
            end
        end
    end
    return result
end
function Core.marker_parts(cache,p,scale)
    if cache.scale~=scale then cache.scale=scale;cache.shapes={} end
    local key=p.kind..':'..string.format('%.17g',p.size)
    local parts=cache.shapes[key]
    if parts then return parts end
    parts={}
    local edge=math.max(2,2*scale)
    for _,spec in ipairs({{p.size+4*edge,4*edge,{255,0,0,0},Core.layers.outline},
                          {p.size,edge,Core.marker_color(p),Core.layers.symbol}}) do
        for _,part in ipairs(Core.compact_glyph(Core.glyph(p.kind,spec[1],spec[2],math.max(1,scale)))) do
            parts[#parts+1]={part[1],part[2],part[3],part[4],
                spec[4]==Core.layers.symbol and (part[5] or spec[3]) or spec[3],spec[4]}
        end
    end
    cache.shapes[key]=parts
    return parts
end
-- Reuse retained rectangles and touch only changed ones. Some game builds may
-- omit update_rect; keep the established destroy/create path as a fallback.
function Core.draw_rect(state,api,index,x,y,part)
    state.rects=state.rects or {}
    local old=state.rects[index]
    if old and old.x==x and old.y==y and old.part==part then return end
    local color=part[5]
    local pos=api.Vector3(x,y,part[6])
    local size=api.Vector2(part[3],part[4])
    local tint=api.Color(color[1],color[2],color[3],color[4])
    local id=state.ids[index]
    local updated=false
    if id and not state.update_rect_unavailable and type(api.Gui.update_rect)=='function' then
        updated=pcall(api.Gui.update_rect,state.gui,id,pos,size,tint)
        if not updated then state.update_rect_unavailable=true end
    end
    if not updated then
        if id then api.Gui.destroy_rect(state.gui,id);state.ids[index]=nil end
        state.ids[index]=assert(api.Gui.rect(state.gui,pos,size,tint),'rectangle creation failed')
    end
    state.rects[index]={x=x,y=y,part=part}
end
local VIEW_FIELDS={'origin_x','origin_y','pan_x','pan_y','scale','cx','cy','radius',
    'map_address','width','height','hud_curve','xx','xy','yx','yy','tx','ty','icon_scale'}
function Core.same_view(a,b)
    if not a or not b then return false end
    for _,key in ipairs(VIEW_FIELDS) do if a[key]~=b[key] then return false end end
    return true
end
function Core.same_rows(a,b)
    if not a or #a~=#b then return false end
    for i,p in ipairs(a) do
        local q=b[i]
        if p.x~=q.x or p.y~=q.y or p.kind~=q.kind or p.completed~=q.completed then return false end
    end
    return true
end
function Core.options_key(options)
    local key=0
    for i,spec in ipairs(Core.option_specs) do
        if options[spec.key] then key=key+2^(i-1) end
    end
    return key
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
local state={version='1.3.7',frame=0,ids={},phase='starting',options={outposts=true,objectives=true,credits=true,black_boxes=true,medals=false,refresh_hz=5,boost_hz=60}}
_G.HD2TargetOverlay=state
local function status(phase,message)
    if state.phase==phase and state.message==message then return end
    state.phase,state.message=phase,message

end
local ffi,crypto,kernel,base,read,sr
local clock=os.clock
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
      uint64_t GetTickCount64(void);
    ]]
    kernel,crypto=ffi.load('kernel32'),ffi.load('advapi32')
    clock=function() return tonumber(kernel.GetTickCount64())/1000 end
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
    status('READY','Overlay follows native minimap visibility; refresh rates are configurable in Mod Options Menu')
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
local function clear(list)
    state.draw_rows,state.draw_view=nil,nil
    if #state.ids==0 then return end
    if state.gui and live(list,state.world) then
        for _,id in ipairs(state.ids) do pcall(sr.Gui.destroy_rect,state.gui,id) end
    end
    state.ids={}
    state.rects={}
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
            state.in_render=true
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
    if state.draw_rows==rows and Core.same_view(state.draw_view,view) then return end
    local projected=Core.map_project(rows,view)
    state.glyph_cache=state.glyph_cache or {}
    local index=0
    for _,p in ipairs(projected) do
        for _,part in ipairs(Core.marker_parts(state.glyph_cache,p,view.icon_scale)) do
            index=index+1
            Core.draw_rect(state,sr,index,p.x+part[1],p.y+part[2],part)
        end
    end
    for i=#state.ids,index+1,-1 do
        sr.Gui.destroy_rect(state.gui,state.ids[i]);state.ids[i]=nil;state.rects[i]=nil
    end
    state.draw_rows,state.draw_view=rows,view
end
-- Complete a query round in one display update. Keep the two-second deadline
-- and never catch up missed rounds or retry failures every game frame.
local function collect_rows(list,main,now)
    if now<(state.next_query or 0) then return end
    state.next_query=now+2
    local credit_ok,credits=true,{}
    if state.options.credits then credit_ok,credits=pcall(Core.credit_positions,sr,list,main) end
    state.credit_error=not credit_ok and tostring(credits) or nil
    credits=credit_ok and credits or {};state.credit_count=#credits
    local medal_ok,medals=true,{}
    if state.options.medals then medal_ok,medals=pcall(Core.medal_positions,sr,list,main) end
    state.medal_error=not medal_ok and tostring(medals) or nil
    medals=medal_ok and medals or {};state.medal_count=#medals
    local box_ok,boxes=true,{}
    if state.options.black_boxes then
        box_ok,boxes=pcall(function()
            return Core.unmarked_black_boxes(read,base,Core.black_box_positions(sr,list,main))
        end)
    end
    state.black_box_error=not box_ok and tostring(boxes) or nil
    boxes=box_ok and boxes or {};state.black_box_count=#boxes
    local ok,rows,errors=pcall(Core.mission_rows,read,base,credits,state.options,boxes,medals)
    state.category_error=ok and errors~='' and errors or nil
    state.snapshot_error=not ok and tostring(rows) or state.category_error
    rows=ok and rows or {}
    if not Core.same_rows(state.rows,rows) then state.rows=rows end
end
local function reset_queries()
    state.rows,state.next_query=nil,nil
    state.query_world,state.query_map,state.query_options=nil,nil,nil
end
local function observe_map(map,scale,now)
    if map~=state.observed_map or scale~=state.observed_scale then
        state.fast_until=now+0.5
        state.observed_map,state.observed_scale=map,scale
        return true
    end
    return false
end
local function reset_interaction()
    state.observed_map,state.observed_scale,state.fast_until=nil,nil,nil
end
local function refresh(now)
    now=now or clock()
    local list=worlds()
    local width,height=sr.Gui.resolution()
    assert(type(width)=='number' and type(height)=='number' and width>0 and height>0,'invalid screen size')
    local valid,view=pcall(Core.map_view,read,base,width,height)
    if not valid or not view then
        clear(list)
        reset_queries()
        if valid then observe_map(nil,nil,now) else reset_interaction() end
        local detail=not valid and tostring(view) or 'Native minimap closed or HUD hidden'
        status('MAP_HIDDEN',detail)
        return
    end
    state.map_owner=view.ui_owner
    observe_map(view.map_address,view.scale,now)
    local main=sr.Application.main_world()
    local options=Core.options_key(state.options)
    if state.query_world~=main or state.query_map~=view.map_address or state.query_options~=options then
        clear(list);reset_queries()
        state.query_world,state.query_map,state.query_options=main,view.map_address,options
    end
    collect_rows(list,main,now)
    local rows=state.rows
    if not rows or #rows==0 then
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
    if state.frame==1 or state.frame%30==0 then Core.menu_step(state,rawget(_G,'ModOptionsMenu')) end
    if worker then
        if state.frame<120 then return end
        local ok,message=coroutine.resume(worker)
        if not ok then error(message) end
        if coroutine.status(worker)=='dead' then worker=nil;install_render_tracking() end
        return
    end
    local now=clock()
    local closing=false
    if #state.ids>0 then
        local ok,opened=pcall(Core.map_is_open,read,base,state.query_map,state.map_owner)
        if not ok or not opened then
            clear(worlds());reset_queries();observe_map(nil,nil,now)
            closing=true
        end
    end
    local due=closing or now>=(state.next_display or 0)
    if not due and now>=(state.next_visibility or 0) then
        -- Reuse the bounded visibility header to detect opening and zoom,
        -- even when no icons exist. No model queries or projection here.
        state.next_visibility=now+0.1
        local ok,map,head=pcall(Core.map_gate,read,base)
        if not ok then
            clear(worlds());reset_queries();reset_interaction()
            status('MAP_HIDDEN','Native minimap unavailable')
        elseif not map then
            clear(worlds());reset_queries()
            due=observe_map(nil,nil,now)
            status('MAP_HIDDEN','Native minimap closed or HUD hidden')
        else
            if map~=state.query_map then clear(worlds());reset_queries() end
            local scale=f32(head,0x28)
            if scale and scale>0 and scale<100 then due=observe_map(map,scale,now) end
        end
    end
    if due then
        state.next_visibility=now+0.1
        refresh(now)
        local interval=Core.display_interval(state,now)
        state.next_display=now+interval
        if now<(state.fast_until or 0) then state.next_display=math.min(state.next_display,state.fast_until) end
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
