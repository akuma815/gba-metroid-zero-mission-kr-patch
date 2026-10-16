"""용어집과 용어 사용 현황을 CSV 로 내보낸다.

일관성 점검용이다.
- glossary.csv: 승인 대상 용어 목록
- term_usage.csv: 각 용어가 실제로 어느 항목에 쓰였는지, 원문 대응이 맞는지
  (원문에 해당 단어가 있는데 번역에 용어가 없으면 '누락 의심'으로 표시)
"""
import csv
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rombuild import PROJECT  # noqa: E402

TR = PROJECT / "workspace" / "text" / "translation"
TOKEN_RE = re.compile(r"\{[^}]*\}")


def strip_tokens(s: str) -> str:
    return TOKEN_RE.sub("", s)


def main():
    gl = json.loads((TR / "glossary.json").read_text(encoding="utf-8"))
    led = json.loads((TR / "ko.json").read_text(encoding="utf-8"))
    entries = led["entries"]

    # 1) 용어집
    with (TR / "glossary.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["용어ID", "영어", "일본어", "한국어", "상태", "대안", "비고"])
        for t in gl["terms"]:
            w.writerow([t["id"], t.get("src_en", ""), t.get("src_ja", ""),
                        t["ko"], t.get("state", ""),
                        " / ".join(t.get("options", [])), t.get("note", "")])

    # 2) 용어 사용 현황
    rows = []
    for t in gl["terms"]:
        ko_term = t["ko"]
        ja_term = t.get("src_ja", "")
        en_term = t.get("src_en", "")

        used, missing = [], []
        for e in entries:
            ko = strip_tokens(e["ko"])
            ja = strip_tokens(e["protected"]["langs"]["kana"]["text"])
            en = strip_tokens(e["protected"]["langs"]["english"]["text"])
            has_ko = ko_term in ko
            # 원문 대응: 일본어나 영어 어느 쪽에든 원어가 있으면 대상으로 본다
            has_src = (ja_term and ja_term in ja) or (en_term and en_term.lower() in en.lower())
            if has_ko:
                used.append(e["id"])
            elif has_src:
                missing.append(e["id"])

        rows.append([
            t["id"], en_term, ja_term, ko_term, t.get("state", ""),
            len(used), " ".join(used[:12]) + (" …" if len(used) > 12 else ""),
            len(missing), " ".join(missing[:8]) + (" …" if len(missing) > 8 else ""),
        ])

    with (TR / "term_usage.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["용어ID", "영어", "일본어", "한국어", "상태",
                    "사용건수", "사용항목", "누락의심건수", "누락의심항목"])
        for r in sorted(rows, key=lambda r: (-r[7], -r[5])):
            w.writerow(r)

    unused = [r[0] for r in rows if r[5] == 0]
    suspect = [(r[0], r[7]) for r in rows if r[7] > 0]
    print(f"용어 {len(rows)}개 -> glossary.csv, term_usage.csv")
    print(f"  번역문에 한 번도 안 쓰인 용어: {len(unused)}개")
    if unused:
        print("   ", ", ".join(unused[:12]) + (" …" if len(unused) > 12 else ""))
    print(f"  원문엔 있는데 번역에 용어가 안 보이는 항목이 있는 용어: {len(suspect)}개")
    for tid, n in suspect[:10]:
        print(f"    {tid}: {n}건")


if __name__ == "__main__":
    main()
