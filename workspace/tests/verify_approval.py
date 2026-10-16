"""승인 무결성 검사 — 승인 후 번역이 바뀐 항목을 찾는다.

승인은 그 시점의 문장에 대한 것이다. 이후 ko 가 바뀌면 그 항목의 승인은 무효이며
다시 검토를 받아야 한다. 배포 후보 빌드 전에 실행한다.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from rombuild import PROJECT  # noqa: E402

TR = PROJECT / "workspace" / "text" / "translation"


def main() -> int:
    led = json.loads((TR / "ko.json").read_text(encoding="utf-8"))
    gl = json.loads((TR / "glossary.json").read_text(encoding="utf-8"))

    stale, unapproved = [], []
    for e in led["entries"]:
        ap = e.get("approval")
        if e["status"] == "distribution_eligible":
            if not ap:
                unapproved.append((e["id"], "승인 기록 없음"))
            elif ap.get("approved_text") != e["ko"]:
                stale.append(e["id"])

    gl_stale = [t["id"] for t in gl["terms"]
                if t.get("state") == "approved" and t.get("approved_ko") != t["ko"]]

    print(f"번역 {len(led['entries'])}건, 용어 {len(gl['terms'])}개 검사")
    if not (stale or unapproved or gl_stale):
        note = led.get("approval_note", {})
        print(f"PASS — 승인 후 변경 없음 (승인: {note.get('by')} {note.get('date')})")
        return 0

    if stale:
        print(f"\nFAIL 승인 후 번역이 바뀐 항목 {len(stale)}건 — 재검토 필요")
        for i in stale[:15]:
            print("  -", i)
    if unapproved:
        print(f"\nFAIL 승인 기록 없이 배포 적격으로 표시된 항목 {len(unapproved)}건")
        for i, why in unapproved[:15]:
            print(f"  - {i}: {why}")
    if gl_stale:
        print(f"\nFAIL 승인 후 표기가 바뀐 용어 {len(gl_stale)}개 — 사용 항목 재검토 필요")
        for i in gl_stale:
            print("  -", i)
    return 1


if __name__ == "__main__":
    sys.exit(main())
