-- 지도 지역명 라벨 칸만 강제로 보이게 한다 (QA 전용).
--
-- 게임은 지도 칸마다 가시성 비트(SRAM 0x380 + 구역번호*128B, 32x32, LSB 우선)를 보고
-- 0 인 칸을 배경 타일로 덮는다. 라벨 칸 비트는 그 라벨을 처음 발견할 때 켜지고
-- 폭은 그때의 타일맵을 따르므로, **한글화 이전 세이브**로는 넓어진 라벨의 마지막
-- 글자가 빠져 보인다. 이 스크립트가 그 칸들을 대신 켜 준다.
--
-- 지도 전체를 켜지 않고 **라벨 칸만** 건드리므로 탐사 표시는 그대로다.
-- 다만 게임에서 세이브하면 이 상태가 세이브에 굳는다 — 검증용 세이브로만 쓸 것.
--
-- Mesen GUI -> Debug -> Script Window 에서 F5.
local MT = emu.memType.gbaSaveRam
local BITS = {
  {0x394, 0x07},  -- 브린스타/TOURIAN
  {0x3B0, 0x3E},  -- 브린스타/CRATERIA
  {0x3BA, 0xE0},  -- 브린스타/NORFAIR
  {0x3D0, 0xE0},  -- 브린스타/KRAID
  {0x3D1, 0x01},  -- 브린스타/KRAID
  {0x40C, 0x80},  -- 크레이드/BRINSTAR
  {0x40D, 0x07},  -- 크레이드/BRINSTAR
  {0x488, 0xF0},  -- 노페어/CRATERIA
  {0x489, 0xF1},  -- 노페어/BRINSTAR, 노페어/CRATERIA
  {0x4BE, 0x07},  -- 노페어/RIDLEY
  {0x501, 0xC0},  -- 리들리/NORFAIR
  {0x502, 0x01},  -- 리들리/NORFAIR
  {0x582, 0x3E},  -- 투리안/CRATERIA
  {0x586, 0x78},  -- 투리안/BRINSTAR
  {0x60F, 0x1E},  -- 크레테리아/CHOZODIA
  {0x61F, 0x1E},  -- 크레테리아/CHOZODIA
  {0x625, 0xC0},  -- 크레테리아/NORFAIR
  {0x626, 0x01},  -- 크레테리아/NORFAIR
  {0x631, 0x0F},  -- 크레테리아/BRINSTAR
  {0x638, 0x1C},  -- 크레테리아/TOURIAN
}
-- 비트 연산자(|)는 Lua 판마다 없을 수 있어 산술로만 켠다.
local function setbits(cur, mask)
  local out = cur
  local m = 1
  for _ = 0, 7 do
    if math.floor(mask / m) % 2 == 1 and math.floor(out / m) % 2 == 0 then out = out + m end
    m = m * 2
  end
  return out
end

-- **불러오기 전에 SRAM 을 건드리면 안 된다.** 세이브에는 검사값이 있어서 한 바이트만
-- 달라도 게임이 파일을 버리고 새 게임을 시작한다. 그래서 게임플레이에 들어간 뒤
-- (에너지가 60프레임 연속 0 이 아닐 때)부터 쓴다.
local ENERGY = 0x1536          -- IWRAM, 사무스 현재 에너지 (u16)
local IW = emu.memType.gbaIntWorkRam
local EW = emu.memType.gbaExtWorkRam
local EW_BASES = {0x037080, 0x038000, 0x03B660}   -- SRAM 오프셋 + 이 값 = EWRAM 사본
local alive = 0
local armed = false

emu.addEventCallback(function()
  if not armed then
    local e = emu.read(ENERGY, IW) + emu.read(ENERGY + 1, IW) * 256
    if e > 0 and e <= 1299 then alive = alive + 1 else alive = 0 end
    if alive < 60 then return end
    armed = true
  end
  for _, e in ipairs(BITS) do
    local cur = emu.read(e[1], MT)
    local want = setbits(cur, e[2])
    if want ~= cur then emu.write(e[1], want, MT) end
    for _, b in ipairs(EW_BASES) do            -- EWRAM 작업 사본 3곳
      local a = e[1] + b
      local c2 = emu.read(a, EW)
      local w2 = setbits(c2, e[2])
      if w2 ~= c2 then emu.write(a, w2, EW) end
    end
  end
end, emu.eventType.startFrame)
