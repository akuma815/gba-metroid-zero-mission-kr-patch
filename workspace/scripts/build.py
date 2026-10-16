"""한국어 패치 통합 빌드.

불변 원본에서 시작해 아래를 한 빌드로 적용한다.
  1. 한글 글리프 설치 — 배정표(hangul_codes.json)의 각 글자에 전각 코드 쌍 4타일
  2. 번역문 재삽입 — lang0(kanji)/lang1(kana) 두 슬롯이 같은 본문을 공유하도록
     포인터를 같은 주소로 맞춘다. lang2(english)는 원본 유지.
  3. 줄 시작 X 좌표 재계산 — 원본 줄의 중심을 보존한다(layout.py)

모든 쓰기는 RomBuilder 의 Expected Write 와 writer 충돌 검사를 거친다.
"""
import argparse
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bitmap_font  # noqa: E402
import charmap  # noqa: E402
from hangul_alloc import Allocation  # noqa: E402
from hangul_glyph import fullwidth_tiles, glyph_extent, outline, render_bitmap  # noqa: E402
from layout import (  # noqa: E402
    CTRL_X_LINE,
    NEWLINE,
    TERMINATOR,
    SCREEN_WIDTH,
    line_width,
    patched_width_rom,
    split_lines,
    x_for_center,
)
from rombuild import PROJECT, RomBuilder, glyph_offsets  # noqa: E402
from tokens import text_to_codes  # noqa: E402

LEDGER = PROJECT / "workspace" / "text" / "translation" / "ko.json"
ALLOC = PROJECT / "workspace" / "text" / "translation" / "hangul_codes.json"
SCOPE_EXC = PROJECT / "workspace" / "text" / "translation" / "scope_exceptions.json"

# 폰트 사양 (workspace/analysis/POC.md 채택안)
TTF = "Galmuri11-Condensed.ttf"
SIZE = 11
AT = (1, 3)

# 폭 함수: code <= 0x49F 이면 폭 테이블, 초과면 기본 상수.
# 한글 배정이 0x0440 부터라 앞쪽 글자들이 폭 테이블 범위에 걸린다.
# 그대로 두면 원본 한자 폭(3~8px)을 물려받아 자간이 제각각이 된다
# (실제로 '파'가 3px 이라 다음 글자와 겹쳤다). 해당 항목을 진행폭으로 덮어쓴다.
WIDTH_TABLE = 0x40D80C
WIDTH_MAX_CODE = 0x49F
WIDTH_CONST_OFF = 0x06E498
WIDTH_CONST_ORIG = bytes([0x0A, 0x20])  # movs r0, #10

# 본문 배치 시작 = 원본 lang0 본문 시작
TEXT_BASE = 0x4414BC
TEXT_LIMIT = 0x445400  # 원본 lang0+lang1 영역의 끝(그 뒤는 lang2)

GROUPS = {
    "msg_a": {"meta": 0x760890, "count": 65},
    "msg_b": {"meta": 0x7603E4, "count": 62},
}


def install_font(b: RomBuilder, alloc: Allocation, ttf: str, size: int,
                 at: tuple[int, int], advance: int,
                 bitmap: bool = False) -> tuple[int, int, int]:
    """한글 글리프를 설치하고 (글자 수, 폭 테이블 수정 수, 최대 글리프 폭)을 돌려준다.

    bitmap=True 면 TTF 렌더 대신 비트맵 시트(bitmap_font.py)에서 글리프를 가져온다.
    """
    n = fixed = 0
    maxw = 0
    for ch, lo in sorted(alloc.char_to_code.items(), key=lambda kv: kv[1]):
        if bitmap:
            rows = outline(bitmap_font.place_in_cell(ch, box=(16, 16), at=at))
        else:
            rows = outline(render_bitmap(ch, ttf, size, box=(16, 16), at=at))
        x0, x1, _, _ = glyph_extent(rows)
        maxw = max(maxw, x1 + 1)
        t = fullwidth_tiles(rows)
        l_top, l_bot = glyph_offsets(lo)
        r_top, r_bot = glyph_offsets(lo + 1)
        for off, data, tag in ((l_top, t["left_top"], "LT"), (l_bot, t["left_bottom"], "LB"),
                               (r_top, t["right_top"], "RT"), (r_bot, t["right_bottom"], "RB")):
            b.write(off, data, expected=b.source[off:off + 32], who=f"font:{ch}:{tag}")
        # 폭 테이블 범위에 걸린 한글은 진행폭을 명시한다
        if lo <= WIDTH_MAX_CODE:
            off = WIDTH_TABLE + lo
            if b.source[off] != advance:
                b.write(off, bytes([advance]), expected=b.source[off:off + 1],
                        who=f"width:{ch}")
                fixed += 1
        n += 1
    return n, fixed, maxw


def relayout(codes: list[int], layout: list[dict], rom: bytes, eid: str = "?") -> list[int]:
    """줄 시작 X 를 원본 중심 기준으로 재계산한다.

    원본 줄에 X 가 있었다면(center 확정) 번역문에 X 토큰이 빠져 있어도 삽입한다.
    번역자가 `{x:NN}` 을 빠뜨리면 그 줄이 엉뚱한 위치에 그려지므로 조용히 넘기지 않는다.
    원본에 X 가 없던 줄(center=None)은 좌측 정렬이므로 손대지 않는다.
    """
    out: list[int] = []
    for i, line in enumerate(split_lines(codes)):
        w = line_width(line, rom)
        if w > SCREEN_WIDTH:
            raise ValueError(f"{eid} L{i}: 폭 {w}px > 화면 {SCREEN_WIDTH}px")
        center = layout[i]["center"] if i < len(layout) else None
        if center is None:
            out.extend(line)
            out.append(NEWLINE)
            continue

        new_x = x_for_center(center, w)
        if new_x < 0:
            raise ValueError(
                f"{eid} L{i}: 폭 {w}px 가 중심 {center} 에 맞지 않는다 "
                f"(X={new_x}). 최대 {int(center) * 2}px 까지 가능 — {w - int(center) * 2}px 축약 필요")
        if new_x > 0xFF:
            raise ValueError(f"{eid} L{i}: X={new_x} 범위 밖")

        done = False
        for c in line:
            if not done and (c >> 8) == CTRL_X_LINE:
                out.append((CTRL_X_LINE << 8) | new_x)
                done = True
            else:
                out.append(c)
        if not done:  # 번역문에 X 토큰이 없으면 줄 앞에 삽입
            out = out[:len(out) - len(line)] + [(CTRL_X_LINE << 8) | new_x] + line
        out.append(NEWLINE)
    out[-1] = TERMINATOR  # 마지막 줄바꿈을 종료자로
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(PROJECT / "build" / "mzm_ko.gba"))
    ap.add_argument("--font", default=TTF)
    ap.add_argument("--size", type=int, default=SIZE)
    ap.add_argument("--at", default=",".join(map(str, AT)))
    ap.add_argument("--advance", type=int, default=10,
                    help="한글 진행폭 픽셀 (기본 10 = 원본 상수 유지)")
    ap.add_argument("--ttf", action="store_true",
                    help=f"기본 비트맵 시트({bitmap_font.SHEET}) 대신 TTF 렌더를 쓴다")
    ap.add_argument("--release", action="store_true",
                    help="배포 후보 빌드: distribution_eligible 항목만 허용한다")
    ap.add_argument("--no-menu-gfx", action="store_true",
                    help="메뉴 그래픽(LZ77) 한글 교체를 건너뛴다")
    ap.add_argument("--no-obj-gfx", action="store_true",
                    help="언어별 그래픽 텍스트(OBJ/BG) 한글 교체를 건너뛴다")
    ap.add_argument("--no-title-gfx", action="store_true",
                    help="타이틀 로고 한글 교체를 건너뛴다")
    ap.add_argument("--no-map-gfx", action="store_true",
                    help="지도 화면 지역명 라벨 교체를 건너뛴다")
    ap.add_argument("--no-comm-gfx", action="store_true",
                    help="통신(링크) 화면 문구 교체를 건너뛴다")
    ap.add_argument("--link-save", action="store_true",
                    help="Mesen 세이브를 새 빌드 이름으로 복사한다 "
                         "(빌드 파일명이 바뀌면 세이브가 끊기기 때문)")
    ap.add_argument("--allow-untranslated", action="store_true",
                    help="미번역 항목을 원문 유지로 허용(개발 빌드)")
    a = ap.parse_args()
    a.bitmap = not a.ttf
    at = tuple(int(v) for v in a.at.split(","))
    if a.bitmap and a.at == ",".join(map(str, AT)):
        at = (1, 2)   # 9x12 시트는 잉크가 셀 좌상단부터라 기본 배치를 따로 둔다

    charmap.reload_hangul()
    b = RomBuilder()
    rom = b.source
    led = json.loads(LEDGER.read_text(encoding="utf-8"))
    alloc = Allocation(ALLOC)

    # 배포 적격성 판정 — 검토 전 번역이 섞인 빌드는 배포 후보가 될 수 없다
    from collections import Counter
    states = Counter(e["status"] for e in led["entries"])
    ineligible = {s: n for s, n in states.items() if s != "distribution_eligible"}
    if a.release and ineligible:
        print("배포 후보 빌드 불가 — 미승인 항목이 있다:", ineligible)
        print("사용자 검토·승인 후 상태를 distribution_eligible 로 올려야 한다.")
        return 1

    # 범위 예외 — 제외 승인(approved)이나 번역 완료(done)가 아닌 항목은 배포를 막는다
    exc = json.loads(SCOPE_EXC.read_text(encoding="utf-8")) if SCOPE_EXC.is_file() else None
    exc_items = exc["exceptions"] if exc else []
    OK_STATES = ("approved", "done")
    pending_exc = [e["id"] for e in exc_items if e.get("state") not in OK_STATES]
    if a.release and pending_exc:
        print(f"배포 후보 빌드 불가 — 미해결 범위 항목 {len(pending_exc)}건:")
        for e in exc_items:
            if e.get("state") not in OK_STATES:
                pr = f"[{e.get('priority', '-')}] " if e.get("priority") else ""
                print(f"  - {pr}{e['id']} ({e.get('state')}): {e['content']}")
                print(f"      영향: {e['player_impact']}")
        print("번역해서 done 으로 올리거나, 제외 사유를 승인해 approved 로 올려야 한다.")
        print("screen_pending 은 삽입까지 끝났고 실화면 확인만 남은 항목이다.")
        return 1

    is_test_build = bool(ineligible) or bool(pending_exc)

    # 1. 폰트 + 폭
    if a.bitmap:
        missing_glyph = [c for c in alloc.char_to_code if not bitmap_font.has(c)]
        if missing_glyph:
            print(f"비트맵 시트에 없는 글자 {len(missing_glyph)}자: {missing_glyph[:10]}")
            return 1
    n, fixed, maxw = install_font(b, alloc, a.font, a.size, at, a.advance, a.bitmap)
    src = f"비트맵 {bitmap_font.SHEET}" if a.bitmap else f"{a.font} {a.size}px"
    print(f"폰트: {src} at={at}, 한글 {n}자 설치 "
          f"(글리프 최대 폭 {maxw}px, 폭 테이블 보정 {fixed}자)")
    if a.advance != 10:
        b.write(WIDTH_CONST_OFF, bytes([a.advance, 0x20]),
                expected=WIDTH_CONST_ORIG, who=f"width:default={a.advance}")
        print(f"기본 진행폭 10 -> {a.advance}px")
    if maxw > a.advance:
        print(f"  ** 경고: 글리프 폭 {maxw}px > 진행폭 {a.advance}px — 겹침 **")

    # 2. 번역문 인코딩 + X 재계산
    missing = [e["id"] for e in led["entries"] if not e["ko"]]
    if missing and not a.allow_untranslated:
        print(f"미번역 {len(missing)}건: {missing[:5]} — 중단")
        return 1

    # X 재계산에는 폭 테이블이 최종 상태인 이미지를 쓴다.
    # 테이블 밖 코드는 기본 상수를 따르므로 그 값도 맞춘다.
    wrom = patched_width_rom(rom, alloc.char_to_code.values(), a.advance)
    import layout as _layout
    _layout.WIDTH_DEFAULT = a.advance

    blobs = {}
    for e in led["entries"]:
        if not e["ko"]:
            continue
        codes = relayout(text_to_codes(e["ko"]), e["protected"]["layout"], wrom, e["id"])
        blobs[e["id"]] = b"".join(struct.pack("<H", w) for w in codes)

    total = sum(len(v) for v in blobs.values())
    print(f"본문: {len(blobs)}건, {total} 바이트 (한 벌, lang0/lang1 공유)")
    if TEXT_BASE + total > TEXT_LIMIT:
        print(f"공간 초과: 0x{TEXT_BASE + total:06X} > 0x{TEXT_LIMIT:06X}")
        return 1

    # 2.5 메뉴 그래픽(LZ77 블롭) 한글 교체
    if not a.no_menu_gfx:
        import menu_gfx
        from lz77 import compress as _lz_compress
        grid, orig_size = menu_gfx.load(rom)
        applied = menu_gfx.apply_translation(grid)
        # 작은 글씨(세이브 요약 난이도·지역명)는 타일 순서 평면에서 따로 교체한다
        raw2, small_log = menu_gfx.apply_small(menu_gfx.to_tiles(grid))
        packed = _lz_compress(raw2, optimal=True)
        if len(packed) > orig_size:
            print(f"메뉴 그래픽 재압축 {len(packed)}B > 원본 {orig_size}B — 재배치 필요")
            return 1
        b.write(menu_gfx.BLOB, packed,
                expected=rom[menu_gfx.BLOB:menu_gfx.BLOB + len(packed)],
                who="menu_gfx")
        print(f"메뉴 그래픽: 큰 글씨 {len(applied)}개 + 작은 글씨 {len(small_log)}개 교체, "
              f"압축 {orig_size} -> {len(packed)}B (여유 {orig_size - len(packed)}B)")
        for line in applied + small_log:
            print(f"  {line}")

    # 2.6 데이터 삭제 확인 화면(LZ77 블롭 2개) 한글 교체
    if not a.no_menu_gfx:
        import confirm_gfx
        for cbase, cpacked, corig, clog in confirm_gfx.apply(rom):
            if len(cpacked) > corig:
                print(f"삭제 확인 0x{cbase:06X} 재압축 {len(cpacked)}B > {corig}B — 재배치 필요")
                return 1
            b.write(cbase, cpacked, expected=rom[cbase:cbase + len(cpacked)],
                    who=f"confirm_gfx:{cbase:06X}")
            print(f"삭제 확인 0x{cbase:06X}: {len(clog)}줄 교체, "
                  f"압축 {corig} -> {len(cpacked)}B")
            for line in clog:
                print(f"  {line}")

    # 2.7 언어별 그래픽 텍스트(OBJ/BG 자산) 한글 교체 + lang0 포인터 통일
    if not a.no_obj_gfx:
        import obj_gfx
        for gid in obj_gfx.GROUPS:
            base, packed, orig, slot, glog = obj_gfx.apply_group(rom, gid)
            if len(packed) > orig:
                print(f"{gid} 재압축 {len(packed)}B > 원본 {orig}B — 재배치 필요")
                return 1
            b.write(base, packed, expected=rom[base:base + len(packed)],
                    who=f"obj_gfx:{gid}")
            off, exp, new = obj_gfx.lang0_patch(rom, gid)
            b.write(off, new, expected=exp, who=f"obj_ptr:{gid}")
            print(f"그래픽 {gid} 0x{base:06X}: {len(glog)}개 라벨, "
                  f"압축 {orig} -> {len(packed)}B (여유 {orig - len(packed)}B), "
                  f"lang0 0x{off:06X} -> 0x{base:06X}")
            for line in glog:
                print(f"  {line}")

    # 2.8 타이틀 로고 한글 교체
    if not a.no_title_gfx:
        import title_gfx
        tbase, tpacked, torig, tlog = title_gfx.apply(rom)
        if len(tpacked) > torig:
            print(f"타이틀 재압축 {len(tpacked)}B > 원본 {torig}B — 재배치 필요")
            return 1
        b.write(tbase, tpacked, expected=rom[tbase:tbase + len(tpacked)],
                who="title_gfx")
        print(f"타이틀 로고 0x{tbase:06X}: 압축 {torig} -> {len(tpacked)}B "
              f"(여유 {torig - len(tpacked)}B)")
        for line in tlog:
            print(f"  {line}")

    # 2.9 지역 지도 화면의 지역명 라벨(BG3 타일셋 + 타일맵)
    if not a.no_map_gfx:
        import map_gfx
        tile_writes, map_writes, mlog = map_gfx.apply(rom)
        for off, data, who in tile_writes:
            b.write(off, data, expected=rom[off:off + len(data)], who=who)
        for addr, packed, csize, ptr in map_writes:
            if len(packed) > csize:
                print(f"지도 타일맵 0x{addr:06X} 재압축 {len(packed)}B > {csize}B — 재배치 필요")
                return 1
            b.write(addr, packed, expected=rom[addr:addr + len(packed)],
                    who=f"map_tilemap:0x{addr:06X}")
        print(f"지도 지역명: 타일 {len(tile_writes)}개, 타일맵 {len(map_writes)}개 재압축")
        for line in mlog:
            print(f"  {line}")

    # 2.10 통신(링크 케이블) 화면 문구
    if not a.no_comm_gfx:
        import comm_gfx
        cwrites, clog2 = comm_gfx.apply(rom)
        for addr, packed, csize in cwrites:
            if len(packed) > csize:
                print(f"통신 화면 0x{addr:06X} 재압축 {len(packed)}B > {csize}B — 재배치 필요")
                return 1
            b.write(addr, packed, expected=rom[addr:addr + len(packed)],
                    who=f"comm_gfx:0x{addr:06X}")
        print(f"통신 화면: 블롭 {len(cwrites)}개")
        for line in clog2:
            print(f"  {line}")

    # 3. 본문 배치 + 포인터 갱신
    addr = TEXT_BASE
    placed = {}
    for eid, blob in blobs.items():
        b.write(addr, blob, expected=rom[addr:addr + len(blob)], who=f"text:{eid}")
        placed[eid] = addr
        addr += len(blob)
    print(f"배치: 0x{TEXT_BASE:06X}-0x{addr:06X} (여유 {TEXT_LIMIT - addr} 바이트)")

    def lang_tables(meta):
        out = []
        for i in range(7):
            t = struct.unpack_from("<I", rom, meta + i * 4)[0] & 0xFFFFFF
            if t not in out:
                out.append(t)
        return out

    npat = 0
    for gid, g in GROUPS.items():
        tables = lang_tables(g["meta"])
        for li in (0, 1):  # kanji, kana 두 슬롯이 같은 본문을 가리키게 한다
            tbl = tables[li]
            for i in range(g["count"]):
                eid = f"{gid}:{i:03d}"
                if eid not in placed:
                    continue
                slot = tbl + i * 4
                newv = struct.pack("<I", 0x08000000 | placed[eid])
                b.write(slot, newv, expected=rom[slot:slot + 4], who=f"ptr:{eid}:L{li}")
                npat += 1
    print(f"포인터: {npat}개 갱신")

    out = Path(a.out)
    b.save(out)
    import hashlib
    sha = hashlib.sha256(bytes(b.buf)).hexdigest()

    # 빌드 매니페스트 — 빌드 자체가 비배포 여부를 기록해 검증한다
    manifest = {
        "build": out.name,
        "sha256": sha,
        "source_sha256": led["source_baseline"]["sha256"],
        "distribution": "NOT FOR DISTRIBUTION" if is_test_build else "release_candidate",
        "reason": ("; ".join(filter(None, [
            f"미승인 번역 {sum(ineligible.values())}건" if ineligible else None,
            f"미승인 범위 예외 {len(pending_exc)}건" if pending_exc else None,
        ])) or None),
        "translation_states": dict(states),
        "pending_scope_exceptions": pending_exc,
        "glyph_source": (f"bitmap:{bitmap_font.SHEET}" if a.bitmap
                         else f"ttf:{a.font}@{a.size}px"),
        "cell_placement": list(at),
        "advance_px": a.advance,
        "hangul_chars": n,
        "messages": len(blobs),
        "text_bytes": total,
        "pointer_updates": npat,
        "declared_changes": len(b.changes),
    }
    out.with_suffix(".manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")

    if a.link_save:
        import subprocess
        r = subprocess.run([sys.executable, str(Path(__file__).with_name("link_save.py")),
                            "--to", str(out)], capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        print((r.stdout or "").strip() or (r.stderr or "").strip())

    print()
    print(f"변경 선언 {len(b.changes)}건")
    print("SHA-256:", sha)
    if is_test_build:
        print(f"** 검증용 빌드 (배포 불가) — 상태: {ineligible}")
    print(f"출력: {out}")
    print(f"매니페스트: {out.with_suffix('.manifest.json').name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
