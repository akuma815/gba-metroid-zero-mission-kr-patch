"""통신(링크 케이블) 화면의 일본어 문구를 한글로 교체한다.

자산 (workspace/analysis/comm_graphics.md)
  ROM 0x75C2E4~0x75E617 에 LZ77 블롭이 빈틈없이 이어져 있다. 그 안에 링크 완료/실패
  문구가 **일본어 5벌 + 영어 1벌**씩 들어 있다. 포인터로 가리키는 곳이 없어
  (코드가 배열 위치를 계산해 쓰는 것으로 보인다) 언어 슬롯 표로는 찾을 수 없었다.
  ROM 전역 LZ77 블롭 680개를 훑어 글자처럼 보이는 것을 걸러 찾았다.

구조
  완료 문구 : 256x32px (128타일). y1~y14 가 문구, 일부 벌은 y16~ 에 표식 글자 1개.
  실패 문구 : 256x16px (64타일).  y1~y14 가 문구.
  색은 **본체 4 / 외곽선 1 / 배경 0**. (메뉴 그래픽의 본체5/외곽선8 과 반대다.)

한글 그리기
  본체만 색 4 로 그린다. 한글은 획 간격이 1px 이라 외곽선을 두르면 획 사이가 메워져
  뭉갠다(menu_gfx 에서 확인한 교훈). 마침표 `。` 는 시트에 없으므로 원본에서 떠서 쓴다.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import obj_gfx  # noqa: E402
from bitmap_font import MENU  # noqa: E402
from lz77 import compress, decompress  # noqa: E402

COLS = 32               # 타일 가로 개수 (256px)
BAND = (0, 0, 255, 15)  # 문구 밴드 x0..255 / y0..15
INK = 4                 # 본체
DY = 1                  # 원본 글자가 y1 부터 시작한다
ADVANCE = 11            # 원본 가나 폭에 맞춘 진행폭

# (주소, 종류). 종류별 문구는 TEXT 참조.
BLOBS = [
    (0x75C4DC, "done"), (0x75CB8C, "done"), (0x75CEE8, "done"),
    (0x75D244, "done"), (0x75D598, "done"),
    (0x75D8F4, "error"), (0x75DD2C, "error"), (0x75DF68, "error"),
    (0x75E1A4, "error"), (0x75E3D8, "error"),
]

# **문구는 런타임 원장(ko.json)의 승인 번역과 글자까지 맞춘다.** 같은 문장이 메시지로도
# 나오므로(msg_b:051 / msg_b:056) 다르면 화면마다 표현이 갈린다.
TEXT = {
    # つうしんが おわりました。 でんげんを きってください。  == msg_b:051
    "done": "통신이 끝났습니다。 전원을 꺼 주세요。",
    # つうしんエラーです。 やりなおしてください。            == msg_b:056
    "error": "통신 에러입니다。 다시 해 주세요。",
}

# 원본에서 떠 쓸 기호 `。` — 실측으로 **5x5**, 밴드 기준 y10~y14 에 앉는다.
# 글자끼리 붙어 있어 빈 열로 잘라낼 수 없으므로 마지막 잉크 x 에서 왼쪽 5px 를 뜬다.
PERIOD_W, PERIOD_H, PERIOD_Y = 5, 5, 10


def _last_run_end(grid) -> int:
    """문구 밴드에서 잉크가 있는 마지막 x 를 돌려준다."""
    for x in range(len(grid[0]) - 1, -1, -1):
        if any(grid[y][x] for y in range(BAND[1], BAND[3] + 1)):
            return x
    raise ValueError("문구를 찾지 못했다")


def capture_period(grid):
    """원본 문구 끝의 `。` 를 떠서 obj_gfx 의 기호 캐시에 넣는다."""
    x1 = _last_run_end(grid)
    x0 = x1 - PERIOD_W + 1
    return [[grid[BAND[1] + PERIOD_Y + y][x0 + x] for x in range(PERIOD_W)]
            for y in range(PERIOD_H)]


PERIOD_ADVANCE = 7      # 마침표는 좁게 붙인다


def text_width(text: str) -> int:
    return sum(PERIOD_ADVANCE if ch == "。" else ADVANCE for ch in text)


def apply_one(rom: bytes, addr: int, kind: str):
    """(주소, 재압축본, 원본 압축 크기, 로그) 를 돌려준다."""
    raw, csize = decompress(rom, addr)
    nt = len(raw) // 32
    grid = obj_gfx.to_grid(raw, COLS)

    period = capture_period(grid)
    obj_gfx.clear(grid, BAND, [0] * (BAND[3] - BAND[1] + 1))

    text = TEXT[kind]
    for ch in text:
        if ch not in (" ", "。") and not MENU.has(ch):
            raise ValueError(f"시트에 없는 글자: {ch!r}")

    w = text_width(text)
    if w > BAND[2] - BAND[0] + 1:
        raise ValueError(f"'{text}' 가 {w}px 로 밴드({BAND[2] - BAND[0] + 1}px)를 넘는다")
    x = (BAND[2] - BAND[0] + 1 - w) // 2

    for ch in text:
        if ch == " ":
            x += ADVANCE
            continue
        mark = ch == "。"
        cellimg = period if mark else MENU.cell(ch)
        y0 = BAND[1] + (PERIOD_Y if mark else DY)
        for yy, row in enumerate(cellimg):
            for xx, v in enumerate(row):
                if not v:
                    continue
                ty, tx = y0 + yy, x + xx
                if 0 <= ty <= BAND[3] and 0 <= tx <= BAND[2]:
                    grid[ty][tx] = v if mark else INK
        x += PERIOD_ADVANCE if mark else ADVANCE

    packed = compress(obj_gfx.to_tiles(grid, nt), optimal=True)
    log = f"0x{addr:06X} {kind:5s} {w}px  압축 {csize} -> {len(packed)}B"
    return addr, packed, csize, log


def apply(rom: bytes):
    """(쓰기 목록, 로그) 를 돌려준다."""
    writes, log = [], []
    for addr, kind in BLOBS:
        a, packed, csize, line = apply_one(rom, addr, kind)
        writes.append((a, packed, csize))
        log.append(line + ("  OK" if len(packed) <= csize else
                           f"  초과 {len(packed) - csize}B"))
    return writes, log
