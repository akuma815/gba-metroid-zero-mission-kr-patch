"""번역 원장 전체를 빌드와 동일한 조건으로 검사한다.

빌드는 첫 위반에서 멈추므로, 배치 작업 전에 모든 위반을 한 번에 보기 위한 검사다.
검사 항목: 토큰 파싱, 종료자, 줄 수, 줄 폭, X 재계산, **창 폭**.

창 폭 검사가 필요한 이유: 화면 폭(240px)만 보면 부족하다. 실제 대화창은 훨씬 좁고
창마다 다르다. 파일 선택 화면의 삭제 확인 창은 약 128px 뿐이라, 240px 기준을 통과한
번역이 실제로는 두 줄로 넘쳐 글자가 쪼개졌다(사용자 제보로 발견).

원문은 각 창에 맞게 짜여 있으므로 **같은 창을 쓰는 메시지들의 원문 최대 폭**을
그 창의 허용치로 삼는다. 단, 실화면에서 원문보다 넓어도 정상임이 확인된 그룹은
확인된 값으로 완화한다.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import charmap  # noqa: E402
import layout as _layout  # noqa: E402
from hangul_alloc import Allocation  # noqa: E402
from layout import (  # noqa: E402
    SCREEN_WIDTH,
    line_width,
    patched_width_rom,
    split_lines,
    x_for_center,
)
from rombuild import PROJECT, load_source  # noqa: E402
from tokens import text_to_codes  # noqa: E402

LEDGER = PROJECT / "workspace" / "text" / "translation" / "ko.json"
ALLOC = PROJECT / "workspace" / "text" / "translation" / "hangul_codes.json"
SOURCE = PROJECT / "workspace" / "text" / "source" / "messages.json"

# 창(화면) 그룹 -> (msg 그룹, 인덱스 범위, 허용 폭 상한)
# 상한은 그 창을 쓰는 원문의 최대 폭이다. 실화면에서 원문보다 넓어도 정상임이
# 확인된 그룹만 확인된 값으로 완화한다.
WINDOWS = [
    ("아이템·시스템 메시지", "msg_a", range(0, 39), 216),   # 원문 최대 216(msg_a:004)
    ("지역 이름", "msg_a", range(39, 65), 216),
    ("튜토리얼", "msg_b", range(0, 19), 224),               # 원문 최대 224
    ("인트로 독백", "msg_b", range(19, 22), 240),           # 실화면 확인: 화면 전체
    ("긴급 지령", "msg_b", range(22, 25), 240),             # 실화면 확인: 화면 전체
    ("파일 선택·삭제", "msg_b", range(25, 39), 128),        # 실측 약 128 (좁은 창)
    ("시작·옵션", "msg_b", range(39, 45), 128),
    ("통신", "msg_b", range(45, 58), 200),
    ("해금 알림", "msg_b", range(58, 62), 117),
]


def window_limit(group: str, index: int) -> tuple[str, int]:
    for name, g, rng, lim in WINDOWS:
        if g == group and index in rng:
            return name, lim
    return "미분류", SCREEN_WIDTH


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--advance", type=int, default=10)
    a = ap.parse_args()

    charmap.reload_hangul()
    _layout.WIDTH_DEFAULT = a.advance
    rom = patched_width_rom(load_source(), Allocation(ALLOC).char_to_code.values(), a.advance)
    led = json.loads(LEDGER.read_text(encoding="utf-8"))

    problems = []
    checked = 0
    for e in led["entries"]:
        if not e["ko"]:
            problems.append((e["id"], "미번역"))
            continue
        checked += 1
        try:
            codes = text_to_codes(e["ko"])
        except ValueError as ex:
            problems.append((e["id"], f"토큰/문자: {ex}"))
            continue
        if not codes or codes[-1] != 0xFF00:
            problems.append((e["id"], "{end} 누락"))
        lay = e["protected"]["layout"]
        lines = split_lines(codes)
        if len(lines) != len(lay):
            problems.append((e["id"], f"줄 수 {len(lines)} != 원문 {len(lay)}"))
            continue
        wname, wlimit = window_limit(e["group"], e["index"])
        for i, line in enumerate(lines):
            w = line_width(line, rom)
            if w > SCREEN_WIDTH:
                problems.append((e["id"], f"L{i} 폭 {w}px > 화면 {SCREEN_WIDTH}px"))
                continue
            if w > wlimit:
                problems.append((e["id"],
                                 f"L{i} 폭 {w}px > {wname} 창 {wlimit}px "
                                 f"({w - wlimit}px 축약 필요)"))
                continue
            c = lay[i]["center"]
            if c is None:
                continue
            x = x_for_center(c, w)
            if x < 0:
                need = w - int(c) * 2
                problems.append((e["id"], f"L{i} 폭 {w}px, 중심 {c} -> X={x} "
                                          f"({need}px 축약 필요, 최대 {int(c) * 2}px)"))
            elif x + w > SCREEN_WIDTH:
                problems.append((e["id"], f"L{i} 우측 초과 X={x}+{w}={x + w}"))

    print(f"진행폭 {a.advance}px 기준, 번역 {checked}건 검사")
    if problems:
        print(f"\nFAIL {len(problems)}건")
        for eid, why in problems:
            print(f"  {eid}: {why}")
        return 1
    print("PASS — 전 항목이 폭·조판 제약을 만족")
    return 0


if __name__ == "__main__":
    sys.exit(main())
