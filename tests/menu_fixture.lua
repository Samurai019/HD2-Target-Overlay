-- Actual upstream options/API/text code; only native descriptors and filesystem
-- are fixtures. Exercise validation, saved values and APPLY/discard semantics.
return function(options_source, api_source, text_source)
    return function(saved)
        local env={};for k,v in pairs(_G) do env[k]=v end
        env._G=env
        local files={['/virtual/ModOptionsMenu.values']=saved}
        env.io={open=function(path,mode)
            if mode=='rb' then
                if not files[path] then return nil end
                return {read=function() return files[path] end,close=function() return true end}
            end
            assert(mode=='wb');local buffer=''
            return {write=function(self,text) buffer=buffer..text;return self end,
                    close=function() files[path]=buffer;return true end}
        end}
        env.os={getenv=function() return nil end,remove=function(p) files[p]=nil;return true end,
                rename=function(a,b) if not files[a] then return nil end;files[b]=files[a];files[a]=nil;return true end}
        local function run(source,...)
            local fn=assert(loadstring(source));setfenv(fn,env);return fn(...)
        end
        local state={mods={},refused={},refused_count=0,options={},option_count=0,values={},pending={},
            pending_count=0,queued={},queued_any=false,callbacks={},revision=0,dirty=false}
        local mom={state=state,note=function() end,loader={log_directory='/virtual'},TEXT_TEMPLATE=42,
            MAX_MODS=112,MAX_ROWS=32,descriptor=function() return 123,{} end,
            translation={T=run(text_source),tr=function(key) return key end}}
        run(options_source,mom);run(api_source,mom)
        return mom.api,state,mom,function() return files['/virtual/ModOptionsMenu.values'] end
    end
end
