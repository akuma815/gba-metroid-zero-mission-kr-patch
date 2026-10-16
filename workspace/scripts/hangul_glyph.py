"""TTF에서 게임 타일 글리프를 생성한다.

게임 글리프 형식(workspace/analysis/text_map.json 확정 구조):
- 코드 하나 = 8x16 = 상단 8x8 타일(0x4154BC + code*32) + 하단 8x8 타일(+0x400)
- 한자/전각은 인접 코드 쌍(짝수=좌반부, 홀수=우반부)으로 16x16을 이룬다.
- 렌더러는 글리프를 진행폭까지만 그린다(work/diag_layout.py 실증).
- 색은 4=본체, 1=외곽선 (원본 生 0x0F18 분석).

한글은 8px 폭에 들어가지 않으므로 전각(2코드 16x16) 방식을 쓴다.
픽셀 폰트는 그레이 렌더 후 이진화하면 자형이 뭉개지므로 FreeType 모노크롬 경로를 쓴다.
"""
from pathlib import Path

from PIL import Image, ImageFont

FONT_DIR = Path(r"G:\Downloads\Korean Traslate Project\Font")


def ink_bitmap(ch: str, ttf: str, size: int) -> list[list[int]]:
    """문자 하나를 힌팅된 모노크롬으로 렌더링해 잉크 영역 격자를 돌려준다."""
    font = ImageFont.truetype(str(FONT_DIR / ttf), size)
    mask = font.getmask(ch, mode="1")
    w, h = mask.size
    if w == 0 or h == 0:
        return []
    img = Image.frombuffer("L", (w, h), bytes(mask), "raw", "L", 0, 1)
    px = img.load()
    rows = [[1 if px[x, y] else 0 for x in range(w)] for y in range(h)]
    # 좌우·상하 공백 제거
    xs = [x for y in range(h) for x in range(w) if rows[y][x]]
    ys = [y for y in range(h) for x in range(w) if rows[y][x]]
    if not xs:
        return []
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    return [row[x0:x1 + 1] for row in rows[y0:y1 + 1]]


def place(ink: list[list[int]], box=(16, 16), at=(1, 3)) -> list[list[int]]:
    """잉크 격자를 셀 안 지정 위치에 배치한다. 넘치는 부분은 잘라낸다."""
    w, h = box
    out = [[0] * w for _ in range(h)]
    ox, oy = at
    for y, row in enumerate(ink):
        ty = oy + y
        if not 0 <= ty < h:
            continue
        for x, v in enumerate(row):
            tx = ox + x
            if v and 0 <= tx < w:
                out[ty][tx] = 1
    return out


def render_bitmap(ch: str, ttf: str, size: int, box=(16, 16), at=(1, 3)) -> list[list[int]]:
    """문자 하나를 box 크기 1비트 격자로 렌더링해 지정 위치에 배치한다."""
    return place(ink_bitmap(ch, ttf, size), box=box, at=at)


def outline(rows: list[list[int]], body: int = 4, edge: int = 1) -> list[list[int]]:
    """1비트 격자를 원본 폰트와 같은 [본체 body + 외곽선 edge] 2색 격자로 만든다."""
    h, w = len(rows), len(rows[0])
    out = [[body if rows[y][x] else 0 for x in range(w)] for y in range(h)]
    for y in range(h):
        for x in range(w):
            if rows[y][x]:
                continue
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w and rows[ny][nx]:
                        out[y][x] = edge
                        break
                else:
                    continue
                break
    return out


def _tile(rows8: list[list[int]], x0: int, color: int | None) -> bytes:
    """8x8 영역 -> GBA 4bpp 타일 32바이트.

    color=None 이면 격자 값을 그대로 색 인덱스로 쓴다(외곽선 포함 격자용).
    """
    out = bytearray()
    for y in range(8):
        for x in range(0, 8, 2):
            a, b = rows8[y][x0 + x], rows8[y][x0 + x + 1]
            lo = (a if color is None else (color if a else 0)) & 0xF
            hi = (b if color is None else (color if b else 0)) & 0xF
            out.append(lo | (hi << 4))
    return bytes(out)


def fullwidth_tiles(rows: list[list[int]], color: int | None = None):
    """16x16 픽셀 격자 -> 좌코드(상,하), 우코드(상,하) 타일 4개."""
    assert len(rows) == 16 and all(len(r) == 16 for r in rows)
    top, bottom = rows[:8], rows[8:]
    return {
        "left_top": _tile(top, 0, color),
        "left_bottom": _tile(bottom, 0, color),
        "right_top": _tile(top, 8, color),
        "right_bottom": _tile(bottom, 8, color),
    }


def glyph_extent(rows: list[list[int]]) -> tuple[int, int, int, int]:
    """격자의 (x0, x1, y0, y1) 잉크 범위."""
    h, w = len(rows), len(rows[0])
    xs = [x for y in range(h) for x in range(w) if rows[y][x]]
    ys = [y for y in range(h) for x in range(w) if rows[y][x]]
    return (min(xs), max(xs), min(ys), max(ys)) if xs else (0, -1, 0, -1)


def show(rows) -> str:
    """색 인덱스를 그대로 표시한다 (0=., 그 외는 16진 숫자)."""
    return "\n".join("".join(".123456789ABCDEF"[v] if v else "." for v in r) for r in rows)


if __name__ == "__main__":
    import sys

    text = sys.argv[1] if len(sys.argv) > 1 else "기계생명체파괴"
    for ttf, size, at in (("Galmuri11-Condensed.ttf", 11, (1, 3)),
                          ("Galmuri11-Condensed.ttf", 12, (1, 2)),
                          ("neodgm.ttf", 11, (0, 2))):
        widths = []
        for ch in text:
            g = outline(render_bitmap(ch, ttf, size, at=at))
            x0, x1, y0, y1 = glyph_extent(g)
            widths.append(x1 - x0 + 1)
        print(f"===== {ttf} {size}px at={at}: 글리프 폭 {min(widths)}-{max(widths)}px")
        g = outline(render_bitmap(text[0], ttf, size, at=at))
        print(show(g))
