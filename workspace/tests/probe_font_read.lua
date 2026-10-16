-- 폰트 영역 읽기 추적 + 실행 ROM 신원 확인
-- 1) 로드된 ROM에서 PoC 마커 바이트를 직접 읽어 신원을 확인한다.
-- 2) 폰트 영역(0x08415000-0x08442000) 읽기 접근을 프레임별로 집계한다.

local OUT_DIR = "@@OUT_DIR@@"
local MAX_FRAME = @@MAX_FRAME@@

local frame = 0
local log = {}

local function put(s)
  log[#log + 1] = s
  emu.log(s)
end

-- memType 이름 나열 (빌드별 차이 확인용)
do
  local names = {}
  for k, _ in pairs(emu.memType) do names[#names + 1] = k end
  table.sort(names)
  put("memType: " .. table.concat(names, ","))
end

-- 실행 중인 ROM의 폰트 바이트 확인 (0x4154BC + 0x85*32 = 0x41655C)
do
  local parts = {}
  for i = 0, 15 do
    parts[#parts + 1] = string.format("%02X", emu.read(0x41655C + i, emu.memType.gbaPrgRom, false))
  end
  put("rom@0x41655C: " .. table.concat(parts, " "))
end

-- 폰트 영역 읽기 카운터
local hits = {}
local total = 0
emu.addMemoryCallback(function(addr, value)
  total = total + 1
  local key = frame
  hits[key] = (hits[key] or 0) + 1
end, emu.callbackType.read, 0x415000, 0x442000, nil, emu.memType.gbaPrgRom)

emu.addEventCallback(function()
  frame = frame + 1
  if hits[frame - 1] and hits[frame - 1] > 0 then
    put(string.format("frame %d: font reads = %d", frame - 1, hits[frame - 1]))
  end
  if frame >= MAX_FRAME then
    put("total font reads = " .. total)
    local f = io.open(OUT_DIR .. "/probe_font_read.txt", "w")
    if f then
      f:write(table.concat(log, "\n"))
      f:close()
    end
    emu.stop(0)
  end
end, emu.eventType.endFrame)
