"""빌드 이름이 바뀌어도 기존 세이브를 이어 쓰도록 복사한다.

Mesen 은 배터리 세이브를 `<Mesen>/Saves/<ROM 파일명>.sav` 로 관리한다.
빌드 파일명이 바뀌면 새 이름의 세이브가 없어 게임이 빈 슬롯으로 시작한다.

**주의**: 헤드리스 프로브를 빌드 이름으로 돌리면 그 빌드의 세이브가 새 게임 상태로
덮인다. 프로브는 `work/run_named.py` 처럼 `_probe` 라는 별도 이름으로 돌려야 한다.
그 사고를 막으려고 여기서는 진행도가 더 적은 세이브로 덮어쓰려 하면 막는다.

사용:
  link_save.py --list
  link_save.py --to build/mzm_ko_rc5.gba                    # 진행도가 가장 많은 것에서
  link_save.py --to ... --from build/mzm_ko_rc2.gba         # 원본 지정
  link_save.py --to ... --from ... --force                  # 진행도 역전도 강행
"""
import argparse
import hashlib
import shutil
import sys
import time
from collections import Counter
from pathlib import Path

SAVES = Path(r"H:\Mesen\Saves")
PROBE = "_probe"


def digest(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:12]


def richness(p: Path) -> int:
    """세이브에 든 내용의 양(서로 다른 바이트 수). 빈 세이브일수록 낮다."""
    return len(Counter(p.read_bytes()))


def candidates():
    out = [q for q in SAVES.glob("*.sav")
           if q.stem.startswith("mzm") and q.stem != PROBE]
    return sorted(out, key=lambda q: (richness(q), q.stat().st_mtime), reverse=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--to")
    ap.add_argument("--from", dest="src")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()

    if not SAVES.is_dir():
        print(f"세이브 폴더 없음: {SAVES}")
        return 1

    if a.list or not a.to:
        print(f"{SAVES} 의 mzm 세이브 (내용 많은 순):")
        for q in candidates():
            t = time.strftime("%Y-%m-%d %H:%M", time.localtime(q.stat().st_mtime))
            print(f"  {q.name:28s} 내용 {richness(q):3d}  {t}  {digest(q)}")
        return 0

    dst = SAVES / (Path(a.to).stem + ".sav")
    if a.src:
        s = Path(a.src)
        src = s if s.suffix == ".sav" else SAVES / (s.stem + ".sav")
    else:
        cands = [q for q in candidates() if q != dst]
        if not cands:
            print("복사할 세이브가 없다")
            return 1
        src = cands[0]

    if not src.is_file():
        print(f"원본 세이브 없음: {src}")
        return 1
    if src == dst:
        print(f"원본과 대상이 같다: {dst.name}")
        return 0

    if dst.is_file():
        if digest(dst) == digest(src):
            print(f"이미 같은 내용: {dst.name}")
            return 0
        if richness(dst) > richness(src) and not a.force:
            print(f"거부 — 대상이 원본보다 진행도가 많다: "
                  f"{dst.name}(내용 {richness(dst)}) > {src.name}(내용 {richness(src)}). "
                  f"덮어쓰려면 --force")
            return 1
        bak = dst.with_suffix(".sav.bak-" + time.strftime("%Y%m%d-%H%M%S"))
        shutil.copy2(dst, bak)
        print(f"기존 세이브 백업: {bak.name}")

    shutil.copy2(src, dst)
    print(f"세이브 연동: {src.name}(내용 {richness(src)}) -> {dst.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
