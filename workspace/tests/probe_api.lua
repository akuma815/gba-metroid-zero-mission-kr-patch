-- emu 네임스페이스의 함수 목록을 덤프한다(세이브스테이트 API 확인용).
local OUT_DIR = "@@OUT_DIR@@"
local MAX_FRAME = @@MAX_FRAME@@

local log = {}
local function put(s) log[#log + 1] = s; emu.log(s) end

local names = {}
for k, v in pairs(emu) do
  if type(v) == "function" then names[#names + 1] = k end
end
table.sort(names)
put("emu functions: " .. table.concat(names, ", "))

local f = 0
emu.addEventCallback(function()
  f = f + 1
  if f >= MAX_FRAME then
    local h = io.open(OUT_DIR .. "/api.txt", "w")
    if h then h:write(table.concat(log, "\n")); h:close() end
    emu.stop(0)
  end
end, emu.eventType.endFrame)
