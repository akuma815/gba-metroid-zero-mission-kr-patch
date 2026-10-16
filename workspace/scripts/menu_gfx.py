"""메뉴 그래픽(LZ77 블롭 0x458E70)의 일본어 문구를 한글로 교체한다.

구조 (workspace/analysis/menu_graphics.md)
  압축 0x458E70 -> 해제 21,504B = 8x8 타일 672개, VRAM 0x06000400 업로드

이 블롭은 두 구간으로 나뉜다.

  **큰 글씨** (타일 0~255, 16px 높이)
    타일을 32개씩 늘어놓으면 문구가 가로로 이어진다(픽셀 256x168).
    한 문구의 아랫줄 타일은 윗줄 +32 다. 진행폭 8px, 본체 색 5, 외곽선 색 8.
    파일 선택·OPTIONS 항목이 여기 있다.

  **작은 글씨** (타일 256~, 8px 높이)
    파일 선택 화면의 세이브 요약(난이도·지역명)이 쓰는 한 줄짜리 글씨다.
    타일 순서대로 이어지므로 32타일 격자가 아니라 **전 타일을 한 줄로 편 평면**에서
    다뤄야 한다. 32타일 경계를 넘는 단어(やさしい)가 있어 격자로 보면 끊겨 보인다.
    글자 색 1, 1px 테두리 색 6, 배경 투명. 실측 `work/small_zoom.py`.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bitmap_font import MENU  # noqa: E402
from lz77 import compress, decompress  # noqa: E402

BLOB = 0x458E70
COLS = 32
ADVANCE = 8
BODY_COLOR = 5
EDGE_COLOR = 8


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


def to_tiles(grid: list[list[int]]) -> bytes:
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


def glyph_2color(ch: str, outline: bool = False) -> list[list[int]]:
    """한글 한 글자를 8x12 격자에 그린다.

    기본은 본체(색 5)만 쓴다. 시트 본체가 7x11 로 셀을 거의 채워 외곽선을 두를
    여백이 없고, 한글은 획 간격이 1px 이라 외곽선이 획 사이를 메워 글자가 뭉갠다
    (work/menu_ko_preview.png 1차 시도에서 확인). 원본 가나는 획이 성겨서 외곽선이
    성립하지만 한글에는 맞지 않는다.
    """
    src = MENU.cell(ch)          # 8x12 1비트
    h, w = len(src), len(src[0])
    out = [[BODY_COLOR if src[y][x] else 0 for x in range(w)] for y in range(h)]
    if not outline:
        return out
    for y in range(h):
        for x in range(w):
            if src[y][x]:
                continue
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w and src[ny][nx]:
                        out[y][x] = EDGE_COLOR
                        break
                if out[y][x]:
                    break
    return out


ASCII_CACHE: dict[str, list[list[int]]] = {}


def capture_ascii(grid, ch: str, x0: int, y0: int, w: int = 8, h: int = 14):
    """원본 그래픽에서 기호 한 글자를 떠서 재사용한다(대괄호 등)."""
    ASCII_CACHE[ch] = [[grid[y0 + y][x0 + x] for x in range(w)] for y in range(h)]


def draw(grid, text: str, x0: int, y0: int, limit_px: int | None = None) -> int:
    """text 를 (x0, y0)부터 8px 간격으로 그린다. 반환은 사용한 픽셀 폭."""
    x = x0
    for ch in text:
        if ch == " ":
            x += ADVANCE
            continue
        if ch in ASCII_CACHE:
            g = ASCII_CACHE[ch]
        else:
            g = glyph_2color(ch)
        for yy, row in enumerate(g):
            for xx, v in enumerate(row):
                ty, tx = y0 + yy, x + xx
                if v and 0 <= ty < len(grid) and 0 <= tx < len(grid[0]):
                    grid[ty][tx] = v
        x += ADVANCE
        if limit_px is not None and x - x0 > limit_px:
            raise ValueError(f"'{text}' 가 허용 폭 {limit_px}px 를 넘었다")
    return x - x0


def clear(grid, x0: int, y0: int, x1: int, y1: int):
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            grid[y][x] = 0


def load(rom: bytes):
    raw, consumed = decompress(rom, BLOB)
    return to_grid(raw), consumed


def pack(grid) -> bytes:
    return compress(to_tiles(grid))


# --- 번역 계획 ---------------------------------------------------------------
# 각 항목: (한국어, 그릴 x, 허용 폭). 좌표는 해제 격자(256x168) 기준이며
# 원본 문구는 타일 경계(8px)에 정렬돼 있다. 근거 work/split_by_bracket.py
#
# 밴드별 계획. 좌표는 해제 격자(256x168) 기준이고 문구는 타일 경계(8px)에 정렬돼 있다.
# 화면 대응은 BG1 타일맵으로 확인했다(work/read_tilemap.py):
#   밴드 0 상단 = 블롭 타일 0-21, 하단 = 32-53
PLANS = [
    {   # 밴드 0 (y0-15): 파일 선택 화면
        "clear": (0, 0, 175, 15),
        "y": 1,
        "strings": [
            ("[데이터복사]", 0, 63),
            ("[데이터삭제]", 64, 56),
            ("[옵션]", 120, 56),
        ],
    },
    {   # 밴드 1 (y16-31): 사운드 / 사운드 테스트 / 타임 어택 기록
        "clear": (0, 16, 223, 31),
        "y": 17,
        "strings": [
            ("사운드", 0, 32),
            ("사운드 테스트", 56, 56),
            ("타임 어택 기록", 128, 88),
        ],
    },
    {   # 밴드 2 (y32-47): 갤러리 / 퓨전 데이터 읽기
        "clear": (0, 32, 223, 47),
        "y": 33,
        "strings": [
            ("갤러리", 0, 40),
            ("퓨전 데이터 읽기", 128, 88),
        ],
    },
    {   # 밴드 3 (y48-63): 퓨전 갤러리 / 오리지널 메트로이드
        "clear": (0, 48, 215, 63),
        "y": 49,
        "strings": [
            ("퓨전 갤러리", 0, 88),
            ("오리지널 메트로이드", 128, 80),
        ],
    },
]

# 대괄호는 원본에서 그대로 떠서 재사용한다(실측: '[' x0-4, ']' x58-62, y1-13)
BRACKETS = {"[": (0, 1, 5, 13), "]": (58, 1, 5, 13)}


def apply_translation(grid) -> list[str]:
    """번역 계획을 격자에 적용하고 적용 내역을 돌려준다."""
    for ch, (x, y, w, h) in BRACKETS.items():
        capture_ascii(grid, ch, x, y, w, h)

    log = []
    for p in PLANS:
        clear(grid, *p["clear"])
        for text, x0, limit in p["strings"]:
            used = draw(grid, text, x0, p["y"], limit_px=limit)
            log.append(f"{text} @x{x0},y{p['y']} {used}px/{limit}px")
    return log


# --- 작은 글씨 구간 (세이브 요약용 난이도·지역명) -----------------------------
# 파일 선택 화면에서 세이브 슬롯 옆에 뜨는 글씨다. 히라가나 모드로 저장하고
# 다시 켜면 그대로 가나가 나온다(사용자 제보). 큰 글씨와 달리 8px 한 줄이며
# 타일이 연속이라 '전 타일 한 줄' 평면 좌표로 다룬다.
#
# 각 항목: (한국어, 시작 타일, 끝 타일). 상자 폭 = (끝-시작+1)*8 px.
# 표기는 런타임과 맞춘다 — 난이도는 msg_b:042/043 의 쉬움/보통/어려움,
# 지역명은 용어집(msg_a:039~045).
SMALL_INK = 1        # 글자 (화면에서 흰색)
SMALL_EDGE = 6       # 1px 테두리
SMALL_BG = 0         # 투명
SMALL_DY = 1         # 원본 글자가 y1 부터 시작한다

SMALL_WORDS = [
    ("쉬움", 285, 288),          # やさしい
    ("보통", 290, 292),          # ふつう
    ("어려움", 295, 299),        # むずかしい
    ("크레테리아", 300, 304),    # クレテリア
    ("브린스타", 306, 310),      # ブリンスタ
    ("크레이드", 312, 315),      # クレイド
    ("노페어", 318, 322),        # ノルフェア
    ("리들리", 324, 327),        # リドリー
    ("투리안", 330, 334),        # ツーリアン
    ("초조디아", 336, 341),      # チョウゾディア
    ("타임 어택", 404, 408),     # タイムアタック
    # --- 영문 세트도 같이 바꾼다 ---
    # 이 블롭은 포인터로 언어를 고르는 자산이 아니라 **한 블롭 안에서 색인으로 세트를
    # 고른다**. 한자 모드에서는 영문 세트가 나오므로 여기까지 바꿔야 어느 모드든 한글이다.
    # (사용자 제보: 세이브 요약이 NORMAL/CRATERIA 로, 지도 구역 이동 화면도 영문으로 나왔다.)
    # 글자 색·테두리는 가나 세트와 같다(잉크 1, 테두리 6).
    ("크레테리아", 342, 347),    # CRATERIA
    ("브린스타", 348, 353),      # BRINSTAR
    ("크레이드", 354, 357),      # KRAID
    ("노페어", 360, 364),        # NORFAIR
    ("리들리", 366, 370),        # RIDLEY
    ("투리안", 372, 376),        # TOURIAN
    ("초조디아", 378, 383),      # CHOZODIA
    ("쉬움", 384, 386),          # EASY
    ("보통", 389, 392),          # NORMAL
    ("어려움", 394, 396),        # HARD
    ("타임 어택", 399, 403),     # TIME ATTACK
]


def apply_small(raw: bytes) -> tuple[bytes, list[str]]:
    """작은 글씨 구간을 한글로 교체한 타일 데이터를 돌려준다."""
    import obj_gfx      # 평면 격자·글자 그리기 공용 구현

    g = obj_gfx.to_grid(raw)          # 전 타일 한 줄
    log = []
    for ko, t0, t1 in SMALL_WORDS:
        box = (t0 * 8, 0, t1 * 8 + 7, 7)
        obj_gfx.clear(g, box, [SMALL_BG] * 8)
        used = obj_gfx.draw(g, ko, box, SMALL_INK, dy=SMALL_DY, halo=SMALL_EDGE)
        log.append(f"{ko} @t{t0}..{t1} {used}px/{(t1 - t0 + 1) * 8}px")
    return obj_gfx.to_tiles(g, len(raw) // 32), log
