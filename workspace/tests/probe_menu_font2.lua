-- 파일 선택 화면 '진입 순간'의 폰트 읽기를 추적한다.
-- 1회성 업로드는 늦게 관측하면 놓친다(앞선 추적이 2470부터라 진입 구간을 못 봤다).
-- 여기서는 START 입력 직후부터 계속 본다.

local OUT_DIR = "@@OUT_DIR@@"
local MAX_FRAME = @@MAX_FRAME@@
local FONT_BASE = 0x4154BC

local frame = 0
local log = {}
local function put(s) log[#log + 1] = s; emu.log(s) end

local press = {}
for f = 2450, 2469 do press[f] = true end

emu.addEventCallback(function()
  if press[frame] then
    local inp = emu.getInput(0)
    inp.start = true
    emu.setInput(inp, 0)
  end
end, emu.eventType.inputPolled)

local cur, curN = {}, 0
emu.addMemoryCallback(function(addr)
  if curN < 8000 then
    cur[addr] = true
    curN = curN + 1
  end
end, emu.callbackType.read, 0x415000, 0x442000, nil, emu.memType.gbaPrgRom)

emu.addEventCallback(function()
  frame = frame + 1
  if curN > 0 and frame >= 2440 then
    local codes = {}
    for a in pairs(cur) do
      local tile = math.floor((a - FONT_BASE) / 32)
      local code = tile
      if (math.floor(tile / 32) % 2) == 1 then code = tile - 32 end
      codes[code] = true
    end
    local list = {}
    for c in pairs(codes) do list[#list + 1] = c end
    table.sort(list)
    local parts = {}
    for i = 1, math.min(#list, 30) do parts[#parts + 1] = string.format("%04X", list[i]) end
    put(string.format("frame %d: reads=%d codes(%d): %s",
      frame - 1, curN, #list, table.concat(parts, " ")))
  end
  cur, curN = {}, 0
  if frame >= MAX_FRAME then
    local f = io.open(OUT_DIR .. "/probe_menu_font2.txt", "w")
    if f then f:write(table.concat(log, "\n")); f:close() end
    emu.stop(0)
  end
end, emu.eventType.endFrame)
