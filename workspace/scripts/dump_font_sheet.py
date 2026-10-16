"""폰트 시트를 PNG로 덤프한다.

글리프: 상단 = 0x4154BC + code*32, 하단 = +0x400. 8x16, 4bpp.
인쇄 코드는 (code & 0x20) == 0 이므로, 0x40 블록마다 앞 32코드만 유효하다.
시트는 16열 x N행으로 배치하고 좌상단에 코드값을 별도 인덱스 파일로 남긴다.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rombuild import PROJECT, load_source, FONT_BASE, FONT_BOTTOM_DELTA  # noqa: E402

try:
    from PIL import Image
except ImportError:
    print("Pillow 필요: python -m pip install pillow")
    raise

PAL = [(0, 0, 0), (255, 255, 255), (255, 96, 96), (96, 160, 255),
       (255, 255, 96), (160, 255, 160), (255, 160, 255), (160, 160, 160),
       (64, 64, 64), (200, 200, 200), (255, 0, 0), (0, 0, 255),
       (255, 255, 0), (0, 255, 0), (255, 0, 255), (128, 128, 128)]


def glyph_pixels(rom: bytes, code: int):
    """8x16 픽셀 값(0-15) 2차원 리스트."""
    top = FONT_BASE + code * 32
    bot = top + FONT_BOTTOM_DELTA
    rows = []
    for off in (top, bot):
        for y in range(8):
            row = []
            for xb in range(4):
                b = rom[off + y * 4 + xb]
                row.append(b & 0xF)
                row.append(b >> 4)
            rows.append(row)
    return rows


def printable_codes(start: int, end: int):
    return [c for c in range(start, end) if (c & 0x20) == 0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=lambda x: int(x, 0), default=0x0040)
    ap.add_argument("--end", type=lambda x: int(x, 0), default=0x0300)
    ap.add_argument("--cols", type=int, default=32)
    ap.add_argument("--scale", type=int, default=2)
    ap.add_argument("--out", default=str(PROJECT / "workspace" / "font" / "sheet.png"))
    a = ap.parse_args()

    rom = load_source()
    codes = printable_codes(a.start, a.end)
    cols = a.cols
    rows_n = (len(codes) + cols - 1) // cols
    GW, GH, PAD = 8, 16, 1
    W = cols * (GW + PAD) + PAD
    H = rows_n * (GH + PAD) + PAD

    img = Image.new("RGB", (W, H), (24, 24, 32))
    px = img.load()
    for i, code in enumerate(codes):
        cx = (i % cols) * (GW + PAD) + PAD
        cy = (i // cols) * (GH + PAD) + PAD
        for y, row in enumerate(glyph_pixels(rom, code)):
            for x, v in enumerate(row):
                if v:
                    px[cx + x, cy + y] = PAL[v]
    if a.scale > 1:
        img = img.resize((W * a.scale, H * a.scale), Image.NEAREST)

    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)

    idx = out.with_suffix(".index.txt")
    lines = [f"codes 0x{a.start:04X}-0x{a.end:04X}, printable {len(codes)}, {cols} cols"]
    for r in range(rows_n):
        chunk = codes[r * cols:(r + 1) * cols]
        lines.append(f"row {r:3d}: 0x{chunk[0]:04X} .. 0x{chunk[-1]:04X}")
    idx.write_text("\n".join(lines), encoding="utf-8")
    print(f"{out}  ({len(codes)} glyphs, {cols}x{rows_n})")
    print(f"{idx}")


if __name__ == "__main__":
    main()
