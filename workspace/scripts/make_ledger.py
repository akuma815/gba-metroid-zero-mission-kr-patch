"""번역 원장(SSOT) 생성 — 추출 기준선에서 파생하되 번역 필드는 보존한다.

단위: 언어 축을 뺀 메시지 하나(msg_a:000 … msg_b:061). 127건.
  일본판 언어 옵션은 한자/히라가나 2종이므로 한국어 1개를 두 슬롯에 넣는다.

보호 필드(protected)는 추출기가 쓴다. 번역 단계는 ko/status/notes/decisions 만 바꾼다.
재생성 시 기존 번역 필드는 안정 ID로 이어붙이고, 보호 필드가 달라지면 경고한다.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from layout import center_of, line_lead_x, line_width, split_lines  # noqa: E402
from rombuild import PROJECT, load_source  # noqa: E402
from tokens import codes_to_text  # noqa: E402

SRC = PROJECT / "workspace" / "text" / "source" / "messages.json"
LEDGER = PROJECT / "workspace" / "text" / "translation" / "ko.json"

STATUS_UNTRANSLATED = "untranslated"


def build(rom: bytes, data: dict, prev: dict | None) -> dict:
    prev_entries = {e["id"]: e for e in prev["entries"]} if prev else {}
    by_id = {m["id"]: m for m in data["messages"]}

    entries = []
    warnings = []
    for gid, g in data["groups"].items():
        for i in range(g["count"]):
            eid = f"{gid}:{i:03d}"
            langs = {}
            for ln in data["lang_names"]:
                m = by_id[f"{gid}:{ln}:{i:03d}"]
                langs[ln] = {
                    "pointer": m["pointer"],
                    "pointer_slot": m["pointer_slot"],
                    "codes": m["codes"],
                    "text": codes_to_text(m["codes"]),
                }

            # 조판 기준: 번역 대상인 kanji 슬롯의 줄별 중심과 원본 폭
            lines = []
            for line in split_lines(by_id[f"{gid}:kanji:{i:03d}"]["codes"]):
                x = line_lead_x(line)
                w = line_width(line, rom)
                lines.append({
                    "src_x": x,
                    "src_width": w,
                    "center": center_of(x, w) if x is not None else None,
                })

            e = {
                "id": eid,
                "group": gid,
                "index": i,
                "protected": {"langs": langs, "layout": lines},
                "ko": "",
                "status": STATUS_UNTRANSLATED,
                "notes": None,
                "decisions": [],
            }
            p = prev_entries.get(eid)
            if p:
                if p["protected"] != e["protected"]:
                    warnings.append(eid)
                e["ko"] = p.get("ko", "")
                e["status"] = p.get("status", STATUS_UNTRANSLATED)
                e["notes"] = p.get("notes")
                e["decisions"] = p.get("decisions", [])
            entries.append(e)

    return {
        "schema_version": 1,
        "source_baseline": {
            "sha256": data["source_sha256"],
            "extract": "workspace/text/source/messages.json",
            "message_count": data["message_count"],
        },
        "target_slots": ["kanji", "hiragana"],
        "target_note": "한국어 1건을 lang0(kanji)·lang1(kana) 두 슬롯에 삽입한다. "
                       "일본판 옵션이 한자/히라가나 2종이라 어느 쪽을 골라도 한글이 나오게 한다.",
        "entry_count": len(entries),
        "entries": entries,
    }, warnings


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(LEDGER))
    a = ap.parse_args()

    rom = load_source()
    data = json.loads(SRC.read_text(encoding="utf-8"))
    out = Path(a.out)
    prev = json.loads(out.read_text(encoding="utf-8")) if out.is_file() else None

    ledger, warnings = build(rom, data, prev)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(ledger, ensure_ascii=False, indent=1), encoding="utf-8")

    from collections import Counter
    st = Counter(e["status"] for e in ledger["entries"])
    print(f"원장 {ledger['entry_count']}건 -> {out}")
    print("상태:", dict(st))
    if warnings:
        print(f"\n경고: 보호 필드가 바뀐 항목 {len(warnings)}건 — 번역 재검증 필요")
        for w in warnings[:10]:
            print("  -", w)


if __name__ == "__main__":
    main()
