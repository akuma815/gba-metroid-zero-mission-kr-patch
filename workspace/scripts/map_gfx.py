"""구역 이동/지역 지도 화면의 지역명 라벨을 한글로 교체한다.

구조 (workspace/analysis/obj_graphics.md)
  타일셋  : **비압축** ROM 0x40E120 (타일 T = 0x40E120 + T*32), BG3 charbase 2
  타일맵  : LZ77, 포인터 테이블 0x7602FC 에 11항목(고유 8개). 그중 6개가 라벨을 갖는다.

판 디자인 (B안)
  원본은 타일마다 초록 테두리를 둘러 안쪽이 7x6px 뿐이고, 영문도 5px 로 그려져 있다.
  한글을 6px 로 넣으면 뭉개므로 **상하 테두리와 타일별 세로 구분선을 없애고**
  좌우 바깥 테두리만 남긴다. 안쪽이 8px 가 되어 8x8 시트(잉크 7x7)가 그대로 들어간다.

타일 배정
  한글이 원문보다 길거나 짧으므로 라벨마다 필요한 타일 수가 다르다.
  원본 블록(t325~350)을 다시 나누고 t351(미참조) 하나만 더 쓴다. t344(파란 막대)는 보존.

타일맵 수정
  라벨이 쓰던 칸을 새 타일로 채우고, **남는 칸은 배경 타일로 지운다**
  (안 지우면 원문 꼬리가 남는다 — 노페어 뒤에 R 이 남아 실제로 확인됐다).
  길어진 라벨은 옆 배경 칸을 하나 더 먹는다.
"""
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bitmap_font import SMALL  # noqa: E402
from lz77 import compress, decompress  # noqa: E402

TILESET = 0x40E120
PTR_TABLE = 0x7602FC
PTR_COUNT = 11
KANA_SHIFT = 32                 # 가나 모드는 타일셋을 32타일 밀어서 올린다 (아래 설명)

GREEN, INNER, INK = 4, 5, 1     # 테두리 / 안쪽 / 글자
BG_TILE = 320                   # 지도 배경 타일

# 라벨 정의: 원문이 쓰는 **정확한 타일 시퀀스**와 한국어, 새 시작 타일.
# 시퀀스로 찾는 이유: CHOZODIA 는 [348,349,350,328] 로 CRATERIA 의 'IA' 타일(328)을
# 재활용한다. "타일 번호가 범위 안" 식으로 찾으면 라벨 경계를 잘못 잡는다.
LABELS = [
    ("CRATERIA", [325, 326, 327, 328],      "크레테리아", 325),
    ("TOURIAN",  [329, 330, 331, 332],      "투리안",     330),
    ("NORFAIR",  [333, 334, 335, 336],      "노페어",     333),
    ("KRAID",    [337, 338, 339],           "크레이드",   336),
    ("BRINSTAR", [340, 341, 342, 343],      "브린스타",   340),
    ("RIDLEY",   [345, 346, 347],           "리들리",     345),
    ("CHOZODIA", [348, 349, 350, 328],      "초조디아",   348),
]


ARROW_DOWN, ARROW_UP = 322, 321   # 라벨 위에 오는 ↓화살표 / 라벨 아래에 오는 ↑화살표


def label_gaps(rom: bytes) -> dict:
    """라벨마다 글자를 타일 안에서 1px 내릴지(1) 그대로 둘지(0) 정한다.

    엘리베이터 화살표와 1px 띄우는 것이 목적이다.
      * 라벨 **위**에 ↓화살표(t322) -> 글자를 1px **아래로** (gap 1)
      * 라벨 **아래**에 ↑화살표(t321) -> 글자를 위에 둔다 (gap 0).
        시트의 빈 7행이 그대로 아래쪽 여백이 된다.

    타일은 **라벨 이름 단위로 공유**되므로(같은 이름이 여러 지도에 나온다) 이름마다 하나만
    고를 수 있다. 위/아래가 섞인 이름은 많은 쪽을 따른다 — 실측 분포는 apply() 로그에 찍힌다.
    """
    from collections import Counter
    votes = {ko: Counter() for _, _, ko, _ in LABELS}
    seen = set()
    for _, addr in map_pointers(rom):
        if addr in seen:
            continue
        seen.add(addr)
        tm, _ = decompress(rom, addr)

        def tile(cy, cx):
            return struct.unpack_from("<H", tm, (cy * 32 + cx) * 2)[0] & 0x3FF

        for en, cy, cx, have, ny, nx, need, ko, nt0 in placements(tm, addr):
            if nx is None:
                continue
            for k in range(-1, need + 1):
                x = nx + k
                if not 0 <= x < 32:
                    continue
                if ny > 0 and tile(ny - 1, x) == ARROW_DOWN:
                    votes[ko]["down"] += 1
                if ny < 31 and tile(ny + 1, x) == ARROW_UP:
                    votes[ko]["up"] += 1
    return {ko: (1 if v["down"] >= max(1, v["up"]) else 0) for ko, v in votes.items()}, votes


def label_tiles(ko: str, top_gap: int = 0) -> list[bytes]:
    """한글 라벨을 8px 타일 여러 개로 굽는다(B안 판).

    원본은 타일마다 초록 세로선을 두고 안쪽이 7x6px 뿐이라 한글이 뭉갠다.
    상하 테두리와 타일별 세로선을 없애고 좌우 바깥만 남겨 안쪽을 8px 로 넓힌다.

    `top_gap` 은 label_gaps() 가 화살표 방향을 보고 정한다.

    **글자는 테두리 위에 그린다.** 예전에는 테두리 칸(x0 / x끝)을 보호했는데, 이 시트는
    거의 모든 글자가 0열부터 잉크가 있어 첫 글자의 왼쪽 획이 잘렸다(리들리에서 발견).
    """
    w = len(ko) * 8
    g = [[0] * w for _ in range(8)]
    for y in range(top_gap, 8):
        for x in range(w):
            g[y][x] = INNER
        g[y][0] = GREEN
        g[y][w - 1] = GREEN
    dx = PIXEL_DX.get(ko, 0)
    for c, ch in enumerate(ko):
        if not SMALL.has(ch):
            raise ValueError(f"시트에 없는 글자: {ch!r}")
        for yy, row in enumerate(SMALL.cell(ch)):
            ty = yy + top_gap
            if ty >= 8:
                continue
            for xx, v in enumerate(row):
                x = c * 8 + xx + dx
                if not v:
                    continue
                if not (0 <= x < w):
                    raise ValueError(f"'{ko}' 를 {dx}px 밀면 글자가 판을 벗어난다")
                g[ty][x] = INK
    out = []
    for t in range(len(ko)):
        b = bytearray(32)
        for y in range(8):
            for xb in range(4):
                lo = g[y][t * 8 + xb * 2] & 0xF
                hi = g[y][t * 8 + xb * 2 + 1] & 0xF
                b[y * 4 + xb] = lo | (hi << 4)
        out.append(bytes(b))
    return out


def map_pointers(rom: bytes) -> list[tuple[int, int]]:
    out = []
    for k in range(PTR_COUNT):
        o = PTR_TABLE + k * 4
        out.append((o, struct.unpack_from("<I", rom, o)[0] & 0xFFFFFF))
    return out


def find_labels(tm) -> list[tuple[str, int, int, list[int], str, int]]:
    """원본 타일맵에서 라벨 출현을 정확한 시퀀스로 찾는다."""
    def tile(i):
        return struct.unpack_from("<H", tm, i * 2)[0] & 0x3FF

    hits = []
    for en, seq, ko, nt0 in LABELS:
        n = len(seq)
        for cy in range(32):
            for cx in range(32 - n + 1):
                if all(tile(cy * 32 + cx + k) == seq[k] for k in range(n)):
                    hits.append((en, cy, cx, seq, ko, nt0))
    return hits


# 라벨 옮기기 — (타일맵 주소, 원문, 원래 cy, 원래 cx) -> (dy, dx)
#
# 원본은 라벨 바로 위에 엘리베이터 화살표가 붙는 경우가 있는데, 한글은 가나보다 획이
# 위로 차서 화살표·지도 테두리와 붙어 읽기 어렵다(사용자 제보). 그런 라벨은 한 줄
# 내려 사이에 빈 줄을 만든다. 리들리는 지도 블록에 가려 있어 오른쪽으로도 한 칸 민다.
# 옮길 자리는 **원본 타일이 배경(320)인 칸만** 고른다.
MOVES: dict = {
    # 지금은 비어 있다. 칸째(8px) 옮기는 것은 "너무 멀다"는 사용자 판단이라
    # 화살표·지도와 붙는 문제는 판 위쪽 여백(TOP_GAP)과 픽셀 밀기(PIXEL_DX)로 푼다.
}

# 라벨별 픽셀 단위 가로 밀기. 타일 안에서 글자만 옮기므로 칸 수·가시성 비트가 안 바뀐다.
# 리들리는 왼쪽 옆 칸(cx15)이 지도 블록이라 1px 띄운다.
# **그 라벨 전용 타일에만 영향이 간다** — 같은 이름이 여러 지도에 나오면 전부 같이 밀린다.
PIXEL_DX = {
    "리들리": 1,
}


def placements(tm, addr: int):
    """라벨마다 (원문, 원래 cy·cx·칸수, 최종 cy·cx·칸수, 한국어)를 정한다.

    patch_tilemap 과 QA 치트가 같은 자리를 쓰도록 배치 계산을 한 곳에 모았다.
    """
    def tile(i):
        return struct.unpack_from("<H", tm, i * 2)[0] & 0x3FF

    out = []
    for en, cy, cx, seq, ko, nt0 in find_labels(tm):
        have, need = len(seq), len(ko)
        dy, dx = MOVES.get((addr, en, cy, cx), (0, 0))
        ny = cy + dy
        orig = {(cy, cx + k) for k in range(have)}

        def free(y, x):
            return (y, x) in orig or tile(y * 32 + x) == BG_TILE

        placed = None
        for cand in (cx + dx, cx + dx - max(0, need - have)):
            if cand < 0 or cand + need > 32:
                continue
            if all(free(ny, cand + k) for k in range(need)):
                placed = cand
                break
        out.append((en, cy, cx, have, ny, placed, need, ko, nt0))
    return out


def patch_tilemap(tm: bytearray, log: list[str], tag: str, addr: int = 0) -> bool:
    """라벨 칸을 새 타일 배치로 바꾼다. 원래 칸 중 남는 것은 배경으로 지운다."""
    def cell(i):
        return struct.unpack_from("<H", tm, i * 2)[0]

    ok = True
    for en, cy, cx, have, ny, nx, need, ko, nt0 in placements(tm, addr):
        if nx is None:
            log.append(f"  !! {tag} {en}: 자리 부족 (cy{cy} cx{cx}, {need}칸 필요)")
            ok = False
            continue
        attr = cell(cy * 32 + cx) & 0xF000          # 팔레트·반전 유지
        new_cells = {(ny, nx + k) for k in range(need)}
        for k in range(need):
            struct.pack_into("<H", tm, (ny * 32 + nx + k) * 2, attr | (nt0 + k))
        for k in range(have):                        # 원문 꼬리 제거
            if (cy, cx + k) not in new_cells:
                struct.pack_into("<H", tm, (cy * 32 + cx + k) * 2, BG_TILE)
        moved = "" if (ny, nx) == (cy, cx) else f" [옮김 cy{cy}cx{cx} ->]"
        log.append(f"  {tag} {en:9s} cy{ny:2d} cx{nx}..{nx+need-1} "
                   f"({have}->{need}칸){moved} -> {ko}")
    return ok


def apply(rom: bytes):
    """(타일셋 쓰기 목록, 타일맵 쓰기 목록, 로그)."""
    log = []
    tile_writes = []
    gaps, votes = label_gaps(rom)
    for en, seq, ko, nt0 in LABELS:
        v = votes[ko]
        log.append(f"  {ko} 화살표 위{v['down']}·아래{v['up']} -> 글자 {gaps[ko]}px 내림")
        for k, data in enumerate(label_tiles(ko, gaps[ko])):
            t = nt0 + k
            tile_writes.append((TILESET + t * 32, data, f"map_tile:{ko}:{k}"))
            # 가나(히라가나) 모드는 같은 타일 번호를 쓰되 타일 **그림**을 32타일 뒤에서
            # 가져다 올린다(VRAM t325..351 <- ROM t357..383). 한자 모드만 고치면
            # 히라가나 모드에서 가나가 그대로 나온다 — 두 블록 모두에 쓴다.
            tile_writes.append((TILESET + (t + KANA_SHIFT) * 32, data,
                                f"map_tile_kana:{ko}:{k}"))


    map_writes = []
    seen = {}
    for off, addr in map_pointers(rom):
        if addr in seen:
            continue
        raw, csize = decompress(rom, addr)
        tm = bytearray(raw)
        patch_tilemap(tm, log, f"0x{addr:06X}", addr)
        if bytes(tm) == raw:
            seen[addr] = None
            continue
        packed = compress(bytes(tm), optimal=True)
        seen[addr] = packed
        map_writes.append((addr, packed, csize, off))
    return tile_writes, map_writes, log
