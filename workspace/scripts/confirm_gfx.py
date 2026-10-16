"""데이터 삭제 확인 화면(LZ77 블롭 2개)의 일본어를 한글로 교체한다.

0x760530 테이블 = 7언어 x 2 블롭. lang0/1(일본어)이 아래 둘을 공유한다.
  0x4138EC  1차 확인: すべての「サムスデータ」をけし / しょきのじょうたいにもどしますか？
  0x41250C  2차 확인: ほんとうに すべての「サムスデータ」を / けしてもよろしいですか？
각 블롭 128타일(256x32px)이며 우측에 いいえ / はい 선택지가 있다.

색 규약이 메뉴 그래픽과 다르다: **배경 15, 외곽선 3, 본체 2**.
한글은 획 간격이 좁아 외곽선을 두르면 뭉개지므로 진한 색(3)으로 획만 그린다.
진행폭은 메뉴와 같은 8px.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bitmap_font import MENU  # noqa: E402
from lz77 import compress, decompress  # noqa: E402

COLS = 32
ADVANCE = 8
BG = 15
INK = 3          # 원본의 외곽선 색. 배경 15 위에서 가장 진하다.

BLOBS = {
    0x4138EC: {
        "lines": [
            # (한국어, x, y, 허용폭). 선택지가 x200 부터라 x24 기준 168px 까지 안전하다
            ("모든 사무스 데이터를 지우고", 24, 1, 168),
            ("초기 상태로 되돌리시겠습니까?", 24, 17, 168),
            ("아니오", 200, 1, 25),
            ("예", 200, 17, 17),
        ],
        "clear": [(24, 0, 191, 15), (24, 16, 191, 31),
                  (200, 0, 231, 15), (200, 16, 231, 31)],
    },
    0x41250C: {
        "lines": [
            ("정말로 모든 사무스 데이터를", 16, 1, 176),
            # 원본 줄2는 96px 로 짧지만 선택지가 x200 부터라 x16 기준 176px 까지 안전하다
            ("지워도 괜찮으시겠습니까?", 16, 17, 176),
            ("아니오", 200, 1, 25),
            ("예", 200, 17, 17),
        ],
        "clear": [(16, 0, 191, 15), (16, 16, 191, 31),
                  (200, 0, 231, 15), (200, 16, 231, 31)],
    },
}


def to_grid(raw: bytes) -> list[list[int]]:
    nt = len(raw) // 32
    w, h = COLS * 8, (nt // COLS) * 8
    g = [[0] * w for _ in range(h)]
    for t in range(nt):
        tx, ty = (t % COLS) * 8, (t // COLS) * 8
        for y in range(8):
            for xb in range(4):
                b = raw[t * 32 + y * 4 + xb]
                g[ty + y][tx + xb * 2] = b & 0xF
                g[ty + y][tx + xb * 2 + 1] = b >> 4
    return g


def to_tiles(grid) -> bytes:
    h, w = len(grid), len(grid[0])
    nt = (w // 8) * (h // 8)
    out = bytearray(nt * 32)
    for t in range(nt):
        tx, ty = (t % COLS) * 8, (t // COLS) * 8
        for y in range(8):
            for xb in range(4):
                lo = grid[ty + y][tx + xb * 2] & 0xF
                hi = grid[ty + y][tx + xb * 2 + 1] & 0xF
                out[t * 32 + y * 4 + xb] = lo | (hi << 4)
    return bytes(out)


def clear(grid, x0, y0, x1, y1):
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            grid[y][x] = BG


# 시트에 없는 기호는 원본에서 그대로 떠서 쓴다.
# 물음표는 0x4138EC 줄2 끝(x152-159, y17-29)의 전각 '？'.
CAPTURED: dict[str, list[list[int]]] = {}


def capture(grid, ch: str, x0: int, y0: int, w: int = 8, h: int = 13):
    CAPTURED[ch] = [[grid[y0 + y][x0 + x] for x in range(w)] for y in range(h)]


def draw(grid, text: str, x0: int, y0: int, limit_px: int) -> int:
    x = x0
    for ch in text:
        if ch == " ":
            x += ADVANCE
            if x - x0 > limit_px:
                raise ValueError(f"'{text}' 가 허용 폭 {limit_px}px 를 넘었다 ({x - x0}px)")
            continue
        if ch in CAPTURED:
            # 원본에서 뜬 기호는 색까지 그대로 옮긴다
            for yy, row in enumerate(CAPTURED[ch]):
                for xx, v in enumerate(row):
                    ty, tx = y0 + yy, x + xx
                    if 0 <= ty < len(grid) and 0 <= tx < len(grid[0]):
                        grid[ty][tx] = v
        else:
            for yy, row in enumerate(MENU.cell(ch)):
                for xx, v in enumerate(row):
                    ty, tx = y0 + yy, x + xx
                    if v and 0 <= ty < len(grid) and 0 <= tx < len(grid[0]):
                        grid[ty][tx] = INK
        x += ADVANCE
        if x - x0 > limit_px:
            raise ValueError(f"'{text}' 가 허용 폭 {limit_px}px 를 넘었다 ({x - x0}px)")
    return x - x0


def apply(rom: bytes) -> list[tuple[int, bytes, int, list[str]]]:
    """각 블롭을 교체해 (주소, 새 압축데이터, 원본 압축크기, 로그)를 돌려준다."""
    result = []
    # 물음표를 먼저 확보한다(지우기 전에 떠야 한다)
    ref, _ = decompress(rom, 0x4138EC)
    capture(to_grid(ref), "?", 152, 17)

    for base, plan in BLOBS.items():
        raw, orig_size = decompress(rom, base)
        grid = to_grid(raw)
        for box in plan["clear"]:
            clear(grid, *box)
        log = []
        for text, x, y, limit in plan["lines"]:
            used = draw(grid, text, x, y, limit)
            log.append(f"{text} @x{x},y{y} {used}px/{limit}px")
        packed = compress(to_tiles(grid))
        result.append((base, packed, orig_size, log))
    return result
