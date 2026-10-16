"""번역문을 원장에 적용한다.

입력은 {id: ko_text} 매핑 파일(JSON)이다. 보호 필드는 건드리지 않고
ko/status/notes 만 갱신한다. 적용 시 토큰 파싱과 폭 예산을 즉시 검사해
경계 위반을 뒤로 미루지 않는다.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
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


def check_entry(ko: str, layout: list[dict], rom: bytes) -> list[str]:
    """번역문의 기계적 제약을 검사한다. 반환은 위반 목록."""
    problems = []
    try:
        codes = text_to_codes(ko)
    except ValueError as e:
        return [f"토큰/문자 오류: {e}"]

    if not codes or codes[-1] != 0xFF00:
        problems.append("{end} 로 끝나지 않음")

    lines = split_lines(codes)
    if len(lines) != len(layout):
        problems.append(f"줄 수 {len(lines)} != 원문 {len(layout)}")

    for i, line in enumerate(lines):
        w = line_width(line, rom)
        if w > SCREEN_WIDTH:
            problems.append(f"L{i} 폭 {w}px > 화면 {SCREEN_WIDTH}px")
            continue
        if i < len(layout) and layout[i]["center"] is not None:
            x = x_for_center(layout[i]["center"], w)
            if x < 0:
                problems.append(f"L{i} 폭 {w}px 로 X={x} (< 0, 중심 {layout[i]['center']})")
            elif x + w > SCREEN_WIDTH:
                problems.append(f"L{i} 우측 초과: X={x}+{w}={x + w} > {SCREEN_WIDTH}")
    return problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", help="{id: ko} JSON")
    ap.add_argument("--status", default="needs_review")
    ap.add_argument("--ledger", default=str(LEDGER))
    ap.add_argument("--advance", type=int, default=10,
                    help="한글 진행폭 (빌드와 같은 값이어야 폭 검사가 정확하다)")
    a = ap.parse_args()

    # 빌드와 같은 폭 조건으로 검사한다: 한글은 배정 위치와 무관하게 진행폭이 같다
    rom = patched_width_rom(load_source(), Allocation(ALLOC).char_to_code.values(), a.advance)
    import layout as _layout
    _layout.WIDTH_DEFAULT = a.advance
    led_path = Path(a.ledger)
    led = json.loads(led_path.read_text(encoding="utf-8"))
    incoming = json.loads(Path(a.input).read_text(encoding="utf-8"))

    by_id = {e["id"]: e for e in led["entries"]}
    applied, failed, unknown = 0, [], []

    for eid, ko in incoming.items():
        e = by_id.get(eid)
        if e is None:
            unknown.append(eid)
            continue
        problems = check_entry(ko, e["protected"]["layout"], rom)
        if problems:
            failed.append((eid, problems))
            continue
        e["ko"] = ko
        e["status"] = a.status
        applied += 1

    led_path.write_text(json.dumps(led, ensure_ascii=False, indent=1), encoding="utf-8")

    from collections import Counter
    st = Counter(e["status"] for e in led["entries"])
    print(f"적용 {applied}건 / 입력 {len(incoming)}건")
    print("원장 상태:", dict(st))
    if unknown:
        print(f"\n알 수 없는 ID {len(unknown)}건: {unknown[:5]}")
    if failed:
        print(f"\n검사 실패 {len(failed)}건 (적용 안 함)")
        for eid, ps in failed:
            print(f"  {eid}")
            for p in ps:
                print(f"    - {p}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
