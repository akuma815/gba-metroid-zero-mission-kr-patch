-- 전 구역 지도를 전부 밝힌다 (QA 전용).
--
-- 게임은 지도 칸마다 가시성 비트를 보고 0 인 칸을 배경 타일로 덮는다.
--   저장본 : SRAM 0x380 + 구역번호*128B (구역당 32x32 비트, LSB 우선)
--   작업본 : EWRAM 사본 3곳 — 화면은 이쪽을 따른다. **둘 다 써야 한다.**
--
-- 주의 두 가지
--   1) 세이브에는 검사값이 있어 **불러오기 전에 SRAM 을 건드리면 파일이 버려진다.**
--      그래서 게임플레이에 들어간 뒤(에너지가 60프레임 연속 정상)부터 쓴다.
--   2) 이 상태로 게임에서 저장하면 "지도 전부 밝힘"이 세이브에 굳는다.
--      검증용 세이브로만 쓰고, 진행용 세이브는 미리 백업할 것.
--
-- Mesen GUI -> Debug -> Script Window 에서 F5.
local MT = emu.memType.gbaSaveRam
local EW = emu.memType.gbaExtWorkRam
local IW = emu.memType.gbaIntWorkRam
local EW_BASES = {0x037080, 0x038000, 0x03B660}   -- SRAM 오프셋 + 이 값 = EWRAM 사본
local FIRST, LAST = 0x380, 0x700                  -- 7구역 x 128B
local ENERGY = 0x1536                             -- IWRAM, 사무스 현재 에너지 (u16)

local alive, armed, cursor = 0, false, FIRST

emu.addEventCallback(function()
  if not armed then
    local e = emu.read(ENERGY, IW) + emu.read(ENERGY + 1, IW) * 256
    if e > 0 and e <= 1299 then alive = alive + 1 else alive = 0 end
    if alive < 60 then return end
    armed = true
  end
  for _ = 1, 96 do                                -- 프레임당 조금씩 훑는다
    if emu.read(cursor, MT) ~= 0xFF then emu.write(cursor, 0xFF, MT) end
    for _, b in ipairs(EW_BASES) do
      local a = cursor + b
      if emu.read(a, EW) ~= 0xFF then emu.write(a, 0xFF, EW) end
    end
    cursor = cursor + 1
    if cursor >= LAST then cursor = FIRST end
  end
end, emu.eventType.startFrame)
