-- 게임을 시작해 맵 화면을 열고 그 시점의 BG 설정·타일맵을 덤프한다.
-- 맵 화면 판정: BG 설정이 바뀌고 화면에 지역명이 뜨는 프레임을 여러 번 캡처해 고른다.

local OUT_DIR = "@@OUT_DIR@@"
local MAX_FRAME = @@MAX_FRAME@@

local frame = 0
local log = {}
local function put(s) log[#log + 1] = s; emu.log(s) end

local press = {}
local function hold(a, b, btns)
  for f = a, b do press[f] = btns end
end

hold(2450, 2470, {"start"})     -- 타이틀 통과
hold(2640, 2650, {"a"})         -- 파일 선택
hold(2760, 2770, {"a"})         -- 메시지 옵션 확정(기본=첫 항목)
-- 인트로 스킵: A/START 를 길게 반복
for f = 2900, 5200, 12 do
  hold(f, f + 4, {"start"})
end
-- 게임 중 맵 열기 시도
for f = 5400, 7000, 60 do
  hold(f, f + 6, {"start"})
end

emu.addEventCallback(function()
  local w = press[frame]
  if w then
    local inp = emu.getInput(0)
    for _, b in ipairs(w) do inp[b] = true end
    emu.setInput(inp, 0)
  end
end, emu.eventType.inputPolled)

local function rd16(a)
  return emu.read(a, emu.memType.gbaMemory, false)
       + emu.read(a + 1, emu.memType.gbaMemory, false) * 256
end

local shots = {}
for _, f in ipairs({5300, 5500, 5700, 5900, 6100, 6300, 6500, 6700, 6900}) do
  shots[f] = true
end

emu.addEventCallback(function()
  frame = frame + 1
  if shots[frame] then
    local png = emu.takeScreenshot()
    local p = io.open(string.format("%s/%05d.png", OUT_DIR, frame), "wb")
    if p then p:write(png); p:close() end
    put(string.format("f%d DISPCNT=%04X BG0=%04X BG1=%04X BG2=%04X BG3=%04X",
      frame, rd16(0x04000000), rd16(0x04000008), rd16(0x0400000A),
      rd16(0x0400000C), rd16(0x0400000E)))
  end
  if frame >= MAX_FRAME then
    local g = io.open(OUT_DIR .. "/scan.txt", "w")
    if g then g:write(table.concat(log, "\n")); g:close() end
    emu.stop(0)
  end
end, emu.eventType.endFrame)
