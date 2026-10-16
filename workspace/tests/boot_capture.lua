-- Mesen 2 testRunner 스크립트: 무수정 GBA ROM 부팅 기준선 캡처
-- 지정 프레임에서 스크린샷을 저장하고 마지막에 emu.stop(0)으로 종료한다.
-- 출력 경로는 OUT_DIR 플레이스홀더를 러너가 치환한다.

local OUT_DIR = "@@OUT_DIR@@"
local SHOTS = @@SHOTS@@   -- { {frame=..., name=...}, ... }

local frame = 0
local idx = 1

local function save(name)
  local png = emu.takeScreenshot()
  local path = OUT_DIR .. "/" .. name .. ".png"
  local f = io.open(path, "wb")
  if f then
    f:write(png)
    f:close()
    emu.log("saved " .. path)
  else
    emu.log("FAILED to open " .. path)
  end
end

emu.addEventCallback(function()
  frame = frame + 1
  while idx <= #SHOTS and SHOTS[idx].frame <= frame do
    save(string.format("%05d_%s", SHOTS[idx].frame, SHOTS[idx].name))
    idx = idx + 1
  end
  if idx > #SHOTS then
    emu.log("done at frame " .. frame)
    emu.stop(0)
  end
end, emu.eventType.endFrame)

emu.log("boot_capture started")
