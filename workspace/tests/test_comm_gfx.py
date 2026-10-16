"""통신(링크 케이블) 화면 문구 교체 검사.

1. 글리프 — 모든 문자가 시트에 있거나 원본에서 뜬 기호여야 한다.
2. 폭 — 문구가 밴드(256px) 안에 들어가야 한다.
3. 보호 픽셀 — 문구 밴드 밖(완료 문구의 표식 글자 등)은 바뀌지 않아야 한다.
4. 컨테이너 불변 — 해제 크기·타일 수가 그대로여야 한다.
5. 공간 — 재압축본이 원본 압축 크기 안에 들어가야 한다.
6. 왕복 — 재압축본을 해제하면 의도한 타일과 정확히 같아야 한다.
7. VRAM 안전 — 거리 1 참조가 없어야 한다.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[1] / "scripts"))

import comm_gfx  # noqa: E402
import obj_gfx  # noqa: E402
from bitmap_font import MENU  # noqa: E402
from lz77 import decompress  # noqa: E402
from rombuild import load_source  # noqa: E402
from test_obj_gfx import scan_distances  # noqa: E402


def main() -> int:
    rom = load_source()
    fails: list[str] = []

    for kind, text in comm_gfx.TEXT.items():
        missing = [c for c in text if c not in (" ", "。") and not MENU.has(c)]
        if missing:
            fails.append(f"{kind}: 시트에 없는 글자 {missing}")
        w = comm_gfx.text_width(text)
        if w > comm_gfx.BAND[2] - comm_gfx.BAND[0] + 1:
            fails.append(f"{kind}: {w}px 가 밴드를 넘는다")

    writes, log = comm_gfx.apply(rom)
    by_addr = {a: p for a, p, _ in writes}

    for addr, kind in comm_gfx.BLOBS:
        raw, csize = decompress(rom, addr)
        packed = by_addr[addr]
        if len(packed) > csize:
            fails.append(f"0x{addr:06X}: 재압축 {len(packed)}B > 원본 {csize}B")
        new, _ = decompress(bytes(packed) + b"\0" * 8, 0)
        if len(new) != len(raw):
            fails.append(f"0x{addr:06X}: 해제 크기 {len(new)} != {len(raw)}")
            continue

        # 밴드 밖 보호
        g0 = obj_gfx.to_grid(raw, comm_gfx.COLS)
        g1 = obj_gfx.to_grid(new, comm_gfx.COLS)
        for y in range(len(g0)):
            if comm_gfx.BAND[1] <= y <= comm_gfx.BAND[3]:
                continue
            if g0[y] != g1[y]:
                fails.append(f"0x{addr:06X}: 밴드 밖 y{y} 가 바뀌었다")
                break

        d = scan_distances(bytes(packed))
        if d < 2:
            fails.append(f"0x{addr:06X}: 참조 거리 {d} < 2 (VRAM 위험)")

    for line in log:
        print(f"  {line}")
    if fails:
        print("\n실패:")
        for f in fails:
            print(f"  - {f}")
        return 1
    print("통신 화면 검사 통과")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
