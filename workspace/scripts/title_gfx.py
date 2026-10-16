"""타이틀 로고(LZ77 블롭 0x44713C)의 영문 로고를 한글로 교체한다.

구조 (workspace/analysis/title_graphics.md)
  블롭 0x44713C : 압축 4,377B -> 10,240B(320타일), VRAM 0x0C000 = BG1 charbase 3
  타일맵 0x44E2D8 : 압축 794B -> 2,048B, screenbase 2. 30x20 칸을 쓴다.

지켜야 하는 것
  - **타일맵은 고치지 않는다.** 재압축 여유가 2B 뿐이다.
    따라서 이미 내용이 있는 칸(고유 타일)만 다시 쓴다. 빈 칸은 여러 칸이
    공유하는 blank 타일을 가리키므로 건드리면 화면 전체가 오염된다.
  - 팔레트 뱅크 0 의 색인만 쓴다. 색인 0 은 투명.

로고 팔레트는 **애니메이션**이다(핑크 위상 <-> 파랑/노랑 위상).
자산은 핑크 위상 기준으로 감색했고, 색인이 밝기 램프를 따르므로 다른 위상에서도
원본과 같은 방식으로 색이 바뀐다(work/title/ko_B_t2600.png 로 확인).

자산: workspace/assets/title_ko.png (240x160 인덱스 PNG)
      원본 그림 workspace/assets/title_ko_source.png 에서 축소·감색해 만들었다
      (work/title_ko_build.py 배치안 B).
"""
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lz77 import compress, decompress  # noqa: E402
from rombuild import PROJECT  # noqa: E402

BLOB = 0x44713C
TILEMAP = 0x44E2D8
ASSET = PROJECT / "workspace" / "assets" / "title_ko.png"


def load_asset():
    from PIL import Image
    img = Image.open(ASSET)
    if img.mode != "P":
        raise ValueError(f"{ASSET.name} 은 인덱스 PNG 여야 한다 (현재 {img.mode})")
    if img.size != (240, 160):
        raise ValueError(f"{ASSET.name} 크기 {img.size} != (240, 160)")
    px = img.load()
    return [[px[x, y] for x in range(240)] for y in range(160)]


def cell_map(rom):
    """칸 -> 타일번호, 그리고 타일별 사용 칸 수."""
    tm, _ = decompress(rom, TILEMAP)
    cells, cnt = {}, {}
    for cy in range(20):
        for cx in range(30):
            t = struct.unpack_from("<H", tm, (cy * 32 + cx) * 2)[0] & 0x3FF
            cells[(cx, cy)] = t
            cnt[t] = cnt.get(t, 0) + 1
    return cells, cnt


def apply(rom: bytes):
    """(블롭주소, 새 압축, 원본 압축크기, 로그)."""
    raw, orig_size = decompress(rom, BLOB)
    cells, cnt = cell_map(rom)
    art = load_asset()
    out = bytearray(raw)

    # 로고가 있던 칸(cy5..11)만 다룬다. 그 밖은 손대지 않는다.
    written = cleared = 0
    for (cx, cy), t in cells.items():
        if not (5 <= cy <= 11):
            continue
        if cnt[t] > 1:                       # 공유 blank 타일 — 쓰기 금지
            if any(art[cy * 8 + y][cx * 8 + x] for y in range(8) for x in range(8)):
                raise ValueError(
                    f"칸 ({cx},{cy}) 은 공유 타일 {t} 인데 그림이 걸쳤다 — "
                    f"타일맵을 고치지 않고는 그릴 수 없다")
            continue
        blk = [[art[cy * 8 + y][cx * 8 + x] for x in range(8)] for y in range(8)]
        for y in range(8):
            for xb in range(4):
                out[t * 32 + y * 4 + xb] = (blk[y][xb * 2] & 0xF) | ((blk[y][xb * 2 + 1] & 0xF) << 4)
        if any(v for r in blk for v in r):
            written += 1
        else:
            cleared += 1

    packed = compress(bytes(out), optimal=True)
    log = [f"타일 {written}개 교체, {cleared}개 비움"]
    return BLOB, packed, orig_size, log
