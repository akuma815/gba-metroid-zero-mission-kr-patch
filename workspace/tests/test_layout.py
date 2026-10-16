"""레이아웃 규칙 회귀 검증.

원본 메시지의 각 줄에 대해, 기록된 X 좌표와 폭으로 되돌린 중심을 이용해
X 를 다시 계산하면 원본 값과 같아야 한다. 이는 번역 시 X 재계산 공식이
원본 조판 규칙과 동일함을 보장한다.
"""
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from layout import center_of, line_lead_x, line_width, split_lines, x_for_center  # noqa: E402
from rombuild import PROJECT, load_source  # noqa: E402


def main() -> int:
    rom = load_source()
    data = json.loads((PROJECT / "workspace" / "text" / "source" / "messages.json")
                      .read_text(encoding="utf-8"))

    total = 0
    ok = 0
    mismatch = []
    centers = Counter()

    for m in data["messages"]:
        for li, line in enumerate(split_lines(m["codes"])):
            x = line_lead_x(line)
            if x is None:
                continue
            w = line_width(line, rom)
            total += 1
            c = center_of(x, w)
            centers[c] += 1
            if x_for_center(c, w) == x:
                ok += 1
            else:
                mismatch.append((m["id"], li, x, w, c, x_for_center(c, w)))

    print(f"선두 X 를 가진 줄 {total}건 중 재계산 일치 {ok}건")
    print("중심 분포:", dict(sorted(centers.items(), key=lambda kv: -kv[1])[:6]))

    if mismatch:
        print(f"\nFAIL 불일치 {len(mismatch)}건")
        for mid, li, x, w, c, got in mismatch[:10]:
            print(f"  {mid} L{li}: x={x} 폭={w} 중심={c} 재계산={got}")
        return 1
    print("\nPASS — 모든 줄에서 X 재계산 공식이 원본과 일치")
    return 0


if __name__ == "__main__":
    sys.exit(main())
