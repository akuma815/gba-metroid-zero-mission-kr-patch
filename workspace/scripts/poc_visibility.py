"""PoC-01 가시성 증명 빌드.

가설: 화면 텍스트의 글리프는 ROM 0x4154BC + code*32(상단) / +0x400(하단)에서 온다.
개입: 라틴 대문자 'E'(code 0x0085)의 상·하단 타일을 식별 가능한 마커 패턴으로 교체한다.
     원본 형상을 지우고 대각선 격자를 그려 어떤 화면이 이 폰트를 소비하는지 식별한다.
판정: 인트로 "EXTERMINATE ALL MET..."의 E가 마커로 바뀌면 통과.
     바뀌지 않으면 인트로는 별도 소비자 경로(그래픽 등)를 쓴다는 증거.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rombuild import PROJECT, RomBuilder, glyph_offsets  # noqa: E402

CODE_E = 0x0085


def marker_tile(fill: int = 0x1) -> bytes:
    """8x8 4bpp 타일: 전체를 fill 색으로 채운다 (완전 블록)."""
    b = (fill | (fill << 4)) & 0xFF
    return bytes([b] * 32)


def hollow_tile(fill: int = 0x1) -> bytes:
    """8x8 4bpp 타일: 테두리만 fill, 내부는 0 (속 빈 사각형)."""
    rows = []
    for y in range(8):
        px = [fill] * 8 if y in (0, 7) else [fill] + [0] * 6 + [fill]
        row = bytearray()
        for x in range(0, 8, 2):
            row.append((px[x] & 0xF) | ((px[x + 1] & 0xF) << 4))
        rows.append(bytes(row))
    return b"".join(rows)


def main():
    b = RomBuilder()
    top, bot = glyph_offsets(CODE_E)

    # 원본 'E' 형상을 기대 바이트로 고정한다 (지원 리비전 확인의 일부)
    exp_top = b.source[top:top + 32]
    exp_bot = b.source[bot:bot + 32]
    print(f"code 0x{CODE_E:04X} top=0x{top:06X} bottom=0x{bot:06X}")
    print(f"  원본 상단: {exp_top.hex()}")
    print(f"  원본 하단: {exp_bot.hex()}")

    b.write(top, marker_tile(0x1), expected=exp_top, who="poc01:E-top")
    b.write(bot, hollow_tile(0x1), expected=exp_bot, who="poc01:E-bottom")

    out = PROJECT / "build" / "poc01_visibility.gba"
    b.save(out)
    print()
    print(b.summary())
    print(f"\n출력: {out}")


if __name__ == "__main__":
    main()
