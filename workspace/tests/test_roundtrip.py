"""추출 데이터의 바이트 동일 왕복 검증.

분모: 메시지 본문 영역 0x4414BC-0x446DC4 전체 (22,792 바이트).
이 영역의 모든 바이트가 [추출된 메시지 + 기록된 정렬 패딩]으로 재구성되어
원본과 바이트 단위로 같아야 통과한다. 한 바이트라도 설명되지 않으면 실패다.

추가로 포인터 슬롯이 실제 메시지 시작을 가리키는지, 모집단 수가 선언과 맞는지 확인한다.
"""
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from charmap import TERMINATOR  # noqa: E402
from rombuild import PROJECT, load_source  # noqa: E402

DATA = PROJECT / "workspace" / "text" / "source" / "messages.json"

failures: list[str] = []


def check(cond: bool, msg: str):
    if not cond:
        failures.append(msg)


def main() -> int:
    rom = load_source()
    data = json.loads(DATA.read_text(encoding="utf-8"))
    msgs = data["messages"]

    # 1. 모집단
    expected = sum(g["count"] * len(data["lang_names"]) for g in data["groups"].values())
    check(len(msgs) == expected, f"메시지 수 {len(msgs)} != 선언 {expected}")
    check(len(msgs) == data["message_count"], "message_count 불일치")

    ids = [m["id"] for m in msgs]
    check(len(set(ids)) == len(ids), "중복 ID 존재")

    # 2. 각 메시지: 포인터 슬롯 일치, 종료자, 원본 바이트 일치
    for m in msgs:
        slot_val = struct.unpack_from("<I", rom, m["pointer_slot"])[0] & 0xFFFFFF
        check(slot_val == m["pointer"],
              f"{m['id']}: 포인터 슬롯 0x{slot_val:06X} != 0x{m['pointer']:06X}")
        check(m["codes"][-1] == TERMINATOR, f"{m['id']}: 종료자 없음")
        check(TERMINATOR not in m["codes"][:-1], f"{m['id']}: 중간에 종료자")
        raw = b"".join(struct.pack("<H", w) for w in m["codes"])
        orig = rom[m["pointer"]:m["pointer"] + len(raw)]
        check(raw == orig, f"{m['id']}: 바이트 불일치 @0x{m['pointer']:06X}")

    # 3. 본문 영역 완전 재구성
    lo, hi = data["body_extent"]["start"], data["body_extent"]["end"]
    buf = bytearray(b"\xAA" * (hi - lo))  # 미기록은 0xAA로 남아 원본과 달라진다
    written = bytearray(hi - lo)
    for m in msgs:
        raw = b"".join(struct.pack("<H", w) for w in m["codes"])
        s = m["pointer"] - lo
        buf[s:s + len(raw)] = raw
        for k in range(s, s + len(raw)):
            written[k] = 1
    for p in data["padding"]:
        raw = bytes.fromhex(p["bytes"])
        s = p["offset"] - lo
        buf[s:s + len(raw)] = raw
        for k in range(s, s + len(raw)):
            written[k] = 1

    unwritten = [i + lo for i, v in enumerate(written) if not v]
    check(not unwritten,
          f"미기록 {len(unwritten)}바이트, 최초 0x{unwritten[0]:06X}" if unwritten else "")

    orig = rom[lo:hi]
    if bytes(buf) != orig:
        diff = [i for i in range(len(orig)) if buf[i] != orig[i]]
        check(False, f"재조립 불일치 {len(diff)}바이트, 최초 0x{diff[0] + lo:06X}")

    # 결과
    total = hi - lo
    print(f"분모: 본문 0x{lo:06X}-0x{hi:06X} = {total} 바이트")
    print(f"메시지 {len(msgs)}건 + 정렬 패딩 {len(data['padding'])}곳")
    if failures:
        print(f"\nFAIL {len(failures)}건")
        for f in failures[:20]:
            print("  -", f)
        return 1
    print("\nPASS — 본문 전체가 바이트 동일하게 재구성됨")
    return 0


if __name__ == "__main__":
    sys.exit(main())
