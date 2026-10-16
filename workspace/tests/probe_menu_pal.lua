-- 파일 선택 화면의 팔레트를 덤프한다(선택/비선택 항목의 색 차이 확인).
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

emu.addEventCallback(function()
  frame = frame + 1
  if frame == 2700 then
    for bank = 0, 15 do
      local parts = {}
      local nz = false
      for i = 0, 15 do
        local a = bank * 32 + i * 2
        local v = emu.read(a, emu.memType.gbaPaletteRam, false)
                + emu.read(a + 1, emu.memType.gbaPaletteRam, false) * 256
        if v ~= 0 then nz = true end
        parts[#parts + 1] = string.format("%2d:%04X", i, v)
      end
      if nz then put(string.format("BG pal%02d: %s", bank, table.concat(parts, " "))) end
    end
    local f = io.open(OUT_DIR .. "/menu_pal.txt", "w")
    if f then f:write(table.concat(log, "\n")); f:close() end
  end
  if frame >= MAX_FRAME then emu.stop(0) end
end, emu.eventType.endFrame)
