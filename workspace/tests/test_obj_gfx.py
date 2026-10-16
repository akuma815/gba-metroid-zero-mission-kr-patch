"""언어별 그래픽 텍스트(OBJ/BG 자산) 교체 검사.

1. 보호 픽셀 — 라벨 상자 밖은 원본과 바이트 동일해야 한다.
2. 컨테이너 불변 — 해제 크기·타일 수가 그대로여야 한다.
3. VRAM 안전 — 거리 1 참조가 없어야 한다(BIOS 가 VRAM 에 16비트로 쓰기 때문).
4. 왕복 — 재압축본을 해제하면 의도한 격자와 정확히 같아야 한다.
5. 공간 — 재압축본이 원본 압축 크기 안에 들어가야 한다.
6. 글리프 — 모든 라벨 문자가 시트에 있어야 한다.
7. 폭 — 모든 라벨이 상자 폭 안에 들어가야 한다.
"""
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[1] / "scripts"))

import obj_gfx  # noqa: E402
from bitmap_font import SMALL  # noqa: E402
from lz77 import decompress  # noqa: E402
from rombuild import load_source  # noqa: E402


def scan_distances(stream: bytes) -> int:
    """압축 스트림의 최소 참조 거리를 돌려준다(참조가 없으면 큰 값)."""
    size = struct.unpack_from("<I", stream, 0)[0] >> 8
    p, out, mind = 4, 0, 1 << 30
    while out < size:
        flags = stream[p]
        p += 1
        for bit in range(8):
            if out >= size:
                break
            if flags & (0x80 >> bit):
                b0, b1 = stream[p], stream[p + 1]
                p += 2
                mind = min(mind, (((b0 & 0xF) << 8) | b1) + 1)
                out += (b0 >> 4) + 3
            else:
                p += 1
                out += 1
    return mind


def main():
    rom = load_source()
    fails = []
    for gid, g in obj_gfx.GROUPS.items():
        ja_raw, ja_size = decompress(rom, g["ja"])
        base, packed, orig, slot, log = obj_gfx.apply_group(rom, gid)
        assert base == g["ja"] and orig == ja_size

        # 5. 공간
        if len(packed) > orig:
            fails.append(f"{gid}: 재압축 {len(packed)}B > 원본 {orig}B")

        new_raw, _ = decompress(packed + b"\x00" * 8, 0)

        # 2. 컨테이너 불변
        if len(new_raw) != len(ja_raw):
            fails.append(f"{gid}: 해제 크기 {len(new_raw)} != 원본 {len(ja_raw)}")
            continue

        # 3. VRAM 안전
        mind = scan_distances(packed)
        if mind < 2:
            fails.append(f"{gid}: 거리 {mind} 참조 — VRAM 해제에서 깨진다")

        # 1. 보호 픽셀 — 라벨 상자 밖 픽셀은 하나도 바뀌면 안 된다
        cols = g.get("stride")
        old_g = obj_gfx.to_grid(ja_raw, cols)
        new_g = obj_gfx.to_grid(new_raw, cols)
        gw, gh = len(old_g[0]), len(old_g)
        inside = set()
        for lab in g["labels"]:
            x0, y0, x1, y1 = lab["box"]
            for y in range(y0, y1 + 1):
                inside.update((y, x) for x in range(x0, x1 + 1))
        nt = len(ja_raw) // 32
        outside_changed = [(y, x) for y in range(gh) for x in range(gw)
                           if (y, x) not in inside and old_g[y][x] != new_g[y][x]]
        if outside_changed:
            fails.append(f"{gid}: 상자 밖 {len(outside_changed)}픽셀이 바뀌었다 "
                         f"(최초 {outside_changed[0]})")
        touched = {(y // 8) * (gw // 8) + x // 8 for y, x in inside}

        # 4. 왕복 — 격자 <-> 타일 변환이 손실 없이 돌아와야 한다
        want = obj_gfx.to_tiles(new_g, nt)
        if want != new_raw:
            fails.append(f"{gid}: 격자 왕복 불일치")

        # 6/7. 글리프·폭
        sheet = g.get("sheet", SMALL)
        adv = g.get("advance", obj_gfx.ADVANCE)
        for lab in g["labels"]:
            x0, _, x1, _ = lab["box"]
            for ch in lab["ko"]:
                if ch != " " and not sheet.has(ch):
                    fails.append(f"{gid}: 시트에 없는 글자 {ch!r} ({lab['ko']})")
            w = obj_gfx.text_width(lab["ko"], adv)
            if w > x1 - x0 + 1:
                fails.append(f"{gid}: '{lab['ko']}' {w}px > 상자 {x1 - x0 + 1}px")

        # 포인터 패치 대상 확인
        off, exp, new = obj_gfx.lang0_patch(rom, gid)
        if struct.unpack_from("<I", exp, 0)[0] & 0xFFFFFF != g["en"]:
            fails.append(f"{gid}: lang0 슬롯 0x{off:06X} 이 영문 블롭을 가리키지 않는다")

        print(f"{gid:12s} 0x{base:06X} {nt:3d}타일 라벨 {len(g['labels']):2d}개 "
              f"압축 {orig}->{len(packed)}B 최소거리 {mind} "
              f"보호타일 {nt - len(touched)}개 OK")

    fails += check_menu_small(rom)
    fails += check_title(rom)

    if fails:
        print("\n실패:")
        for f in fails:
            print(" -", f)
        return 1
    print("\n모든 검사 통과")
    return 0


def check_menu_small(rom: bytes) -> list[str]:
    """메뉴 블롭의 작은 글씨 구간(세이브 요약 난이도·지역명) 검사.

    이 구간은 큰 글씨와 같은 블롭 안에 있으므로 큰 글씨 교체까지 함께 적용한 뒤
    전체가 원본 압축 크기 안에 들어가는지, 상자 밖이 보존되는지를 본다.
    """
    import menu_gfx

    fails = []
    grid, orig_size = menu_gfx.load(rom)
    base_raw = menu_gfx.to_tiles(grid)          # 큰 글씨 교체 전 원본 타일
    menu_gfx.apply_translation(grid)
    big_raw = menu_gfx.to_tiles(grid)
    new_raw, log = menu_gfx.apply_small(big_raw)

    packed = compress_optimal(new_raw)
    if len(packed) > orig_size:
        fails.append(f"menu_gfx: 재압축 {len(packed)}B > 원본 {orig_size}B")
    if scan_distances(packed) < 2:
        fails.append("menu_gfx: 거리 1 참조 — VRAM 해제에서 깨진다")
    back, _ = decompress(packed + b"\x00" * 8, 0)
    if back != new_raw:
        fails.append("menu_gfx: 압축 왕복 불일치")

    # 작은 글씨 상자 밖은 큰 글씨 교체 결과와 같아야 한다
    a = obj_gfx.to_grid(big_raw)
    b = obj_gfx.to_grid(new_raw)
    inside = set()
    for ko, t0, t1 in menu_gfx.SMALL_WORDS:
        inside.update(range(t0 * 8, t1 * 8 + 8))
        w = obj_gfx.text_width(ko)
        box = (t1 - t0 + 1) * 8
        if w > box:
            fails.append(f"menu_gfx: '{ko}' {w}px > 상자 {box}px")
        for ch in ko:
            if ch != " " and not SMALL.has(ch):
                fails.append(f"menu_gfx: 시트에 없는 글자 {ch!r} ({ko})")
    changed = [(y, x) for y in range(8) for x in range(len(b[0]))
               if x not in inside and a[y][x] != b[y][x]]
    if changed:
        fails.append(f"menu_gfx: 작은 글씨 상자 밖 {len(changed)}픽셀 변경 (최초 {changed[0]})")

    # 원본 대비 실제로 바뀐 타일이 큰 글씨 + 작은 글씨 범위 안인지
    nt = len(new_raw) // 32
    touched = {t for t in range(nt)
               if base_raw[t * 32:(t + 1) * 32] != new_raw[t * 32:(t + 1) * 32]}
    print(f"menu_gfx     0x{menu_gfx.BLOB:06X} {nt}타일 "
          f"작은글씨 {len(log)}개 압축 {orig_size}->{len(packed)}B "
          f"최소거리 {scan_distances(packed)} 변경타일 {len(touched)}개 OK")
    return fails


def compress_optimal(data: bytes) -> bytes:
    from lz77 import compress
    return compress(data, optimal=True)


def check_title(rom: bytes) -> list[str]:
    """타이틀 로고 교체 검사.

    타일맵을 못 고치므로 **로고 칸(cy5..11)의 고유 타일만** 바뀌어야 한다.
    그 밖의 타일이 하나라도 바뀌면 다른 칸까지 오염된다.
    """
    import title_gfx
    from PIL import Image

    fails = []
    base, packed, orig, log = title_gfx.apply(rom)
    old, _ = decompress(rom, title_gfx.BLOB)
    new, _ = decompress(packed + bytes(8), 0)

    if len(packed) > orig:
        fails.append(f"title_gfx: 재압축 {len(packed)}B > 원본 {orig}B")
    mind = scan_distances(packed)
    if mind < 2:
        fails.append(f"title_gfx: 거리 {mind} 참조 — VRAM 해제에서 깨진다")
    if len(new) != len(old):
        fails.append(f"title_gfx: 해제 크기 {len(new)} != {len(old)}")
        return fails

    cells, cnt = title_gfx.cell_map(rom)
    allowed = {t for (cx, cy), t in cells.items() if 5 <= cy <= 11 and cnt[t] == 1}
    changed = {t for t in range(len(old) // 32)
               if old[t * 32:(t + 1) * 32] != new[t * 32:(t + 1) * 32]}
    stray = sorted(changed - allowed)
    if stray:
        fails.append(f"title_gfx: 로고 칸 밖 타일 {len(stray)}개 변경 {stray[:8]}")

    img = Image.open(title_gfx.ASSET)
    if img.mode != "P" or img.size != (240, 160):
        fails.append(f"title_gfx: 자산이 240x160 인덱스 PNG 가 아니다 "
                     f"({img.mode} {img.size})")

    print(f"title_gfx    0x{base:06X} {len(old) // 32}타일 "
          f"압축 {orig}->{len(packed)}B 최소거리 {mind} "
          f"변경타일 {len(changed)}/{len(allowed)}개 OK  ({log[0]})")
    return fails


if __name__ == "__main__":
    sys.exit(main())
