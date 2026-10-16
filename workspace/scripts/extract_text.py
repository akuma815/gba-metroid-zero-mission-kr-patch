"""메시지 텍스트 가역 추출.

모집단(정적 열거, exact):
  msg_a 메타 0x760890 -> 언어 3종 x 65 엔트리
  msg_b 메타 0x7603E4 -> 언어 3종 x 62 엔트리
  합계 381 메시지. 종료자는 전부 0xFF00 (work/probe_msg_structure.py 확인).

산출물 JSON은 원시 코드 배열을 보존하므로 바이트 동일 재조립이 가능하다.
사람이 읽는 `text`는 참고용이며, 미매핑 코드(한자 등)는 <XXXX> 원시 토큰으로 남는다.
"""
import argparse
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from charmap import TERMINATOR, decode_stream  # noqa: E402
from rombuild import PROJECT, load_source  # noqa: E402

GROUPS = {
    "msg_a": {"meta": 0x760890, "count": 65, "desc": "아이템 획득 등 단문"},
    "msg_b": {"meta": 0x7603E4, "count": 62, "desc": "튜토리얼/힌트 장문"},
}
LANG_NAMES = ["kanji", "kana", "english"]
MAX_CODES = 600


def u32(d, o):
    return struct.unpack_from("<I", d, o)[0]


def u16(d, o):
    return struct.unpack_from("<H", d, o)[0]


def read_message(d: bytes, ptr: int) -> list[int]:
    codes = []
    o = ptr
    while True:
        w = u16(d, o)
        codes.append(w)
        o += 2
        if w == TERMINATOR:
            return codes
        if len(codes) > MAX_CODES:
            raise ValueError(f"종료자 미발견 @0x{ptr:06X}")


def lang_tables(d: bytes, meta: int) -> list[int]:
    """메타 7슬롯에서 고유 하위 테이블 주소를 순서대로 뽑는다."""
    out = []
    for i in range(7):
        t = u32(d, meta + i * 4) & 0xFFFFFF
        if t not in out:
            out.append(t)
    return out


def extract(d: bytes) -> dict:
    messages = []
    for gid, g in GROUPS.items():
        tables = lang_tables(d, g["meta"])
        if len(tables) != 3:
            raise ValueError(f"{gid}: 언어 테이블 3개가 아님 {tables}")
        for li, tbl in enumerate(tables):
            for i in range(g["count"]):
                slot = tbl + i * 4
                ptr = u32(d, slot) & 0xFFFFFF
                codes = read_message(d, ptr)
                messages.append({
                    "id": f"{gid}:{LANG_NAMES[li]}:{i:03d}",
                    "group": gid,
                    "lang": LANG_NAMES[li],
                    "lang_index": li,
                    "index": i,
                    "pointer_slot": slot,
                    "pointer": ptr,
                    "codes": codes,
                    "text": decode_stream(codes),
                })
    # 본문 영역과 정렬 패딩 기록
    body = {}
    for m in messages:
        for k in range(m["pointer"], m["pointer"] + len(m["codes"]) * 2):
            body[k] = True
    lo, hi = min(body), max(body) + 1
    pads = []
    run = None
    for k in range(lo, hi):
        if k not in body:
            if run is None:
                run = k
        elif run is not None:
            pads.append({"offset": run, "bytes": d[run:k].hex()})
            run = None
    if run is not None:
        pads.append({"offset": run, "bytes": d[run:hi].hex()})

    return {
        "schema_version": 1,
        "source_sha256": "d087ca6e2d1808109a579c2283e944d81c8426d37de564f99ea9273087c2172a",
        "groups": {gid: {"meta": g["meta"], "count": g["count"], "desc": g["desc"],
                         "lang_tables": lang_tables(d, g["meta"])}
                   for gid, g in GROUPS.items()},
        "lang_names": LANG_NAMES,
        "body_extent": {"start": lo, "end": hi},
        "padding": pads,
        "message_count": len(messages),
        "messages": messages,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(PROJECT / "workspace" / "text" / "source" / "messages.json"))
    a = ap.parse_args()

    d = load_source()
    data = extract(d)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

    ext = data["body_extent"]
    print(f"메시지 {data['message_count']}건")
    print(f"본문 0x{ext['start']:06X}-0x{ext['end']:06X} ({ext['end'] - ext['start']} 바이트)")
    print(f"정렬 패딩 {len(data['padding'])}곳: "
          + ", ".join(f"0x{p['offset']:06X}({p['bytes']})" for p in data["padding"]))
    print(f"-> {out}")

    # 중복 포인터 통계
    seen = {}
    for m in data["messages"]:
        seen.setdefault(m["pointer"], []).append(m["id"])
    dup = {k: v for k, v in seen.items() if len(v) > 1}
    print(f"고유 포인터 {len(seen)}개, 공유 포인터 {len(dup)}개")


if __name__ == "__main__":
    main()
