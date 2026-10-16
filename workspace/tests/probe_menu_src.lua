-- 파일 선택 화면이 어느 ROM 영역을 읽는지 추적한다.
-- 폰트(0x415000-0x442000) 읽기가 있으면 u16 텍스트 경로,
-- 없으면 별도 그래픽 자산이다. LZ77 블롭 영역도 함께 본다.

local OUT_DIR = "@@OUT_DIR@@"
local MAX_FRAME = @@MAX_FRAME@@

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

-- 구간별 읽기 카운터
local zones = {
  {name = "font", lo = 0x415000, hi = 0x442000},
  {name = "lz77", lo = 0x412000, hi = 0x414000},
  {name = "text", lo = 0x441000, hi = 0x447000},
}
local hits = {}
for _, z in ipairs(zones) do
  hits[z.name] = {}
  emu.addMemoryCallback(function(addr)
    local t = hits[z.name]
    t[frame] = (t[frame] or 0) + 1
  end, emu.callbackType.read, z.lo, z.hi, nil, emu.memType.gbaPrgRom)
end

emu.addEventCallback(function()
  frame = frame + 1
  if frame >= 2470 and frame <= 2700 then
    local parts = {}
    for _, z in ipairs(zones) do
      local n = hits[z.name][frame - 1]
      if n and n > 0 then parts[#parts + 1] = z.name .. "=" .. n end
    end
    if #parts > 0 then
      put(string.format("frame %d: %s", frame - 1, table.concat(parts, " ")))
    end
  end
  if frame >= MAX_FRAME then
    local f = io.open(OUT_DIR .. "/probe_menu_src.txt", "w")
    if f then f:write(table.concat(log, "\n")); f:close() end
    emu.stop(0)
  end
end, emu.eventType.endFrame)
