"""지역 지도 화면 지역명 라벨(BG3 타일셋 + 타일맵) 교체 검사.

1. 글리프 — 모든 라벨 문자가 8x8 시트에 있어야 한다.
1b. 가나 블록 — 히라가나 모드는 타일셋을 32타일 밀어 올리므로 두 블록에 같은 그림이 있어야 한다.
2. 타일 배정 — t325..351 안에서만 쓰고 t344(파란 막대)는 건드리지 않으며 서로 겹치지 않는다.
3. 배치 성공 — 어느 타일맵에서도 '자리 부족'이 나오면 안 된다.
4. 칸 충돌 — 한 타일맵 안에서 두 라벨의 새 칸 구간이 겹치면 안 된다.
5. 꼬리 제거 — 패치 후 타일맵에 원문 전용 타일이 남아 있으면 안 된다.
6. 공간 — 재압축본이 원본 압축 크기 안에 들어가야 한다.
7. VRAM 안전 — 타일맵 압축 스트림에 거리 1 참조가 없어야 한다.
"""
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[1] / "scripts"))

import map_gfx  # noqa: E402
from bitmap_font import SMALL  # noqa: E402
from lz77 import decompress  # noqa: E402
from rombuild import load_source  # noqa: E402
from test_obj_gfx import scan_distances  # noqa: E402

KEEP = 344          # 파란 막대 타일 — 라벨과 무관하므로 보존해야 한다
LO, HI = 325, 351   # 쓸 수 있는 타일 범위


def main() -> int:
    rom = load_source()
    fails: list[str] = []

    # 1. 글리프
    for en, seq, ko, nt0 in map_gfx.LABELS:
        missing = [c for c in ko if not SMALL.has(c)]
        if missing:
            fails.append(f"{en}: 시트에 없는 글자 {missing}")

    # 2. 타일 배정
    claimed: dict[int, str] = {}
    for en, seq, ko, nt0 in map_gfx.LABELS:
        for k in range(len(ko)):
            t = nt0 + k
            if not (LO <= t <= HI):
                fails.append(f"{en}: 타일 {t} 가 범위 {LO}..{HI} 밖")
            if t == KEEP:
                fails.append(f"{en}: 보존 타일 {KEEP} 를 덮어쓴다")
            if t in claimed:
                fails.append(f"타일 {t} 중복 배정: {claimed[t]} / {en}")
            claimed[t] = en

    tile_writes, map_writes, log = map_gfx.apply(rom)

    # 2b. 가나 블록 미러 — 한자/히라가나 두 모드가 같은 그림을 보게
    by_off = {off: data for off, data, _ in tile_writes}
    for t in sorted(claimed):
        a, b = map_gfx.TILESET + t * 32, map_gfx.TILESET + (t + map_gfx.KANA_SHIFT) * 32
        if a not in by_off or b not in by_off:
            fails.append(f"타일 {t}: 한자/가나 두 블록 중 한쪽만 쓴다")
        elif by_off[a] != by_off[b]:
            fails.append(f"타일 {t}: 두 블록의 그림이 다르다")

    # 3. 배치 성공
    for line in log:
        if "!!" in line:
            fails.append(line.strip())

    # 원문 전용 타일 = 어느 한글 라벨에도 배정되지 않은 옛 타일
    old = {t for _, seq, _, _ in map_gfx.LABELS for t in seq}
    orphan = old - set(claimed)

    packed_by_addr = {a: p for a, p, _, _ in map_writes}
    seen: set[int] = set()
    for _, addr in map_gfx.map_pointers(rom):
        if addr in seen:
            continue
        seen.add(addr)
        raw, csize = decompress(rom, addr)
        tm = bytearray(raw)
        map_gfx.patch_tilemap(tm, [], "", addr)

        # 4. 칸 충돌 — 라벨이 실제로 쓴 칸을 다시 세어 중복을 찾는다
        used: dict[int, str] = {}
        for en, cy, cx, seq, ko, nt0 in map_gfx.find_labels(raw):
            span = {nt0 + k for k in range(len(ko))}
            for i in range(len(tm) // 2):
                if (struct.unpack_from("<H", tm, i * 2)[0] & 0x3FF) in span:
                    if i in used and used[i] != en:
                        fails.append(f"0x{addr:06X}: 칸 {i} 를 {used[i]} 와 {en} 이 함께 쓴다")
                    used[i] = en

        # 5. 꼬리 제거
        left = {struct.unpack_from("<H", tm, i * 2)[0] & 0x3FF
                for i in range(len(tm) // 2)} & orphan
        if left:
            fails.append(f"0x{addr:06X}: 원문 타일 잔재 {sorted(left)}")

        # 6·7. 공간·VRAM 안전
        p = packed_by_addr.get(addr)
        if p is None:
            continue
        if len(p) > csize:
            fails.append(f"0x{addr:06X}: 재압축 {len(p)}B > 원본 {csize}B")
        if decompress(bytes(p) + b"\0" * 8, 0)[0] != bytes(tm):
            fails.append(f"0x{addr:06X}: 재압축 왕복 불일치")
        d = scan_distances(bytes(p))
        if d < 2:
            fails.append(f"0x{addr:06X}: 참조 거리 {d} < 2 (VRAM 위험)")

    for line in log:
        print(f"  {line}")
    print(f"타일 쓰기 {len(tile_writes)}개, 타일맵 재압축 {len(map_writes)}개")
    if fails:
        print("\n실패:")
        for f in fails:
            print(f"  - {f}")
        return 1
    print("지도 지역명 검사 통과")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
