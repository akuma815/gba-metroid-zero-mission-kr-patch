"""사용자 승인을 원장과 용어집에 반영한다.

승인은 '무엇을, 어느 버전에서, 누가' 승인했는지와 무효화 조건을 함께 남긴다.
번역문이나 용어가 이후에 바뀌면 그 항목의 승인은 자동으로 풀린다
(approved_text 와 현재 ko 가 다르면 승인 무효로 본다 — verify_approval.py).
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rombuild import PROJECT  # noqa: E402

TR = PROJECT / "workspace" / "text" / "translation"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--by", default="user", help="승인자")
    ap.add_argument("--date", required=True, help="승인 일자 YYYY-MM-DD")
    ap.add_argument("--note", default="")
    ap.add_argument("--state", default="distribution_eligible")
    a = ap.parse_args()

    led = json.loads((TR / "ko.json").read_text(encoding="utf-8"))
    n = 0
    for e in led["entries"]:
        if not e["ko"]:
            continue
        e["status"] = a.state
        e["approval"] = {
            "by": a.by,
            "date": a.date,
            "approved_text": e["ko"],   # 이후 수정되면 승인 무효 판정에 쓴다
        }
        n += 1
    led["approval_note"] = {
        "by": a.by, "date": a.date, "scope": f"번역 {n}건", "note": a.note,
        "invalidates_on": "해당 항목의 ko 가 approved_text 와 달라지면 그 항목의 승인은 무효",
    }
    (TR / "ko.json").write_text(json.dumps(led, ensure_ascii=False, indent=1), encoding="utf-8")

    gl = json.loads((TR / "glossary.json").read_text(encoding="utf-8"))
    gl["status"] = "approved"
    gl["approval"] = {"by": a.by, "date": a.date,
                      "scope": f"용어 {len(gl['terms'])}개",
                      "invalidates_on": "용어의 ko 표기가 바뀌면 그 용어를 쓰는 항목을 재검토"}
    for t in gl["terms"]:
        t["state"] = "approved"
        t["approved_ko"] = t["ko"]
    (TR / "glossary.json").write_text(json.dumps(gl, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"번역 {n}건 -> {a.state}")
    print(f"용어 {len(gl['terms'])}개 -> approved")
    print("상태:", dict(Counter(e["status"] for e in led["entries"])))


if __name__ == "__main__":
    main()
