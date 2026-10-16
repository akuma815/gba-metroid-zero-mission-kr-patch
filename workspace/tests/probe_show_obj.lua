-- OBJ VRAM 에 이미 올라와 있는 타일을 OAM 에 직접 꽂아 강제로 화면에 띄운다.
--
-- 왜 필요한가
--   후반 아이템 이름(플라즈마/스페이스점프/그래비티)과 지역 진입 배너는 게임을
--   한참 진행해야 나온다. 그런데 두 자산은 **맵 화면에서 이미 OBJ VRAM 에 올라가 있다**
--   (work/qa_verify.py 로 바이트 동일 확인). OAM 은 그냥 RAM 이므로 스프라이트 항목을
--   직접 써 넣으면 실제 하드웨어 경로로 그 타일이 그려진다.
--
--   특히 진입 배너의 **2D OBJ 매핑 가정(아랫줄 타일 = 윗줄 +32)** 을 실기로 검증한다.
--   가정이 틀렸으면 글자가 반쯤 잘린 모양으로 나온다.
--
-- 확인하지 못하는 것
--   게임이 이 라벨을 화면 어디에 어떤 팔레트로 놓는지는 알 수 없다. 자산이 온전히
--   그려지는지만 본다.
--
-- 사용법
--   1) 맵 화면(START)을 띄운다 — 이때 두 자산이 OBJ VRAM 에 올라간다
--   2) Mesen 메뉴 → Debug → Script Window 에서 이 파일을 실행(F5)
--   3) 화면 위쪽에 후반 아이템 3개, 그 아래 배너 4개가 겹쳐 뜬다
--   4) PAL 을 바꿔가며 팔레트를 고를 수 있다 (기본 5 = 지역명이 쓰는 뱅크)
--   5) SHOT_FRAME 프레임 뒤 스크린샷이 저장된다

local OUT = "G:/Downloads/Korean Traslate Project/Games/Metroid - Zero Mission/qa/logs/live"
local TAG = "objprobe"
local PAL = 5            -- 팔레트 뱅크 0~15
local SHOT_FRAME = 30

-- OAM 슬롯은 뒤쪽(64~)을 쓴다. 맵 화면은 앞쪽 9개만 쓴다.
local SLOT0 = 64

-- 그릴 것: {VRAM 타일, 가로타일, 세로타일, 화면x, 화면y}
-- 후반 아이템 블롭 = OBJ 타일 160~179 (20타일, 8px 높이)
--   1..4 플라즈마 / 6..11 스페이스점프 / 13..17 그래비티  (블롭 기준)
-- 진입 배너 블롭 = OBJ 타일 192~255 (64타일). 라벨 하나 = 64x16 = 32x16 두 장.
local SPRITES = {
  -- 후반 아이템 20타일을 32x8(4x1) 다섯 장으로 이어 붙인다
  { 160, 4, 1,   8,  16 },
  { 164, 4, 1,  40,  16 },
  { 168, 4, 1,  72,  16 },
  { 172, 4, 1, 104,  16 },
  { 176, 4, 1, 136,  16 },
  -- 배너 4개 (각 64x16 = 32x16 두 장). 아랫줄 타일은 하드웨어가 +32 에서 가져간다.
  { 192, 4, 2,   8,  32 }, { 196, 4, 2,  40,  32 },
  { 200, 4, 2,   8,  52 }, { 204, 4, 2,  40,  52 },
  { 208, 4, 2,   8,  72 }, { 212, 4, 2,  40,  72 },
  { 216, 4, 2,   8,  92 }, { 220, 4, 2,  40,  92 },
}

local frame = 0
local shot = false

local function rd16(a)
  return emu.read(a, emu.memType.gbaMemory, false)
       + emu.read(a + 1, emu.memType.gbaMemory, false) * 256
end

local function wr16(off, v)
  emu.write(off, v % 256, emu.memType.gbaSpriteRam)
  emu.write(off + 1, math.floor(v / 256) % 256, emu.memType.gbaSpriteRam)
end

-- (가로타일, 세로타일) -> (shape, size)
local function shapeSize(w, h)
  if w == h then
    local s = ({ [1] = 0, [2] = 1, [4] = 2, [8] = 3 })[w]
    return 0, s
  elseif w > h then
    if w == 2 and h == 1 then return 1, 0 end
    if w == 4 and h == 1 then return 1, 1 end
    if w == 4 and h == 2 then return 1, 2 end
    if w == 8 and h == 4 then return 1, 3 end
  else
    if w == 1 and h == 2 then return 2, 0 end
    if w == 1 and h == 4 then return 2, 1 end
    if w == 2 and h == 4 then return 2, 2 end
    if w == 4 and h == 8 then return 2, 3 end
  end
  return nil
end

local function inject()
  for i, s in ipairs(SPRITES) do
    local tile, tw, th, x, y = s[1], s[2], s[3], s[4], s[5]
    local shape, size = shapeSize(tw, th)
    if shape then
      local off = (SLOT0 + i - 1) * 8
      wr16(off,     (y % 256) + shape * 0x4000)               -- attr0
      wr16(off + 2, (x % 512) + size * 0x4000)                -- attr1
      wr16(off + 4, tile % 1024 + PAL * 0x1000)               -- attr2 (prio 0)
      wr16(off + 6, 0)
    end
  end
end

local function onFrame()
  frame = frame + 1
  inject()

  if frame == 2 then
    local d = rd16(0x04000000)
    emu.log(string.format("DISPCNT=%04X  OBJ 매핑=%s", d,
      (math.floor(d / 64) % 2 == 1) and "1D" or "2D(아랫줄=+32)"))
    emu.log(string.format("팔레트 뱅크 %d, OAM 슬롯 %d부터 %d개 주입",
      PAL, SLOT0, #SPRITES))
  end

  if frame == SHOT_FRAME and not shot then
    shot = true
    local png = emu.takeScreenshot()
    local f = io.open(OUT .. "/" .. TAG .. "_screen.png", "wb")
    if f then
      f:write(png); f:close()
      emu.log("saved " .. TAG .. "_screen.png")
    else
      emu.log("!! 스크린샷 저장 실패 - settings.json 의 AllowIoOsAccess 확인")
    end
    -- 팔레트도 같이 남긴다(색 판정용)
    local p = io.open(OUT .. "/" .. TAG .. "_palette.bin", "wb")
    if p then
      local ch = {}
      for a = 0, 0x3FF do
        ch[#ch + 1] = string.char(emu.read(a, emu.memType.gbaPaletteRam, false))
      end
      p:write(table.concat(ch)); p:close()
    end
    emu.displayMessage("Probe", "OBJ 주입 스크린샷 저장")
  end
end

-- 게임은 VBlank 에 OAM 을 갱신한다. 렌더 직전인 startFrame 에 써야 우리 값이 남는다.
-- startFrame 이 없는 빌드에서는 endFrame 으로 떨어뜨린다.
local ok = pcall(function()
  emu.addEventCallback(onFrame, emu.eventType.startFrame)
end)
if not ok then
  emu.log("startFrame 미지원 - endFrame 으로 대체(스프라이트가 안 보이면 이 때문이다)")
  emu.addEventCallback(onFrame, emu.eventType.endFrame)
end
