"""토큰 표현의 전단사 검증.

분모: 추출된 381 메시지 전부.
각 메시지에 대해 codes -> 토큰 문자열 -> codes 가 원본과 완전히 같아야 한다.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from rombuild import PROJECT  # noqa: E402
from tokens import codes_to_text, text_to_codes  # noqa: E402


def main() -> int:
    data = json.loads((PROJECT / "workspace" / "text" / "source" / "messages.json")
                      .read_text(encoding="utf-8"))
    msgs = data["messages"]
    fails = []
    for m in msgs:
        text = codes_to_text(m["codes"])
        try:
            back = text_to_codes(text)
        except ValueError as e:
            fails.append((m["id"], f"역변환 실패: {e}"))
            continue
        if back != m["codes"]:
            first = next((i for i, (a, b) in enumerate(zip(back, m["codes"])) if a != b), None)
            fails.append((m["id"], f"불일치 at {first}: {back[:8]} vs {m['codes'][:8]}"))

    print(f"메시지 {len(msgs)}건 토큰 왕복 검사")
    if fails:
        print(f"\nFAIL {len(fails)}건")
        for mid, why in fails[:10]:
            print(f"  {mid}: {why}")
        return 1
    print("PASS — 전 메시지에서 codes -> 토큰 -> codes 가 동일")
    return 0


if __name__ == "__main__":
    sys.exit(main())
