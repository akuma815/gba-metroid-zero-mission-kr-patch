-- 타이틀에서 START 로 진입해 파일 선택·옵션 화면을 캡처한다.
-- setInput 은 부분 테이블이 아니라 getInput 으로 받은 전체 상태를 되돌려 주는 방식을 쓴다.

local OUT_DIR = "@@OUT_DIR@@"
local MAX_FRAME = @@MAX_FRAME@@

local frame = 0
local press = {}          -- frame -> {버튼 이름들}
local shots = {}          -- frame -> 파일명

-- 아래 줄에 러너가 입력·캡처 계획을 주입한다(주석 줄에 두면 다음 줄이 주석에 먹혀 문법 오류가 난다)
@@PLAN@@

-- 주의: getInput(port) 과 달리 setInput 은 (input, port) 순서다.
-- 반대로 넘기면 "bad argument #1 to 'setInput' (table expected, got number)" 로 스크립트가 죽는다.
emu.addEventCallback(function()
  local want = press[frame]
  if want then
    local inp = emu.getInput(0)
    for _, btn in ipairs(want) do inp[btn] = true end
    emu.setInput(inp, 0)
  end
end, emu.eventType.inputPolled)

emu.addEventCallback(function()
  frame = frame + 1
  local name = shots[frame]
  if name then
    local png = emu.takeScreenshot()
    local f = io.open(string.format("%s/%05d_%s.png", OUT_DIR, frame, name), "wb")
    if f then f:write(png); f:close() end
  end
  if frame >= MAX_FRAME then emu.stop(0) end
end, emu.eventType.endFrame)
