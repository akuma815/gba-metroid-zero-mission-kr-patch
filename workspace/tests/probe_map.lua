-- 맵 화면(히라가나 모드)의 BG 설정과 타일맵을 덤프한다.
-- 지역명 'ブリンスタ' 가 참조하는 타일 번호를 알아내는 것이 목적이다.

local OUT_DIR = "@@OUT_DIR@@"
local MAX_FRAME = @@MAX_FRAME@@

local frame = 0
local log = {}
local function put(s) log[#log + 1] = s; emu.log(s) end

local press = {}
local function hold(from, to, btns)
  for f = from, to do press[f] = btns end
end

-- 타이틀 통과
hold(2450, 2469, {"start"})
-- 파일 선택에서 A
hold(2640, 2646, {"a"})
-- 메시지 옵션에서 아래로 이동 후 A (히라가나 모드 선택)
hold(2760, 2766, {"down"})
hold(2800, 2806, {"a"})
-- 인트로 스킵
hold(2900, 2906, {"a"})
hold(3000, 3006, {"start"})
hold(3100, 3106, {"start"})
hold(3300, 3306, {"a"})
-- 게임 중 맵 열기
hold(@@MAPFRAME@@, @@MAPFRAME@@ + 8, {"start"})

emu.addEventCallback(function()
  local want = press[frame]
  if want then
    local inp = emu.getInput(0)
    for _, b in ipairs(want) do inp[b] = true end
    emu.setInput(inp, 0)
  end
end, emu.eventType.inputPolled)

local function rd16(addr)
  return emu.read(addr, emu.memType.gbaMemory, false)
       + emu.read(addr + 1, emu.memType.gbaMemory, false) * 256
end

local dumped = false
emu.addEventCallback(function()
  frame = frame + 1

  if frame >= @@SHOT@@ and not dumped then
    dumped = true
    local dispcnt = rd16(0x04000000)
    put(string.format("frame %d DISPCNT=%04X", frame, dispcnt))
    for bg = 0, 3 do
      local cnt = rd16(0x04000008 + bg * 2)
      put(string.format("BG%dCNT=%04X charbase %d screenbase %d(0x%05X)",
        bg, cnt, math.floor(cnt / 4) % 4,
        math.floor(cnt / 256) % 32, (math.floor(cnt / 256) % 32) * 0x800))
    end
    local f = io.open(OUT_DIR .. "/vram_map.bin", "wb")
    if f then
      local ch = {}
      for a = 0, 0xFFFF do
        ch[#ch + 1] = string.char(emu.read(a, emu.memType.gbaVideoRam, false))
        if #ch >= 4096 then f:write(table.concat(ch)); ch = {} end
      end
      if #ch > 0 then f:write(table.concat(ch)) end
      f:close()
      put("dumped vram_map.bin")
    end
    local png = emu.takeScreenshot()
    local p = io.open(OUT_DIR .. "/map.png", "wb")
    if p then p:write(png); p:close() end
    local g = io.open(OUT_DIR .. "/bg.txt", "w")
    if g then g:write(table.concat(log, "\n")); g:close() end
  end

  if frame >= MAX_FRAME then emu.stop(0) end
end, emu.eventType.endFrame)
