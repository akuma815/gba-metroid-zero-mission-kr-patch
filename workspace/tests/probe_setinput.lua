-- setInput 호출 형식을 하나씩 시험해 어떤 형태가 통과하는지 기록한다.
local OUT_DIR = "@@OUT_DIR@@"
local MAX_FRAME = @@MAX_FRAME@@

local frame = 0
local log = {}
local function put(s) log[#log + 1] = s; emu.log(s) end

local FULL = {a=false, b=false, l=false, r=false, select=false,
              start=true, up=false, down=false, left=false, right=false}

local tried = false
emu.addEventCallback(function()
  if tried then return end
  tried = true

  local ok, err = pcall(function() emu.setInput(FULL, 0) end)
  put("setInput(FULL, 0): " .. (ok and "OK" or tostring(err)))

  ok, err = pcall(function() emu.setInput(FULL, 0, 0) end)
  put("setInput(FULL, 0, 0): " .. (ok and "OK" or tostring(err)))

  ok, err = pcall(function() emu.setInput({start=true}, 0) end)
  put("setInput({start}, 0): " .. (ok and "OK" or tostring(err)))

  ok, err = pcall(function()
    local inp = emu.getInput(0)
    inp.start = true
    emu.setInput(inp, 0)
  end)
  put("getInput->setInput(inp,0): " .. (ok and "OK" or tostring(err)))
end, emu.eventType.inputPolled)

emu.addEventCallback(function()
  frame = frame + 1
  if frame >= MAX_FRAME then
    local f = io.open(OUT_DIR .. "/probe_setinput.txt", "w")
    if f then f:write(table.concat(log, "\n")); f:close() end
    emu.stop(0)
  end
end, emu.eventType.endFrame)
