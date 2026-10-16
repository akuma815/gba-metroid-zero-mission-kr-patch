-- 세이브스테이트를 로드해 그 화면의 BG 설정과 타일맵을 덤프한다.
-- 세이브스테이트는 ROM 파일명 기준으로 슬롯이 정해지므로, 러너가 ROM 이름을 유지해야 한다.

local OUT_DIR = "@@OUT_DIR@@"
local MAX_FRAME = @@MAX_FRAME@@
local SLOT = @@SLOT@@

local frame = 0
local log = {}
local function put(s) log[#log + 1] = s; emu.log(s) end

local function rd16(addr)
  return emu.read(addr, emu.memType.gbaMemory, false)
       + emu.read(addr + 1, emu.memType.gbaMemory, false) * 256
end

local loaded, dumped = false, false
local loadFrame = nil

-- loadSavestate 는 "exec memory operation callback" 안에서만 호출할 수 있다.
-- 그래서 ROM 실행 주소에 exec 콜백을 걸고 그 안에서 한 번만 로드한다.
local execCb
execCb = emu.addMemoryCallback(function()
  -- 게임이 충분히 초기화된 뒤 로드해야 상태가 온전히 복원된다
  if loaded or frame < @@LOADAT@@ then return end
  loaded = true
  loadFrame = frame
  local ok, err = pcall(function() emu.loadSavestate(SLOT) end)
  put("loadSavestate(" .. SLOT .. ") @frame " .. frame .. ": "
      .. (ok and "OK" or tostring(err)))
  emu.removeMemoryCallback(execCb, emu.callbackType.exec,
                           0x08000000, 0x08FFFFFF, nil, emu.memType.gbaMemory)
end, emu.callbackType.exec, 0x08000000, 0x08FFFFFF, nil, emu.memType.gbaMemory)

emu.addEventCallback(function()
  frame = frame + 1

  -- 로드 직후에는 화면이 아직 복구되지 않는다. 충분히 돌린 뒤 덤프한다.
  if loadFrame and frame == loadFrame + @@WAIT@@ and not dumped then
    dumped = true
    local dispcnt = rd16(0x04000000)
    put(string.format("DISPCNT=%04X", dispcnt))
    for bg = 0, 3 do
      local cnt = rd16(0x04000008 + bg * 2)
      put(string.format("BG%dCNT=%04X charbase %d(0x%05X) screenbase %d(0x%05X) prio %d",
        bg, cnt, math.floor(cnt / 4) % 4, (math.floor(cnt / 4) % 4) * 0x4000,
        math.floor(cnt / 256) % 32, (math.floor(cnt / 256) % 32) * 0x800, cnt % 4))
    end
    -- 스크롤도 함께(타일맵 좌표 보정에 필요)
    for bg = 0, 3 do
      put(string.format("BG%d HOFS=%d VOFS=%d", bg,
        rd16(0x04000010 + bg * 4), rd16(0x04000012 + bg * 4)))
    end

    local f = io.open(OUT_DIR .. "/vram.bin", "wb")
    if f then
      local ch = {}
      for a = 0, 0x17FFF do
        ch[#ch + 1] = string.char(emu.read(a, emu.memType.gbaVideoRam, false))
        if #ch >= 4096 then f:write(table.concat(ch)); ch = {} end
      end
      if #ch > 0 then f:write(table.concat(ch)) end
      f:close()
      put("dumped vram.bin (0x00000-0x17FFF)")
    end

    local png = emu.takeScreenshot()
    local p = io.open(OUT_DIR .. "/screen.png", "wb")
    if p then p:write(png); p:close() end
  end

  if frame >= MAX_FRAME then
    local g = io.open(OUT_DIR .. "/state.txt", "w")
    if g then g:write(table.concat(log, "\n")); g:close() end
    emu.stop(0)
  end
end, emu.eventType.endFrame)
