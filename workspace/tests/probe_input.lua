-- 입력 API 구조 확인: getInput 이 돌려주는 키 이름과 포트를 알아낸다.
local OUT_DIR = "@@OUT_DIR@@"
local MAX_FRAME = @@MAX_FRAME@@

local frame = 0
local log = {}
local function put(s) log[#log + 1] = s; emu.log(s) end

-- API 존재 여부
do
  local names = {}
  for k, v in pairs(emu) do
    if type(v) == "function" and (k:lower():find("input") or k:lower():find("button")) then
      names[#names + 1] = k
    end
  end
  table.sort(names)
  put("input 관련 API: " .. table.concat(names, ", "))
end

-- eventType 목록
do
  local names = {}
  for k, _ in pairs(emu.eventType) do names[#names + 1] = k end
  table.sort(names)
  put("eventType: " .. table.concat(names, ","))
end

-- 포트별 getInput 구조
for port = 0, 1 do
  local ok, res = pcall(emu.getInput, port)
  if ok and type(res) == "table" then
    local keys = {}
    for k, v in pairs(res) do keys[#keys + 1] = k .. "=" .. tostring(v) end
    table.sort(keys)
    put(string.format("getInput(%d): %s", port, table.concat(keys, " ")))
  else
    put(string.format("getInput(%d) 실패: %s", port, tostring(res)))
  end
end

emu.addEventCallback(function()
  frame = frame + 1
  if frame >= MAX_FRAME then
    local f = io.open(OUT_DIR .. "/probe_input.txt", "w")
    if f then f:write(table.concat(log, "\n")); f:close() end
    emu.stop(0)
  end
end, emu.eventType.endFrame)
