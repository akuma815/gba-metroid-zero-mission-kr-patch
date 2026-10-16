-- 폰트 영역 읽기 주소를 수집해 글리프 코드로 역산한다.
-- code = (addr - 0x4154BC) / 32  (상단), 하단은 +0x400

local OUT_DIR = "@@OUT_DIR@@"
local MAX_FRAME = @@MAX_FRAME@@
local FONT_BASE = 0x4154BC

local frame = 0
local log = {}
local function put(s) log[#log + 1] = s; emu.log(s) end

-- 프레임별 접근 주소 집합
local cur = {}
local curN = 0

emu.addMemoryCallback(function(addr, value)
  if curN < 4000 then
    cur[addr] = true
    curN = curN + 1
  end
end, emu.callbackType.read, 0x415000, 0x442000, nil, emu.memType.gbaPrgRom)

emu.addEventCallback(function()
  frame = frame + 1
  if curN > 0 then
    -- 주소를 32바이트 타일 단위로 묶어 코드 역산
    local codes = {}
    local minA, maxA = 0xFFFFFFF, 0
    for a, _ in pairs(cur) do
      if a < minA then minA = a end
      if a > maxA then maxA = a end
      local rel = a - FONT_BASE
      local tile = math.floor(rel / 32)
      -- 하단 타일(+0x400 = +32타일)은 코드에서 32를 뺀다
      local code = tile
      if (math.floor(tile / 32) % 2) == 1 then code = tile - 32 end
      codes[code] = true
    end
    local list = {}
    for c, _ in pairs(codes) do list[#list + 1] = c end
    table.sort(list)
    local parts = {}
    for i = 1, math.min(#list, 40) do parts[#parts + 1] = string.format("%04X", list[i]) end
    put(string.format("frame %d: reads=%d range=0x%06X-0x%06X codes(%d): %s",
      frame - 1, curN, minA, maxA, #list, table.concat(parts, " ")))
    cur = {}
    curN = 0
  end
  if frame >= MAX_FRAME then
    local f = io.open(OUT_DIR .. "/probe_font_addr.txt", "w")
    if f then f:write(table.concat(log, "\n")); f:close() end
    emu.stop(0)
  end
end, emu.eventType.endFrame)
