"""비트맵 폰트 시트 로더.

시트는 한글 완성형 유니코드 순서로 배열된 2색 PNG다(인덱스 = ord(ch) - 0xAC00, 11,172자).

  Galmuri11-Condensed_9x12.png  셀 9x12, 본체 7x11 — 본문 메시지용(진행폭 10px)
  Galmuri11-Condensed_8x12.png  셀 8x12, 본체 7x11 — 메뉴 그래픽용(진행폭 8px)
  Galmuri7_8x8.png              셀 8x8,  본체 7x7  — OBJ/BG 그래픽 텍스트용(진행폭 8px)

메뉴용은 셀이 8px 뿐이라 외곽선을 온전히 두를 수 없다. 원본 가나도 본체와 외곽선이
8px 를 꽉 채우므로(work/menu_glyph_spec.py) 같은 방식으로 셀 경계에서 잘라 쓴다.
"""
from pathlib import Path

from PIL import Image

FONT_DIR = Path(r"G:\Downloads\Korean Traslate Project\Font")
HANGUL_BASE = 0xAC00
HANGUL_COUNT = 11172

# 기본(본문용) 시트
SHEET = "Galmuri11-Condensed_9x12.png"
CELL_W, CELL_H = 9, 12
COLS = 64


class Sheet:
    """하나의 비트맵 시트."""

    def __init__(self, name: str, cell_w: int, cell_h: int, cols: int = 64):
        self.name = name
        self.cell_w = cell_w
        self.cell_h = cell_h
        self.cols = cols
        self._img = None
        self._cache: dict[str, list[list[int]]] = {}

    def _load(self):
        if self._img is None:
            im = Image.open(FONT_DIR / self.name).convert("L")
            self._img = im.load(), im.size
        return self._img

    def has(self, ch: str) -> bool:
        return 0 <= ord(ch) - HANGUL_BASE < HANGUL_COUNT

    def cell(self, ch: str) -> list[list[int]]:
        if ch in self._cache:
            return self._cache[ch]
        idx = ord(ch) - HANGUL_BASE
        if not 0 <= idx < HANGUL_COUNT:
            raise KeyError(f"시트에 없는 문자: {ch!r} (U+{ord(ch):04X})")
        px, (w, h) = self._load()
        x0 = (idx % self.cols) * self.cell_w
        y0 = (idx // self.cols) * self.cell_h
        if x0 + self.cell_w > w or y0 + self.cell_h > h:
            raise KeyError(f"시트 범위 밖: {ch!r} idx={idx}")
        rows = [[1 if px[x0 + x, y0 + y] > 96 else 0 for x in range(self.cell_w)]
                for y in range(self.cell_h)]
        self._cache[ch] = rows
        return rows

    def ink_extent(self, ch: str):
        rows = self.cell(ch)
        xs = [x for y in range(self.cell_h) for x in range(self.cell_w) if rows[y][x]]
        ys = [y for y in range(self.cell_h) for x in range(self.cell_w) if rows[y][x]]
        return (min(xs), max(xs), min(ys), max(ys)) if xs else (0, -1, 0, -1)

    def place_in_cell(self, ch: str, box=(16, 16), at=(0, 2)) -> list[list[int]]:
        """시트 잉크를 지정 크기 격자에 배치한다(넘치면 잘린다)."""
        rows = self.cell(ch)
        w, h = box
        out = [[0] * w for _ in range(h)]
        ox, oy = at
        for y, row in enumerate(rows):
            ty = oy + y
            if not 0 <= ty < h:
                continue
            for x, v in enumerate(row):
                tx = ox + x
                if v and 0 <= tx < w:
                    out[ty][tx] = 1
        return out


BODY = Sheet(SHEET, 9, 12)          # 본문 메시지용
MENU = Sheet("Galmuri11-Condensed_8x12.png", 8, 12)   # 메뉴 그래픽용
SMALL = Sheet("Galmuri7_8x8.png", 8, 8)               # OBJ/BG 그래픽 텍스트용(셀 높이 8px)

# 하위 호환: 기존 호출부는 본문 시트를 쓴다
def has(ch: str) -> bool:
    return BODY.has(ch)


def cell(ch: str):
    return BODY.cell(ch)


def ink_extent(ch: str):
    return BODY.ink_extent(ch)


def place_in_cell(ch: str, box=(16, 16), at=(0, 2)):
    return BODY.place_in_cell(ch, box=box, at=at)


if __name__ == "__main__":
    import sys

    sample = sys.argv[1] if len(sys.argv) > 1 else "데이터복사옵션"
    for sh in (BODY, MENU):
        ws, hs = [], []
        for ch in sample:
            x0, x1, y0, y1 = sh.ink_extent(ch)
            ws.append(x1 - x0 + 1)
            hs.append(y1 - y0 + 1)
        print(f"{sh.name}  셀 {sh.cell_w}x{sh.cell_h}: "
              f"본체 {min(ws)}~{max(ws)} x {min(hs)}~{max(hs)}px")
