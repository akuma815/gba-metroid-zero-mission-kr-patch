"""한글 가시성 PoC 빌드.

대상: 인트로 두 번째 자막 「機械生命体「マザーブレイン」を破壊せよ。」
근거: qa/logs/probe/probe_font_addr.txt 의 frame 687-690 폰트 읽기 추적으로
     이 자막이 소비하는 한자 코드 7쌍을 확정하고, work/show_codes.py 로 자형을 육안 확인했다.

개입
  A. 각 한자 코드 쌍(짝수=좌반부, 홀수=우반부)의 4개 타일을 한글 글리프로 교체한다.
  B. (--width 지정 시) 폭 함수 0x06E498 의 기본 진행폭 `movs r0,#10` 을 지정값으로 바꾼다.
     폭 테이블 0x40D80C 는 코드 0x49F 까지만 담당하고 한자/한글 영역은 이 기본값을 쓴다.

판정 기준
  통과: 의도한 한글이 겹침 없이 원래 한자와 같은 위치·크기로 표시되고 주변 가나·구두점이 유지된다.
  실패: 미표시 또는 판독 불가로 겹친다 -> 폰트 소비 경로 또는 폭 설계를 재검토한다.
  미해결: 일부만 바뀐다 -> 코드 쌍 매핑을 먼저 분리 진단한다.

증명 범위 밖: 텍스트 재인코딩·재배치, 길이 변경, 줄바꿈 정책, 다른 화면의 소비자 경로.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hangul_glyph import (  # noqa: E402
    fullwidth_tiles,
    glyph_extent,
    outline,
    render_bitmap,
)
from rombuild import PROJECT, RomBuilder, glyph_offsets  # noqa: E402

# 기본 폰트 사양.
# Galmuri11-Condensed 11px 는 외곽선 포함 폭이 9px 로 균일해 원본 진행폭 10px 에 그대로 들어간다
# (원본 한자는 11px 글리프에 10px 진행이라 1px 겹쳐 있었다).
DEFAULT_TTF = "Galmuri11-Condensed.ttf"
DEFAULT_SIZE = 11
DEFAULT_AT = (1, 3)

# 폭 함수 기본 진행폭 상수 (Thumb `movs r0, #imm8`)
WIDTH_CONST_OFF = 0x06E498
WIDTH_CONST_ORIG = bytes([0x0A, 0x20])  # movs r0, #10

# 코드 쌍(좌반부 코드) -> (원본 한자, 대체 한글)
# 機/械 는 첫 실행에서 "계기"로 표시돼 뒤바뀐 것이 확인되어 교정했다
# (프레임 읽기 순서는 화면 표시 순서가 아니다).
MAPPING = [
    (0x1182, "機", "기"),
    (0x1598, "械", "계"),
    (0x0F18, "生", "생"),
    (0x0B58, "命", "명"),
    (0x0946, "体", "체"),
    (0x1102, "破", "파"),
    (0x0DCA, "壊", "괴"),
]


def install_fullwidth(b: RomBuilder, lo_code: int, ch: str, who: str,
                      ttf: str, size: int, at: tuple[int, int]) -> int:
    """코드 쌍 (lo_code, lo_code+1) 에 16x16 한글 글리프를 설치하고 글리프 폭을 돌려준다."""
    if lo_code & 1:
        raise ValueError(f"좌반부 코드는 짝수여야 한다: 0x{lo_code:04X}")
    rows = outline(render_bitmap(ch, ttf, size, at=at))
    x0, x1, _, _ = glyph_extent(rows)
    t = fullwidth_tiles(rows)

    l_top, l_bot = glyph_offsets(lo_code)
    r_top, r_bot = glyph_offsets(lo_code + 1)
    for off, data, tag in (
        (l_top, t["left_top"], "LT"),
        (l_bot, t["left_bottom"], "LB"),
        (r_top, t["right_top"], "RT"),
        (r_bot, t["right_bottom"], "RB"),
    ):
        b.write(off, data, expected=b.source[off:off + 32], who=f"{who}:{tag}")
    return x1 + 1  # 왼쪽 여백 포함한 실제 점유 폭


def patch_default_width(b: RomBuilder, px: int):
    """폭 함수의 기본 진행폭 상수를 바꾼다."""
    if not 0 <= px <= 0xFF:
        raise ValueError(f"imm8 범위 밖: {px}")
    b.write(WIDTH_CONST_OFF, bytes([px, 0x20]),
            expected=WIDTH_CONST_ORIG, who=f"width:default={px}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--font", default=DEFAULT_TTF)
    ap.add_argument("--size", type=int, default=DEFAULT_SIZE)
    ap.add_argument("--at", default=",".join(map(str, DEFAULT_AT)),
                    help="셀 안 배치 좌표 x,y")
    ap.add_argument("--width", type=int, default=None,
                    help="기본 진행폭 픽셀 (미지정 시 원본 10 유지)")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    at = tuple(int(v) for v in a.at.split(","))

    b = RomBuilder()
    print(f"폰트: {a.font} {a.size}px at={at}")
    occupied = 0
    for lo, src_ch, ko_ch in MAPPING:
        w = install_fullwidth(b, lo, ko_ch, f"poc:{ko_ch}", a.font, a.size, at)
        occupied = max(occupied, w)
        lt, _ = glyph_offsets(lo)
        print(f"  0x{lo:04X}/0x{lo + 1:04X} @0x{lt:06X}  {src_ch} -> {ko_ch}  점유 {w}px")

    advance = a.width if a.width is not None else 10
    if a.width is not None:
        patch_default_width(b, a.width)
        print(f"기본 진행폭 10 -> {a.width}px @0x{WIDTH_CONST_OFF:06X}")
    else:
        print("기본 진행폭 10px 유지 (패치 없음)")

    gap = advance - occupied
    print(f"진행폭 {advance}px - 점유 {occupied}px = 자간 {gap}px"
          + ("  ** 겹침 위험 **" if gap < 1 else ""))

    name = a.out or f"poc_{Path(a.font).stem}_{a.size}_w{advance}.gba"
    out = PROJECT / "build" / name
    b.save(out)
    print()
    print(b.summary())
    print(f"\n출력: {out}")
    print("기대 화면: 「기계생명체「マザーブレイン」を파괴せよ。」")


if __name__ == "__main__":
    main()
