-- Mesen GUI 에서 직접 실행하는 스크립트.
-- 지금 화면 그대로의 BG 설정 / 타일맵 / VRAM / 스크린샷을 파일로 저장한다.
--
-- 사용법
--   1) 확인하려는 화면을 띄운 상태로 둔다 (예: 히라가나 모드에서 맵 열기)
--   2) 아래 TAG 를 이번 화면 이름으로 바꾼다 (파일 이름 앞에 붙는다)
--   3) Mesen 메뉴 → Debug → Script Window 열기
--   4) 이 파일을 열어 실행(F5)
--   5) qa/logs/live/ 에 <TAG>_ 로 시작하는 파일 5개가 생긴다
--
-- 게임이 멈춰 있어도 되고, 실행 중이어도 첫 프레임에 한 번만 덤프한다.
--
-- TAG 를 안 바꾸면 같은 이름을 덮어쓴다. qa/logs/baseline_map 은 패치 전 맵 화면
-- 기준 덤프이므로 지우지 말 것.

local TAG = "status"

local DIR = "G:/Downloads/Korean Traslate Project/Games/Metroid - Zero Mission/qa/logs/live"
local OUT = DIR .. "/" .. TAG

local done = false

local function rd16(a)
  return emu.read(a, emu.memType.gbaMemory, false)
       + emu.read(a + 1, emu.memType.gbaMemory, false) * 256
end

local function dump()
  local lines = {}
  local function put(s) lines[#lines + 1] = s; emu.log(s) end

  put(string.format("DISPCNT=%04X", rd16(0x04000000)))
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

  -- VRAM 전체 (BG 타일 + 타일맵 + OBJ)
  local f = io.open(OUT .. "_vram.bin", "wb")
  if f then
    local ch = {}
    for a = 0, 0x17FFF do
      ch[#ch + 1] = string.char(emu.read(a, emu.memType.gbaVideoRam, false))
      if #ch >= 4096 then f:write(table.concat(ch)); ch = {} end
    end
    if #ch > 0 then f:write(table.concat(ch)) end
    f:close()
    put("saved vram.bin (96KB)")
  else
    put("!! vram.bin 을 쓸 수 없다 - settings.json 의 AllowIoOsAccess 확인")
  end

  -- 팔레트
  local p = io.open(OUT .. "_palette.bin", "wb")
  if p then
    local ch = {}
    for a = 0, 0x3FF do
      ch[#ch + 1] = string.char(emu.read(a, emu.memType.gbaPaletteRam, false))
    end
    p:write(table.concat(ch)); p:close()
    put("saved palette.bin (1KB)")
  end

  -- OAM: 스프라이트가 어느 OBJ 타일을 참조하는지 알아내는 데 필요하다
  -- (맵 화면 지역명처럼 BG 가 아니라 OBJ 로 그려지는 텍스트 추적용)
  local o = io.open(OUT .. "_oam.bin", "wb")
  if o then
    local ch = {}
    for a = 0, 0x3FF do
      ch[#ch + 1] = string.char(emu.read(a, emu.memType.gbaSpriteRam, false))
    end
    o:write(table.concat(ch)); o:close()
    put("saved oam.bin (1KB)")
  else
    put("!! oam.bin 저장 실패")
  end

  -- 스크린샷
  local png = emu.takeScreenshot()
  local s = io.open(OUT .. "_screen.png", "wb")
  if s then s:write(png); s:close(); put("saved screen.png") end

  local g = io.open(OUT .. "_bg.txt", "w")
  if g then g:write(table.concat(lines, "\n")); g:close() end

  emu.displayMessage("Dump", "화면 정보를 qa/logs/live 에 저장했습니다")
end

emu.addEventCallback(function()
  if not done then
    done = true
    dump()
  end
end, emu.eventType.endFrame)
