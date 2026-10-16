-- 자막 표시 시점의 팔레트를 덤프해 색상 제어코드의 효과 가능 여부를 판단한다.
local OUT_DIR = "@@OUT_DIR@@"
local MAX_FRAME = @@MAX_FRAME@@

local frame = 0
local log = {}
local function put(s) log[#log + 1] = s; emu.log(s) end

local function dumpPalette(tag)
  -- GBA 팔레트 RAM: BG 0x000-0x1FF, OBJ 0x200-0x3FF (u16 BGR555)
  for bank = 0, 31 do
    local parts = {}
    local nonzero = false
    for i = 0, 15 do
      local addr = bank * 32 + i * 2
      local lo = emu.read(addr, emu.memType.gbaPaletteRam, false)
      local hi = emu.read(addr + 1, emu.memType.gbaPaletteRam, false)
      local v = lo + hi * 256
      if v ~= 0 then nonzero = true end
      parts[#parts + 1] = string.format("%04X", v)
    end
    if nonzero then
      local kind = bank < 16 and "BG " or "OBJ"
      put(string.format("%s %s pal%02d: %s", tag, kind, bank % 16, table.concat(parts, " ")))
    end
  end
end

emu.addEventCallback(function()
  frame = frame + 1
  if frame == 850 then
    dumpPalette("f850")
  end
  if frame >= MAX_FRAME then
    local f = io.open(OUT_DIR .. "/probe_palette.txt", "w")
    if f then f:write(table.concat(log, "\n")); f:close() end
    emu.stop(0)
  end
end, emu.eventType.endFrame)
