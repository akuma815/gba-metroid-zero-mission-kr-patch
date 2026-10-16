"""언어별 그래픽 텍스트 자산(가나 블롭)의 일본어를 한글로 교체한다.

구조 (workspace/analysis/obj_graphics.md)
  포인터 테이블 0x760214~ 에 7언어 슬롯 그룹이 나열된다.
  lang0(한자)은 영문 자산을, lang1(히라가나)만 가나 자산을 쓴다.
  채택 방식 B: lang1 블롭의 가나를 한글로 바꾸고 lang0 포인터를 그 주소로 돌린다.
  lang2~6(영어권)은 자기 블롭을 그대로 쓰므로 영문이 남는다.

배치 규칙
  블롭은 8x8 4bpp 타일의 1차원 배열이고, BG 타일맵/OBJ 스프라이트가 타일 번호로
  참조한다. 그 참조는 언어와 무관하게 같으므로 **각 라벨의 타일 범위를 바꾸면 안 된다.**
  글자만 범위 안에서 다시 그린다.

폰트
  셀 높이가 8px 뿐이라 본문용(12px)을 쓸 수 없다. bitmap_font.SMALL
  (Galmuri7_8x8.png, 잉크 7x7) 을 진행폭 8px 로 쓴다.

배경 복원
  라벨 상자 안에서 **행별 최빈색**을 배경으로 본다. 글자는 상자 안에서 소수라
  최빈색이 곧 판 색이다. 판이 세로 그라데이션이면 행마다 값이 달라지므로 행 단위로 잡는다.
  (영문/가나 '같은 픽셀'만 세는 방식은 두 언어의 글자 색이 우연히 겹쳐 실패했다 —
   맵 UI 의 エリアチェンジ 에서 배경이 2/3 줄무늬로 나왔다.)
  판정이 애매한 라벨은 정의에 bg 를 직접 적어 덮어쓴다.

투명 배경 라벨
  같은 문구가 '판 위'와 '투명 배경 위' 두 벌로 들어 있는 경우가 있다.
  투명 쪽은 글자 둘레 1px 를 판 색으로 두른 형태다(halo). 실측: 맵 UI 의
  エリアチェンジ 두 벌은 글자(3/4) 는 같고 배경만 2 <-> 0 이며 0 쪽에 1px 테두리 2 가 있다.
"""
import struct
import sys
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bitmap_font import BODY, SMALL  # noqa: E402
from lz77 import compress, decompress  # noqa: E402

ADVANCE = 8


# --- 그룹 정의 -----------------------------------------------------------------
# box = (x0, y0, x1, y1) 해제 격자 좌표. 격자는 '전체 타일을 한 줄'로 편 것이다.
# ink = 글자 색인. dy = 글자 세로 오프셋(기본 0 = 상자 위 맞춤).

GROUPS = {
    "map_ui": {
        "slot": 0x760284, "en": 0x4006F4, "ja": 0x40BE94,
        "desc": "맵 UI 라벨",
        "labels": [
            # 판 구조: y0 회색바 / y1 검정테 / y2 밝은자주 / y3~y7 몸통.
            # 판 아래 절반은 다른 타일(BG1 r1 t673~675, 3칸이 같은 타일 반복)이라
            # 확장할 수 없다. 즉 **글자가 들어갈 곳은 y2..y7 6줄뿐**이다. 8x8 시트(잉크 7px)를 dy=1 로 놓으면 검정
            # 테두리(y1)를 먹어 글자가 판을 넘은 것처럼 보인다(사용자 제보).
            # 6px 로 렌더되는 Galmuri7@7px 를 dy=2 로 써서 몸통 안에 정확히 넣는다.
            {"ko": "슬립", "box": (6, 0, 33, 7), "ink": 11, "dy": 2,
             "ttf": ("Galmuri7.ttf", 7)},
            {"ko": "상태", "box": (46, 0, 73, 7), "ink": 11, "dy": 2,
             "ttf": ("Galmuri7.ttf", 7)},
            # エリアチェンジ 두 벌. 앞은 투명 배경 + 1px 테두리, 뒤는 판 위.
            {"ko": "구역 이동", "box": (80, 0, 127, 7), "ink": 3, "bg": 0, "halo": 2, "dy": 1},
            {"ko": "구역 이동", "box": (128, 0, 175, 7), "ink": 3, "bg": 2, "dy": 1},
        ],
    },
    "late_items": {
        "slot": 0x76024C, "en": 0x402DAC, "ja": 0x40C7A8,
        "desc": "후반 아이템 이름(플라즈마·스페이스 점프·그래비티)",
        # 160x8 한 줄짜리 판. 왼쪽 x0..x6 은 아이콘이라 건드리지 않는다.
        # 판 배경은 세로 [1,6,4,5,5,5,5,6], 글자는 3. 라벨 타일 범위는 영문/가나가 같다.
        # '스페이스 점프'는 7칸(56px)이라 48px 상자에 안 들어가 띄어쓰기를 뺐다.
        "labels": [
            {"ko": "플라즈마", "box": (8, 0, 39, 7), "ink": 3,
             "bg": [1, 6, 4, 5, 5, 5, 5, 6], "dy": 1},
            {"ko": "스페이스점프", "box": (48, 0, 95, 7), "ink": 3,
             "bg": [1, 6, 4, 5, 5, 5, 5, 6], "dy": 1},
            {"ko": "그래비티", "box": (104, 0, 143, 7), "ink": 3,
             "bg": [1, 6, 4, 5, 5, 5, 5, 6], "dy": 1},
        ],
    },
    "area_big": {
        "slot": 0x760230, "en": 0x402EB0, "ja": 0x40CE1C,
        "desc": "지역명(큰 글씨) — 지역 진입 배너",
        # 2D OBJ 매핑(DISPCNT=0x1E00, bit6=0)이라 VRAM 한 줄이 32타일이다.
        # 64x16 라벨 하나가 윗줄 8타일 + 아랫줄(=+32) 8타일로 이뤄진다.
        # 배경은 전부 투명(0), 글자는 본체 6 + 외곽선 1 — 원본 가나와 같은 규약이다.
        "stride": 32,
        "sheet": BODY,          # 셀 9x12, 잉크 7x11. 외곽선을 두르면 9x13 이 된다.
        "advance": 11,
        "labels": [
            {"ko": ko, "box": (64 * i, 0, 64 * i + 63, 15),
             "ink": 6, "halo": 1, "bg": 0, "dy": 2}
            for i, ko in enumerate(["크레테리아", "브린스타", "크레이드", "노페어"])
        ],
    },
    "status": {
        "slot": 0x760268, "en": 0x400864, "ja": 0x409760,
        "desc": "스테이터스 화면 항목 이름",
        # BG 타일 768(charbase 1)에 올라간다. 라벨은 연속 타일 구간이며 영문/가나가
        # 같은 구간을 쓴다. 판은 두 종류다:
        #   타일 0..36   배경 [1,6,8,8,8,8,8,2]        획 1 (+ 7/5/4 하이라이트)
        #   타일 54..159 배경 [1,14,12,13,13,13,13,14] 획 6 (단색)
        # 앞 판의 원본 글자는 획 1 에 한쪽만 밝은 색을 덧댄 입체 표현이고 잉크행이
        # y2..y6(5px)뿐이다. 한글은 7px 라 입체 표현을 재현할 자리가 없어 획만 그린다.
        # 타일 37..53 은 언어와 무관한 게이지 그래픽이라 손대지 않는다.
        "labels": [
            {"ko": ko, "box": (t0 * 8, 0, t1 * 8 + 7, 7), "dy": 1,
             **({"ink": 1, "bg": [1, 6, 8, 8, 8, 8, 8, 2]} if t0 < 40 else
                {"ink": 6, "bg": [1, 14, 12, 13, 13, 13, 13, 14]})}
            for ko, t0, t1 in [
                ("에너지", 0, 5), ("빔", 6, 9), ("미사일", 11, 16), ("봄", 17, 20),
                ("슈트", 22, 24), ("어빌리티", 28, 32), ("건", 34, 36),
                ("롱", 54, 56), ("차지", 59, 62), ("아이스", 64, 66),
                ("웨이브", 69, 72), ("플라즈마", 74, 77), ("노멀", 79, 82),
                ("슈퍼", 84, 87), ("노멀", 89, 92), ("파워", 96, 99),
                ("배리어", 100, 102), ("그래비티", 105, 109), ("모프볼", 112, 117),
                ("파워 그립", 119, 125), ("스피드 부스터", 128, 134),
                ("하이 점프", 135, 139), ("스크류 어택", 141, 147),
                # 상자가 48px 뿐이라 '스페이스 점프'(56px)는 띄어쓰기를 뺐다
                ("스페이스점프", 148, 153), ("핸드건", 155, 159),
            ]
        ],
    },
    "gameover": {
        "slot": 0x760C00, "en": 0x451CE0, "ja": 0x452214,
        "desc": "게임 오버 화면 (계속하시겠습니까 / 예 / 아니오)",
        # 192타일, 격자 256x48. 글자가 16px 높이라 본문 시트(9x12)를 진행폭 10px 로 쓴다.
        # 원본은 본체 + 그림자 2색이다: 1행 본체 5·그림자 6, 선택지 본체 10·그림자 11.
        # **괄호와 물음표는 시트에 없으므로 상자에서 빼 원본을 그대로 남긴다**
        # (실측: 1행 ？ x192..199, 2행 （x94..98 ）x210..214, 3행 （x94..98 ）x202..206).
        "stride": 32,
        "sheet": BODY,
        "advance": 10,
        "labels": [
            {"ko": "게임을 계속하시겠습니까", "box": (56, 0, 188, 15),
             "ink": 5, "halo": 6, "bg": 0, "dy": 2},
            {"ko": "예", "box": (48, 16, 71, 31),
             "ink": 10, "halo": 11, "bg": 0, "dy": 2},
            {"ko": "게임을 계속한다", "box": (102, 16, 206, 31),
             "ink": 10, "halo": 11, "bg": 0, "dy": 2},
            {"ko": "아니오", "box": (48, 32, 84, 47),
             "ink": 10, "halo": 11, "bg": 0, "dy": 2},
            {"ko": "타이틀로 돌아간다", "box": (102, 32, 198, 47),
             "ink": 10, "halo": 11, "bg": 0, "dy": 2},
        ],
    },
    "area_small": {
        "slot": 0x760214, "en": 0x402A4C, "ja": 0x40BB7C,
        "desc": "지역명(작은 글씨)",
        "labels": [
            {"ko": ko, "box": (48 * i + 4, 0, 48 * i + 43, 7), "ink": 14}
            for i, ko in enumerate(
                ["크레테리아", "브린스타", "크레이드", "노페어", "리들리", "투리안", "초조디아"])
        ] + [
            {"ko": ko, "box": (48 * (i + 7) + 4, 0, 48 * (i + 7) + 43, 7), "ink": 1}
            for i, ko in enumerate(
                ["크레테리아", "브린스타", "크레이드", "노페어", "리들리", "투리안", "초조디아"])
        ],
    },
}


# --- 격자 변환 -----------------------------------------------------------------

def to_grid(raw: bytes, cols: int | None = None) -> list[list[int]]:
    """블롭을 색인 격자로 편다.

    cols=None 이면 타일 전체를 한 줄로 늘어놓는다(8px 높이 라벨용).
    cols 를 주면 그만큼씩 줄바꿈한다 — 2D OBJ 매핑(VRAM 한 줄 = 32타일)에서
    16px 이상 높이 라벨은 아랫줄 타일이 stride 만큼 떨어져 있기 때문이다.
    """
    nt = len(raw) // 32
    c = nt if cols is None else cols
    rows = (nt + c - 1) // c
    g = [[0] * (c * 8) for _ in range(rows * 8)]
    for t in range(nt):
        tx, ty = (t % c) * 8, (t // c) * 8
        for y in range(8):
            for xb in range(4):
                b = raw[t * 32 + y * 4 + xb]
                g[ty + y][tx + xb * 2] = b & 0xF
                g[ty + y][tx + xb * 2 + 1] = b >> 4
    return g


def to_tiles(grid: list[list[int]], nt: int | None = None) -> bytes:
    c = len(grid[0]) // 8
    n = c * (len(grid) // 8) if nt is None else nt
    out = bytearray(n * 32)
    for t in range(n):
        tx, ty = (t % c) * 8, (t // c) * 8
        for y in range(8):
            for xb in range(4):
                lo = grid[ty + y][tx + xb * 2] & 0xF
                hi = grid[ty + y][tx + xb * 2 + 1] & 0xF
                out[t * 32 + y * 4 + xb] = lo | (hi << 4)
    return bytes(out)


# --- 배경 복원 -----------------------------------------------------------------

def bg_profile(ja: list[list[int]], box) -> list[int]:
    """상자 안 행별 배경색(최빈색)을 돌려준다."""
    x0, y0, x1, y1 = box
    return [Counter(ja[y][x] for x in range(x0, x1 + 1)).most_common(1)[0][0]
            for y in range(y0, y1 + 1)]


def clear(grid, box, prof):
    x0, y0, x1, y1 = box
    for i, y in enumerate(range(y0, y1 + 1)):
        for x in range(x0, x1 + 1):
            grid[y][x] = prof[i]


def text_width(text: str, advance: int = ADVANCE) -> int:
    return len(text) * advance


def draw(grid, text: str, box, ink: int, dy: int = 0, halo: int | None = None,
         sheet=SMALL, advance: int = ADVANCE, ttf: tuple | None = None) -> int:
    """상자 안 가운데에 한글을 그린다. 넘치면 예외.

    halo 를 주면 글자 둘레 1px 를 그 색으로 두른다(투명 배경 라벨·외곽선 글꼴용).
    ttf=(파일, 크기) 를 주면 시트 대신 TTF 를 모노크롬으로 렌더한다.
    판 몸통이 6px 뿐인 자리처럼 8x8 시트(잉크 7px)가 안 들어갈 때 쓴다.
    """
    from hangul_glyph import ink_bitmap

    x0, y0, x1, y1 = box
    bw = x1 - x0 + 1
    w = text_width(text, advance)
    if w > bw:
        raise ValueError(f"'{text}' {w}px 가 상자 폭 {bw}px 를 넘었다")
    sx = x0 + (bw - w) // 2
    put = []
    for i, ch in enumerate(text):
        if ch == " ":
            continue
        if ttf:
            cell = ink_bitmap(ch, ttf[0], ttf[1])
            gw = max(len(r) for r in cell)
            off = (advance - gw) // 2
        else:
            cell, off = sheet.cell(ch), 0
        for yy, row in enumerate(cell):
            for xx, v in enumerate(row):
                if v:
                    put.append((y0 + dy + yy, sx + i * advance + off + xx))
    inked = set(put)
    if halo is not None:
        for Y, X in put:
            for ny in (Y - 1, Y, Y + 1):
                for nx in (X - 1, X, X + 1):
                    if (ny, nx) in inked:
                        continue
                    if y0 <= ny <= y1 and x0 <= nx <= x1:
                        grid[ny][nx] = halo
    for Y, X in put:
        if y0 <= Y <= y1 and x0 <= X <= x1:
            grid[Y][X] = ink
    return w


# --- 적용 ---------------------------------------------------------------------

def apply_group(rom: bytes, gid: str):
    """한 그룹을 교체해 (블롭주소, 새 압축, 원본 압축크기, 슬롯주소, 로그)를 돌려준다."""
    g = GROUPS[gid]
    ja_raw, ja_size = decompress(rom, g["ja"])
    en_raw, _ = decompress(rom, g["en"])
    if len(en_raw) != len(ja_raw):
        raise ValueError(f"{gid}: 영문/가나 해제 크기가 다르다 {len(en_raw)} != {len(ja_raw)}")
    cols = g.get("stride")
    sheet = g.get("sheet", SMALL)
    adv = g.get("advance", ADVANCE)
    grid = to_grid(ja_raw, cols)
    ja_orig = to_grid(ja_raw, cols)   # 배경 판정은 손대지 않은 원본으로만 한다

    log = []
    for lab in g["labels"]:
        box = lab["box"]
        y0, y1 = box[1], box[3]
        prof = ([lab["bg"]] * (y1 - y0 + 1) if isinstance(lab.get("bg"), int)
                else lab.get("bg") or bg_profile(ja_orig, box))
        clear(grid, box, prof)
        w = draw(grid, lab["ko"], box, lab["ink"], lab.get("dy", 0), lab.get("halo"),
                 sheet, adv, lab.get("ttf"))
        x0, x1 = box[0], box[2]
        halo = f" 테두리{lab['halo']}" if lab.get("halo") is not None else ""
        log.append(f"{lab['ko']} @x{x0}..{x1} {w}px/{x1 - x0 + 1}px "
                   f"배경{prof} 잉크{lab['ink']}{halo}")

    # 한글은 가나보다 획이 촘촘해 배경 반복이 줄고 압축률이 떨어진다.
    # 원본 압축 크기 안에 넣어야 하므로 최소 비용 경로로 압축한다.
    packed = compress(to_tiles(grid, len(ja_raw) // 32), optimal=True)
    return g["ja"], packed, ja_size, g["slot"], log


def all_groups(rom: bytes):
    for gid in GROUPS:
        yield gid, apply_group(rom, gid)


def lang0_patch(rom: bytes, gid: str) -> tuple[int, bytes, bytes]:
    """lang0 슬롯을 lang1 블롭으로 돌리는 (오프셋, 기대 원본, 새 값)."""
    g = GROUPS[gid]
    off = g["slot"]
    return off, rom[off:off + 4], struct.pack("<I", 0x08000000 | g["ja"])
