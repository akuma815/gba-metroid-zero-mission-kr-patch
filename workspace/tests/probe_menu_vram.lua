-- 파일 선택 화면의 타일 데이터를 VRAM 에서 덤프한다.
-- 폰트를 쓰지 않는 그래픽 자산이므로, 화면에 올라온 타일을 그대로 받아
-- ROM 에서 역검색해 원본 위치를 찾는다.

local OUT_DIR = "@@OUT_DIR@@"
local MAX_FRAME = @@MAX_FRAME@@

local frame = 0
local press = {}
for f = 2450, 2469 do press[f] = true end

emu.addEventCallback(function()
  if press[frame] then
    local inp = emu.getInput(0)
    inp.start = true
    emu.setInput(inp, 0)
  end
end, emu.eventType.inputPolled)

local function dumpVram(tag)
  -- GBA VRAM 0x00000-0x17FFF. 타일 데이터 구간을 통째로 받는다.
  local f = io.open(string.format("%s/vram_%s.bin", OUT_DIR, tag), "wb")
  if not f then return end
  local chunk = {}
  for addr = 0, 0x17FFF do
    chunk[#chunk + 1] = string.char(emu.read(addr, emu.memType.gbaVideoRam, false))
    if #chunk >= 4096 then
      f:write(table.concat(chunk))
      chunk = {}
    end
  end
  if #chunk > 0 then f:write(table.concat(chunk)) end
  f:close()
  emu.log("dumped vram_" .. tag)
end

emu.addEventCallback(function()
  frame = frame + 1
  if frame == 2700 then
    dumpVram("fileselect")
    local png = emu.takeScreenshot()
    local p = io.open(OUT_DIR .. "/fileselect.png", "wb")
    if p then p:write(png); p:close() end
  end
  if frame >= MAX_FRAME then emu.stop(0) end
end, emu.eventType.endFrame)
