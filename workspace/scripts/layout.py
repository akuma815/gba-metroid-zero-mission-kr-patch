"""텍스트 레이아웃 계산 — 제어코드 의미가 실증으로 확정된 규칙을 구현한다.

확정 사실 (workspace/analysis/POC.md 의 CTRL 실증 참조):
  0x80xx = 줄 시작 X 좌표 (하위 바이트가 픽셀 좌표)
  0x81xx = 색상 팔레트 인덱스. 0x8100 은 기본색(4)으로 복귀
  0x83xx = 줄 중간 X 좌표 재설정 (선택지 배치에 사용)

정렬 규칙: 원본 325줄 중 244줄이 `x + 폭/2 = 110.0` 에 수렴하며 상관계수 -0.926.
  x = 110 - ceil(width / 2)
검증: 폭 143 -> 38, 폭 144 -> 38, 폭 24 -> 98, 폭 96 -> 62 (모두 원본과 일치)

창 중심은 화면마다 다르다(대부분 110, 인트로 자막 112, Best Time 47.5/48).
번역 시에는 각 줄의 **원래 중심을 보존**하고 새 폭으로 x 를 다시 구한다.

화면 폭을 넘기면 렌더 버퍼가 왼쪽으로 랩어라운드되어 글자가 깨진다
(work/diag_ctrl80.py 실증). 따라서 폭 상한을 넘지 않아야 한다.
"""
import math

WIDTH_TABLE = 0x40D80C
WIDTH_MAX_CODE = 0x49F
WIDTH_DEFAULT = 10
SCREEN_WIDTH = 240

CTRL_X_LINE = 0x80    # 줄 시작 X
CTRL_COLOR = 0x81     # 색상
CTRL_X_MID = 0x83     # 줄 중간 X
NEWLINE = 0xFE00
TERMINATOR = 0xFF00


def is_control(code: int) -> bool:
    return (code >> 8) in (CTRL_X_LINE, CTRL_COLOR, CTRL_X_MID) or code in (NEWLINE, TERMINATOR)


def code_width(code: int, rom: bytes) -> int:
    """한 코드의 진행폭. 제어코드는 0.

    rom 은 폭 테이블이 최종 상태인 이미지여야 한다. 한글 배정이 폭 테이블 범위
    (<= 0x49F)에 걸치면 원본 한자 폭을 물려받으므로, 빌드와 검사 모두
    patched_width_rom() 으로 보정한 이미지를 넘긴다.
    """
    if is_control(code):
        return 0
    if code <= WIDTH_MAX_CODE:
        return rom[WIDTH_TABLE + code]
    return WIDTH_DEFAULT


def patched_width_rom(rom: bytes, hangul_codes, advance: int) -> bytes:
    """한글 코드의 폭 테이블 항목을 진행폭으로 보정한 이미지를 만든다.

    폭 테이블 범위 밖(> 0x49F)의 한글은 기본 상수를 쓰므로 손대지 않는다.
    기본 상수 자체를 바꾸는 것은 빌드가 담당한다.
    """
    buf = bytearray(rom)
    for lo in hangul_codes:
        if lo <= WIDTH_MAX_CODE:
            buf[WIDTH_TABLE + lo] = advance
    return bytes(buf)


def line_width(codes: list[int], rom: bytes) -> int:
    """줄이 차지하는 폭.

    0x80xx 는 커서를 xx 픽셀 전진시킨다(work/diag_midx.py 실증).
    줄 맨 앞의 것은 시작 위치를 정하는 용도라 폭에서 제외하고,
    줄 중간의 것은 글자 사이 간격이므로 폭에 더한다.
    (난이도 화면이 이 방식으로 대괄호 위치를 맞춘다.)
    """
    w = 0
    seen_ink = False
    for c in codes:
        if (c >> 8) == CTRL_X_LINE:
            if seen_ink:
                w += c & 0xFF
            continue
        if not is_control(c):
            seen_ink = True
        w += code_width(c, rom)
    return w


def x_for_center(center: float, width: int) -> int:
    """주어진 중심에 폭 width 를 중앙 정렬할 때의 시작 X."""
    return int(center) - math.ceil(width / 2) if float(center).is_integer() \
        else math.floor(center - width / 2)


def center_of(x: int, width: int) -> float:
    """원본 줄의 중심을 되돌린다(번역 시 보존 대상)."""
    return x + width / 2


def split_lines(codes: list[int]) -> list[list[int]]:
    """메시지를 줄 단위로 나눈다(종료자·줄바꿈 제외)."""
    lines, cur = [], []
    for w in codes:
        if w == TERMINATOR:
            break
        if w == NEWLINE:
            lines.append(cur)
            cur = []
            continue
        cur.append(w)
    lines.append(cur)
    return lines


def line_lead_x(line: list[int]) -> int | None:
    """줄 선두의 0x80xx 값(X 좌표). 없으면 None."""
    for w in line:
        if (w >> 8) == CTRL_X_LINE:
            return w & 0xFF
        if not is_control(w):
            return None
    return None


def relayout_line(line: list[int], center: float, rom: bytes) -> list[int]:
    """줄의 선두 0x80xx 를 새 폭 기준으로 재계산한다. 나머지 코드는 보존한다."""
    w = line_width(line, rom)
    new_x = x_for_center(center, w)
    if not 0 <= new_x <= 0xFF:
        raise ValueError(f"X 좌표 범위 밖: {new_x} (폭 {w}, 중심 {center})")
    if w > SCREEN_WIDTH:
        raise ValueError(f"줄 폭 {w}px 가 화면 {SCREEN_WIDTH}px 초과 — 랩어라운드로 깨진다")
    out = []
    replaced = False
    for c in line:
        if not replaced and (c >> 8) == CTRL_X_LINE:
            out.append((CTRL_X_LINE << 8) | new_x)
            replaced = True
            continue
        out.append(c)
    if not replaced:
        out.insert(0, (CTRL_X_LINE << 8) | new_x)
    return out
