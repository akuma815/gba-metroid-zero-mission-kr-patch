-- 파일 선택 화면의 BG 설정과 타일맵을 덤프한다.
-- BGxCNT: bit2-3 문자베이스(16KB), bit8-12 스크린베이스(2KB), bit14-15 크기

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

local function rd16(addr)
  return emu.read(addr, emu.memType.gbaMemory, false)
       + emu.read(addr + 1, emu.memType.gbaMemory, false) * 256
end

emu.addEventCallback(function()
  frame = frame + 1
  if frame == 2700 then
    local dispcnt = rd16(0x04000000)
    put(string.format("DISPCNT = %04X (mode %d, BG0-3 on: %d%d%d%d, OBJ %d)",
      dispcnt, dispcnt % 8,
      math.floor(dispcnt / 0x100) % 2, math.floor(dispcnt / 0x200) % 2,
      math.floor(dispcnt / 0x400) % 2, math.floor(dispcnt / 0x800) % 2,
      math.floor(dispcnt / 0x1000) % 2))

    for bg = 0, 3 do
      local cnt = rd16(0x04000008 + bg * 2)
      local charbase = math.floor(cnt / 4) % 4
      local screenbase = math.floor(cnt / 256) % 32
      local size = math.floor(cnt / 0x4000) % 4
      local pal256 = math.floor(cnt / 128) % 2
      put(string.format("BG%dCNT = %04X : charbase %d(0x%05X) screenbase %d(0x%05X) size %d %s",
        bg, cnt, charbase, charbase * 0x4000, screenbase, screenbase * 0x800,
        size, pal256 == 1 and "256color" or "16color"))
    end

    -- 스크린 블록 전체(0x0000-0xFFFF) 중 2KB 단위로 덤프해 나중에 대조한다
    local f = io.open(OUT_DIR .. "/vram_map.bin", "wb")
    if f then
      local chunk = {}
      for a = 0, 0xFFFF do
        chunk[#chunk + 1] = string.char(emu.read(a, emu.memType.gbaVideoRam, false))
        if #chunk >= 4096 then f:write(table.concat(chunk)); chunk = {} end
      end
      if #chunk > 0 then f:write(table.concat(chunk)) end
      f:close()
      put("dumped vram_map.bin (VRAM 0x0000-0xFFFF)")
    end

    local g = io.open(OUT_DIR .. "/bgmap.txt", "w")
    if g then g:write(table.concat(log, "\n")); g:close() end
  end
  if frame >= MAX_FRAME then emu.stop(0) end
end, emu.eventType.endFrame)
