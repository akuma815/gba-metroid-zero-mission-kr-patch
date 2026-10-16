-- 지정한 프레임에서 VRAM·팔레트·OAM·BG레지스터·스크린샷을 저장한다.
-- GUI 없이 특정 화면(타이틀 등)을 조사할 때 쓴다. 러너: workspace/scripts/run_dump.py

local OUT_DIR = "@@OUT_DIR@@"
local FRAMES = @@FRAMES@@      -- { {frame=..., name=...}, ... }
local MAX_FRAME = @@MAX_FRAME@@

local frame = 0
local idx = 1

local function rd16(a)
  return emu.read(a, emu.memType.gbaMemory, false)
       + emu.read(a + 1, emu.memType.gbaMemory, false) * 256
end

local function dumpAll(tag)
  local lines = {}
  local function put(s) lines[#lines + 1] = s; emu.log(s) end

  put(string.format("frame=%d DISPCNT=%04X", frame, rd16(0x04000000)))
  for bg = 0, 3 do
    local c = rd16(0x04000008 + bg * 2)
    put(string.format("BG%dCNT=%04X charbase %d(0x%05X) screenbase %d(0x%05X) prio %d %s",
      bg, c,
      math.floor(c / 4) % 4, (math.floor(c / 4) % 4) * 0x4000,
      math.floor(c / 256) % 32, (math.floor(c / 256) % 32) * 0x800,
      c % 4,
      (math.floor(c / 128) % 2 == 1) and "256color" or "16color"))
  end
  for bg = 0, 3 do
    put(string.format("BG%d HOFS=%d VOFS=%d", bg,
      rd16(0x04000010 + bg * 4), rd16(0x04000012 + bg * 4)))
  end

  local f = io.open(OUT_DIR .. "/" .. tag .. "_vram.bin", "wb")
  if f then
    local ch = {}
    for a = 0, 0x17FFF do
      ch[#ch + 1] = string.char(emu.read(a, emu.memType.gbaVideoRam, false))
      if #ch >= 4096 then f:write(table.concat(ch)); ch = {} end
    end
    if #ch > 0 then f:write(table.concat(ch)) end
    f:close(); put("saved vram")
  else
    put("!! vram 저장 실패 - AllowIoOsAccess 확인")
  end

  local p = io.open(OUT_DIR .. "/" .. tag .. "_palette.bin", "wb")
  if p then
    local ch = {}
    for a = 0, 0x3FF do ch[#ch + 1] = string.char(emu.read(a, emu.memType.gbaPaletteRam, false)) end
    p:write(table.concat(ch)); p:close()
  end

  local o = io.open(OUT_DIR .. "/" .. tag .. "_oam.bin", "wb")
  if o then
    local ch = {}
    for a = 0, 0x3FF do ch[#ch + 1] = string.char(emu.read(a, emu.memType.gbaSpriteRam, false)) end
    o:write(table.concat(ch)); o:close()
  end

  local png = emu.takeScreenshot()
  local s = io.open(OUT_DIR .. "/" .. tag .. "_screen.png", "wb")
  if s then s:write(png); s:close() end

  local g = io.open(OUT_DIR .. "/" .. tag .. "_bg.txt", "w")
  if g then g:write(table.concat(lines, "\n")); g:close() end
end

emu.addEventCallback(function()
  frame = frame + 1
  while idx <= #FRAMES and FRAMES[idx].frame <= frame do
    dumpAll(FRAMES[idx].name)
    idx = idx + 1
  end
  if frame >= MAX_FRAME or idx > #FRAMES then
    emu.log("done at frame " .. frame)
    emu.stop(0)
  end
end, emu.eventType.endFrame)
