-- 상태 개입 검증: 자막 팔레트(BG pal15)의 색 6만 빨강으로 덮어쓰고 화면을 캡처한다.
-- 이는 ROM 패치가 아니라 런타임 팔레트 개입이며, 색상 제어코드 판정에만 쓴다.
-- 원본 ROM 이면 자막은 색 4(흰색)로 그려져 변화가 없어야 하고,
-- <8106> 를 넣은 ROM 이면 그 뒤 글자가 색 6(빨강)으로 그려져야 한다.

local OUT_DIR = "@@OUT_DIR@@"
local MAX_FRAME = @@MAX_FRAME@@
local PAL15_C6 = 15 * 32 + 6 * 2   -- BG 팔레트 15, 인덱스 6
local RED = 0x001F                  -- BGR555 순수 빨강

local frame = 0

emu.addEventCallback(function()
  frame = frame + 1
  -- 자막 표시 구간에서만 덮어쓴다(게임이 매 프레임 팔레트를 갱신할 수 있다)
  if frame >= 840 then
    emu.write(PAL15_C6, RED % 256, emu.memType.gbaPaletteRam)
    emu.write(PAL15_C6 + 1, math.floor(RED / 256), emu.memType.gbaPaletteRam)
  end

  if frame == 850 then
    local png = emu.takeScreenshot()
    local f = io.open(OUT_DIR .. "/color_test.png", "wb")
    if f then f:write(png); f:close(); emu.log("saved color_test.png") end
  end
  if frame >= MAX_FRAME then
    emu.stop(0)
  end
end, emu.eventType.endFrame)
