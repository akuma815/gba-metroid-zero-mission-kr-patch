"""번역 원장을 검토용 CSV 로 내보낸다.

원문(일본어/영어)과 번역을 나란히 두고, 화면·맥락 분류와 화자를 붙여
용어·문체 일관성을 확인할 수 있게 한다.

- 읽기용 열은 제어 토큰을 걷어내 문장만 남긴다.
- 재삽입에 쓰이는 원본 문자열은 별도 열(`번역_원본`)에 보존한다.
- Excel 에서 바로 열리도록 UTF-8 BOM 으로 저장한다.
"""
import argparse
import csv
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import charmap  # noqa: E402
import layout as _layout  # noqa: E402
from hangul_alloc import Allocation  # noqa: E402
from layout import line_width, patched_width_rom, split_lines  # noqa: E402
from rombuild import PROJECT, load_source  # noqa: E402
from tokens import text_to_codes  # noqa: E402

LEDGER = PROJECT / "workspace" / "text" / "translation" / "ko.json"
ALLOC = PROJECT / "workspace" / "text" / "translation" / "hangul_codes.json"

TOKEN_RE = re.compile(r"\{(?:x|c|xm|u):[0-9A-Fa-f]+\}")
BR_RE = re.compile(r"\{br\}")
END_RE = re.compile(r"\{end\}")


def readable(s: str) -> str:
    """제어 토큰을 걷어내고 줄바꿈만 남긴다."""
    s = END_RE.sub("", s)
    s = BR_RE.sub("\n", s)
    s = TOKEN_RE.sub("", s)
    return s.strip()


# 화면·맥락 분류. (그룹, 시작, 끝) -> (분류, 화자/맥락)
# 이 게임은 대화가 거의 없어 대부분 시스템 표시이며, 1인칭 독백만 화자가 뚜렷하다.
BUCKETS = [
    ("msg_a", 0, 0, "미사용", "-"),
    ("msg_a", 1, 7, "아이템 획득", "시스템"),
    ("msg_a", 8, 21, "아이템 이름", "시스템"),
    ("msg_a", 22, 23, "세이브", "시스템"),
    ("msg_a", 24, 26, "보급·회복", "시스템"),
    ("msg_a", 27, 31, "맵 데이터 획득", "시스템"),
    ("msg_a", 32, 32, "아이템 획득", "시스템"),
    ("msg_a", 33, 34, "자폭 경고", "함내 방송"),
    ("msg_a", 35, 35, "디버그", "-"),
    ("msg_a", 36, 38, "슬립 모드", "시스템"),
    ("msg_a", 39, 52, "지역·시설 이름", "화면 표시"),
    ("msg_a", 53, 64, "미사용", "-"),
    ("msg_b", 0, 18, "아이템 설명(튜토리얼)", "시스템"),
    ("msg_b", 19, 21, "인트로 독백", "사무스"),
    ("msg_b", 22, 24, "긴급 지령", "은하연방 사령부"),
    ("msg_b", 25, 25, "시작 메뉴", "시스템"),
    ("msg_b", 26, 30, "파일 복사·삭제", "시스템"),
    ("msg_b", 31, 36, "데이터 손상 경고", "시스템"),
    ("msg_b", 37, 38, "전체 삭제 확인", "시스템"),
    ("msg_b", 39, 40, "시작 메뉴", "시스템"),
    ("msg_b", 41, 41, "메시지 옵션", "시스템"),
    ("msg_b", 42, 43, "난이도 선택", "시스템"),
    ("msg_b", 44, 44, "전체 삭제 확인", "시스템"),
    ("msg_b", 45, 51, "통신(퓨전 연동)", "시스템"),
    ("msg_b", 52, 53, "기록 표시", "화면 표시"),
    ("msg_b", 54, 54, "통신(퓨전 연동)", "시스템"),
    ("msg_b", 55, 57, "통신 오류", "시스템"),
    ("msg_b", 58, 61, "해금 알림", "시스템"),
]


def classify(group: str, index: int) -> tuple[str, str]:
    for g, lo, hi, cat, spk in BUCKETS:
        if g == group and lo <= index <= hi:
            return cat, spk
    return "미분류", "-"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(PROJECT / "workspace" / "text" / "translation" / "review.csv"))
    ap.add_argument("--advance", type=int, default=10)
    a = ap.parse_args()

    charmap.reload_hangul()
    _layout.WIDTH_DEFAULT = a.advance
    rom = patched_width_rom(load_source(), Allocation(ALLOC).char_to_code.values(), a.advance)
    led = json.loads(LEDGER.read_text(encoding="utf-8"))

    # 창별 폭 상한 (validate_translation.py 와 같은 표를 쓴다)
    sys.path.insert(0, str(PROJECT / "workspace" / "tests"))
    from validate_translation import window_limit  # noqa: E402

    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ID", "분류", "화자/맥락", "원문(일본어)", "원문(영어)",
                    "번역(한국어)", "상태", "줄수",
                    "창", "창폭px", "최대폭px", "여유px",
                    "번역_원본(토큰포함)", "비고"])
        for e in led["entries"]:
            cat, spk = classify(e["group"], e["index"])
            p = e["protected"]["langs"]
            ko = e["ko"]
            wname, wlimit = window_limit(e["group"], e["index"])

            lines = split_lines(text_to_codes(ko)) if ko else []
            widths = [line_width(ln, rom) for ln in lines]
            maxw = max(widths) if widths else 0
            slack = wlimit - maxw if lines else ""

            note = []
            if isinstance(slack, int) and slack <= 16:
                note.append(f"여유 적음({slack}px)")
            if e["status"] != "distribution_eligible":
                note.append("재승인 대기")
            if e["group"] == "msg_a" and (e["index"] == 0 or e["index"] in range(53, 65)):
                note.append("게임에 표시되지 않음")

            w.writerow([
                e["id"], cat, spk,
                readable(p["kana"]["text"]),
                readable(p["english"]["text"]),
                readable(ko),
                e["status"], len(lines),
                wname, wlimit, maxw, slack,
                ko, "; ".join(note),
            ])

    from collections import Counter
    st = Counter(e["status"] for e in led["entries"])
    print(f"{len(led['entries'])}건 -> {out}")
    print("열: ID / 분류 / 화자·맥락 / 원문(일본어) / 원문(영어) / 번역 / 상태 / 줄수 /"
          " 창 / 창폭 / 최대폭 / 여유 / 원본토큰 / 비고")
    print("상태:", dict(st))


if __name__ == "__main__":
    main()
