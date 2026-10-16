-- 통 플레이 QA 용 무적 스크립트 (ROM 은 건드리지 않는다).
--
-- 왜 ROM 패치가 아니라 Lua 인가
--   배포할 바이너리와 **똑같은 ROM** 을 테스트해야 한다. ROM 에 치트를 넣으면
--   치트가 유발한 문제를 번역 문제로 오인할 수 있다.
--
-- 원리
--   사무스의 현재 에너지는 IWRAM 0x03001536 (u16) 이다.
--   (work/probe_energy.lua 로 후보 11개에 값을 써 보고 HUD 가 바뀌는 것으로 확정.
--    옆의 0x03001530 은 최대치로 보이나 게임이 현재치를 그때그때 깎지는 않는다.)
--   최대치를 몰라도 되도록, **줄어들면 되돌리는** 방식을 쓴다.
--   늘어나면(회복·에너지 탱크) 그 값을 새 기준으로 삼는다.
--
-- 사용법
--   1) Mesen 으로 패치 ROM 을 띄우고 게임을 시작한다
--   2) Debug -> Script Window 에서 이 파일을 실행(F5)
--   3) 왼쪽 위에 표시가 뜨고, 피격해도 에너지가 즉시 돌아온다
--   4) 끄려면 스크립트 창을 닫는다

local ADDR = 0x1536          -- IWRAM 상대 오프셋 (= 0x03001536)
local IW = emu.memType.gbaIntWorkRam
local MIN, MAX = 1, 2000     -- 이 범위 밖이면 게임 상태가 아니라고 보고 건드리지 않는다

local keep = nil
local restored = 0

local function r16() return emu.read(ADDR, IW, false) + emu.read(ADDR + 1, IW, false) * 256 end
local function w16(v)
  emu.write(ADDR, v % 256, IW)
  emu.write(ADDR + 1, math.floor(v / 256), IW)
end

emu.addEventCallback(function()
  local cur = r16()
  if cur < MIN or cur > MAX then
    keep = nil                       -- 메뉴·전환 중이면 기준을 버린다
    return
  end
  if keep == nil or cur > keep then
    keep = cur                       -- 회복·에너지 탱크 획득
  elseif cur < keep then
    w16(keep)                        -- 피격 취소
    restored = restored + 1
  end
end, emu.eventType.endFrame)

emu.addEventCallback(function()
  emu.drawString(4, 4, string.format("무적 ON  E=%s  복구 %d",
    keep and tostring(keep) or "-", restored), 0xFFFF60, 0x000000)
end, emu.eventType.startFrame)

emu.log("무적 스크립트 시작 - 에너지 0x03001536 을 감시한다")
